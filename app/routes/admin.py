"""
Admin API routes — all require a valid Bearer token.

GET    /api/admin/search?q=...        Search Jellyfin library
GET    /api/admin/libraries           List the server's top-level libraries
POST   /api/admin/links               Create a new share link
GET    /api/admin/links               List all share links
DELETE /api/admin/links/{uuid}        Permanently delete a link + its client records
PATCH  /api/admin/links/{uuid}/toggle Toggle is_active on/off
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from app.database import get_db
from app.auth import require_admin
from app.jellyfin import search_items, get_item, get_libraries
from app.models import CreateLinkRequest
from app.config import PUBLIC_BASE_URL, LINK_ID_LENGTH

router = APIRouter()


def _generate_link_id() -> str:
    """URL-safe random ID, exactly LINK_ID_LENGTH characters (see app/config.py)."""
    n_bytes = -(-LINK_ID_LENGTH * 3 // 4)  # ceil(LINK_ID_LENGTH * 3 / 4)
    return secrets.token_urlsafe(n_bytes)[:LINK_ID_LENGTH]


@router.get("/admin/search")
async def search_jellyfin(
    q: str,
    item_types: str | None = None,
    library_ids: str | None = None,
    _: str = Depends(require_admin),
):
    """Search the Jellyfin library by title. item_types/library_ids are comma-separated."""
    if not q.strip():
        return []
    return await search_items(
        q,
        item_types=item_types.split(",") if item_types else None,
        library_ids=library_ids.split(",") if library_ids else None,
    )


@router.get("/admin/libraries")
async def list_libraries(
    _: str = Depends(require_admin),
):
    """List the server's top-level libraries, for the library filter checklist."""
    return await get_libraries()


@router.post("/admin/links", status_code=201)
async def create_link(
    body: CreateLinkRequest,
    db: Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Create a new share link for a Jellyfin item."""
    item = await get_item(body.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Jellyfin item not found.")

    # Collision retry: astronomically unlikely at this entropy, but uuid is
    # the primary key, so handle it cheaply rather than assume it can't happen.
    for _attempt in range(5):
        link_uuid = _generate_link_id()
        async with db.execute("SELECT 1 FROM share_links WHERE uuid = ?", (link_uuid,)) as cur:
            if await cur.fetchone() is None:
                break
    else:
        raise HTTPException(status_code=500, detail="Failed to generate a unique link ID.")

    await db.execute(
        """INSERT INTO share_links
               (uuid, item_id, item_type, item_title, item_artist, needs_transcode, duration_seconds,
                expires_at, max_uses, max_clients, notes, flavor_enabled, background, flavor_text)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            link_uuid,
            body.item_id,
            item["type"],
            item["title"],
            item.get("artist"),
            1 if item.get("needs_transcode") else 0,
            item.get("duration_seconds"),
            body.expires_at,
            body.max_uses,
            body.max_clients,
            body.notes,
            1 if body.flavor_enabled else 0,
            body.background,
            body.flavor_text,
        ),
    )
    await db.commit()

    return {
        "uuid":             link_uuid,
        "url":              f"{PUBLIC_BASE_URL}/stream/{link_uuid}",
        "item_title":       item["title"],
        "item_artist":      item.get("artist"),
        "item_type":        item["type"],
        "needs_transcode":  bool(item.get("needs_transcode")),
        "duration_seconds": item.get("duration_seconds"),
        "expires_at":       body.expires_at,
        "max_uses":         body.max_uses,
        "max_clients":      body.max_clients,
        "flavor_enabled":   body.flavor_enabled,
        "background":       body.background,
        "flavor_text":      body.flavor_text,
    }


@router.get("/admin/links")
async def list_links(
    db: Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Return all share links with client count and computed status."""
    async with db.execute(
        """SELECT
               sl.*,
               (SELECT COUNT(*) FROM link_clients lc WHERE lc.link_uuid = sl.uuid) AS client_count
           FROM share_links sl
           ORDER BY sl.created_at DESC"""
    ) as cur:
        rows = await cur.fetchall()

    links = []
    for row in rows:
        d = dict(row)
        d["url"] = f"{PUBLIC_BASE_URL}/stream/{d['uuid']}"
        links.append(d)
    return links


@router.delete("/admin/links/{uuid}", status_code=200)
async def delete_link(
    uuid: str,
    db: Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Permanently delete a link and all its client records."""
    async with db.execute("SELECT uuid FROM share_links WHERE uuid = ?", (uuid,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Link not found.")

    await db.execute("DELETE FROM share_links WHERE uuid = ?", (uuid,))
    await db.commit()
    return {"deleted": uuid}


@router.patch("/admin/links/{uuid}/toggle", status_code=200)
async def toggle_link(
    uuid: str,
    db: Connection = Depends(get_db),
    _: str = Depends(require_admin),
):
    """Toggle a link between active and deactivated without deleting it."""
    async with db.execute(
        "SELECT is_active FROM share_links WHERE uuid = ?", (uuid,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Link not found.")
        new_state = 0 if row["is_active"] else 1

    await db.execute(
        "UPDATE share_links SET is_active = ? WHERE uuid = ?", (new_state, uuid)
    )
    await db.commit()
    return {"uuid": uuid, "is_active": bool(new_state)}
