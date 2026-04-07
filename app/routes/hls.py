"""
HLS proxy endpoints for transcoded audio streams.

GET /api/hls/{uuid}/playlist.m3u8?client_id={id}
  - Validates the link and that the client is registered.
  - Fetches Jellyfin's HLS playlist for the linked audio item.
  - Rewrites every segment / init-segment URI in the playlist so it routes
    through /api/hls/{uuid}/seg, keeping the Jellyfin URL and API key
    server-side and unreachable from the browser.
  - Returns the rewritten m3u8 to hls.js.

GET /api/hls/{uuid}/seg?p={path}&client_id={id}
  - Validates the link and client registration.
  - Fetches the requested fMP4 segment from Jellyfin and pipes the bytes
    back to the browser unchanged.
"""

import datetime
import re
from urllib.parse import quote, urlparse

import httpx
from aiosqlite import Connection
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.config import JELLYFIN_API_KEY, JELLYFIN_URL
from app.database import get_db

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    return datetime.datetime.utcnow() > datetime.datetime.fromisoformat(expires_at)


async def _validate_link_and_client(uuid: str, client_id: str, db: Connection) -> dict:
    """Validate link state and client registration; return the link row."""
    async with db.execute(
        "SELECT * FROM share_links WHERE uuid = ?", (uuid,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Link not found.")
    link = dict(row)
    if not link["is_active"]:
        raise HTTPException(status_code=410, detail="Link has been deactivated.")
    if _is_expired(link["expires_at"]):
        raise HTTPException(status_code=410, detail="Link has expired.")
    async with db.execute(
        "SELECT 1 FROM link_clients WHERE link_uuid = ? AND client_id = ?",
        (uuid, client_id),
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=403, detail="Client not registered for this link.")
    return link


def _to_jellyfin_path(uri: str) -> str:
    """
    Normalise a segment URI from the Jellyfin m3u8 to a bare path.
    Handles absolute URLs (strips scheme + host) and relative paths.
    Any existing query string is dropped — our segment endpoint adds
    the API key when fetching from Jellyfin.
    """
    if uri.startswith("http://") or uri.startswith("https://"):
        return urlparse(uri).path
    path = uri.split("?")[0]
    return path if path.startswith("/") else "/" + path


def _rewrite_m3u8(content: str, uuid: str, client_id: str) -> str:
    """
    Replace every segment / init-segment URI in a Jellyfin m3u8 with a path
    that routes through /api/hls/{uuid}/seg.
    """
    def proxy_uri(raw: str) -> str:
        path = _to_jellyfin_path(raw.strip())
        return (
            f"/api/hls/{uuid}/seg"
            f"?p={quote(path)}&client_id={quote(client_id)}"
        )

    lines = []
    for line in content.splitlines():
        # EXT-X-MAP carries the fMP4 init segment URI
        m = re.match(r'(#EXT-X-MAP:URI=")([^"]+)(".*)', line)
        if m:
            line = m.group(1) + proxy_uri(m.group(2)) + m.group(3)
        elif line and not line.startswith("#"):
            # Plain segment URI line
            line = proxy_uri(line)
        lines.append(line)
    return "\n".join(lines)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/hls/{uuid}/playlist.m3u8")
async def hls_playlist(
    uuid: str,
    client_id: str,
    db: Connection = Depends(get_db),
):
    link = await _validate_link_and_client(uuid, client_id, db)

    playlist_url = (
        f"{JELLYFIN_URL}/Audio/{link['item_id']}/main.m3u8"
        f"?AudioCodec=aac&api_key={JELLYFIN_API_KEY}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(playlist_url)
        if r.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Jellyfin returned {r.status_code} for playlist.",
            )
        raw = r.text

    rewritten = _rewrite_m3u8(raw, uuid, client_id)
    return Response(
        content=rewritten,
        media_type="application/vnd.apple.mpegurl",
    )


@router.get("/hls/{uuid}/seg")
async def hls_segment(
    uuid: str,
    p: str,
    client_id: str,
    db: Connection = Depends(get_db),
):
    await _validate_link_and_client(uuid, client_id, db)

    seg_url = f"{JELLYFIN_URL}{p}?api_key={JELLYFIN_API_KEY}"

    client = httpx.AsyncClient(timeout=None)
    jf_req = client.build_request("GET", seg_url)
    jf_resp = await client.send(jf_req, stream=True)

    if jf_resp.status_code >= 400:
        await jf_resp.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail=f"Jellyfin returned {jf_resp.status_code} for segment.",
        )

    async def byte_stream():
        try:
            async for chunk in jf_resp.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await jf_resp.aclose()
            await client.aclose()

    return StreamingResponse(
        byte_stream(),
        status_code=jf_resp.status_code,
        media_type=jf_resp.headers.get("content-type", "video/mp4"),
    )
