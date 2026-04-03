"""
Streaming and image proxy endpoints.

GET /api/stream/{uuid}?client_id={id}
  - Validates the link is still active and the client is registered.
  - Does NOT re-increment use_count (that happened at register time).
  - Forwards Range headers so the browser can seek without re-downloading.
  - Pipes Jellyfin's response bytes directly to the client — no disk buffering.

GET /api/image/{uuid}
  - Proxies the primary cover art image from Jellyfin for the linked item.
  - Requires only a valid, non-expired link UUID — no client registration needed.
  - Keeps the Jellyfin URL and API key server-side.
"""

import datetime
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from aiosqlite import Connection
from app.config import JELLYFIN_URL, JELLYFIN_API_KEY
from app.database import get_db
from app.jellyfin import build_stream_url

router = APIRouter()

_PASSTHROUGH_HEADERS = (
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
)


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    return datetime.datetime.utcnow() > datetime.datetime.fromisoformat(expires_at)


@router.get("/stream/{uuid}")
async def stream_media(
    uuid: str,
    client_id: str,
    request: Request,
    db: Connection = Depends(get_db),
):
    # ── 1. Validate link ───────────────────────────────────────────────────────
    async with db.execute("SELECT * FROM share_links WHERE uuid = ?", (uuid,)) as cur:
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Link not found.")

    link = dict(row)

    if not link["is_active"]:
        raise HTTPException(status_code=410, detail="Link has been deactivated.")

    if _is_expired(link["expires_at"]):
        raise HTTPException(status_code=410, detail="Link has expired.")

    # ── 2. Verify client is registered (must come via watch page first) ────────
    async with db.execute(
        "SELECT 1 FROM link_clients WHERE link_uuid = ? AND client_id = ?",
        (uuid, client_id),
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=403, detail="Client not registered for this link.")

    # ── 3. Build upstream request to Jellyfin ─────────────────────────────────
    stream_url = build_stream_url(link["item_id"], link["item_type"])

    upstream_headers = {}
    if "range" in request.headers:
        upstream_headers["Range"] = request.headers["range"]

    # ── 4. Open a streaming connection to Jellyfin and pipe to client ─────────
    client = httpx.AsyncClient(timeout=None)
    jf_request = client.build_request("GET", stream_url, headers=upstream_headers)
    jf_response = await client.send(jf_request, stream=True)

    if jf_response.status_code >= 400:
        await jf_response.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail=f"Jellyfin returned {jf_response.status_code}.",
        )

    async def byte_generator():
        try:
            async for chunk in jf_response.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await jf_response.aclose()
            await client.aclose()

    response_headers = {
        k: jf_response.headers[k]
        for k in _PASSTHROUGH_HEADERS
        if k in jf_response.headers
    }

    return StreamingResponse(
        byte_generator(),
        status_code=jf_response.status_code,
        headers=response_headers,
        media_type=jf_response.headers.get("content-type", "application/octet-stream"),
    )


@router.get("/image/{uuid}")
async def get_cover_art(uuid: str, db: Connection = Depends(get_db)):
    # ── 1. Validate link exists and is active ─────────────────────────────────
    async with db.execute("SELECT * FROM share_links WHERE uuid = ?", (uuid,)) as cur:
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Link not found.")

    link = dict(row)

    if not link["is_active"] or _is_expired(link["expires_at"]):
        raise HTTPException(status_code=410, detail="Link unavailable.")

    # ── 2. Fetch item data to get the Primary image tag ───────────────────────
    # Jellyfin requires the image etag ('tag' param) to serve the image.
    # For individual audio tracks the art lives on the parent album — the tag
    # is in AlbumPrimaryImageTag and the image must be requested via AlbumId.
    async with httpx.AsyncClient() as client:
        item_r = await client.get(
            f"{JELLYFIN_URL}/Items",
            params={
                "Ids": link["item_id"],
                "Fields": "ImageTags,AlbumId,AlbumPrimaryImageTag",
                "api_key": JELLYFIN_API_KEY,
            },
            timeout=10.0,
        )
        item_r.raise_for_status()
        items = item_r.json().get("Items", [])

        if not items:
            raise HTTPException(status_code=404, detail="No cover art available.")

        item = items[0]

        # Prefer a direct primary image on the item itself
        primary_tag = item.get("ImageTags", {}).get("Primary")
        image_item_id = link["item_id"]

        # Fall back to album art for audio tracks
        if not primary_tag:
            primary_tag = item.get("AlbumPrimaryImageTag")
            image_item_id = item.get("AlbumId", link["item_id"])

        if not primary_tag:
            raise HTTPException(status_code=404, detail="No cover art available.")

        # ── 3. Fetch the image using the resolved item ID and tag ─────────────
        image_r = await client.get(
            f"{JELLYFIN_URL}/Items/{image_item_id}/Images/Primary",
            params={"tag": primary_tag, "api_key": JELLYFIN_API_KEY},
            timeout=10.0,
        )

    if image_r.status_code == 404:
        raise HTTPException(status_code=404, detail="No cover art available.")
    image_r.raise_for_status()

    return Response(
        content=image_r.content,
        media_type=image_r.headers.get("content-type", "image/jpeg"),
    )
