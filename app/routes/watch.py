"""
Public watch endpoint.

POST /api/watch/{uuid}/register
  - Called by the watch page on load before rendering the player.
  - Validates the link and client, registers the client if new, increments use_count.
  - Returns item info on success or a status code indicating why access was denied.
"""

import datetime
from fastapi import APIRouter, Depends, Request
from aiosqlite import Connection
from app.database import get_db
from app.models import RegisterRequest

router = APIRouter()


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    return datetime.datetime.utcnow() > datetime.datetime.fromisoformat(expires_at)


@router.post("/watch/{uuid}/register")
async def register_watch(
    uuid: str,
    body: RegisterRequest,
    request: Request,
    db: Connection = Depends(get_db),
):
    # ── 1. Fetch link ──────────────────────────────────────────────────────────
    async with db.execute("SELECT * FROM share_links WHERE uuid = ?", (uuid,)) as cur:
        row = await cur.fetchone()

    if row is None:
        return {"status": "not_found"}

    link = dict(row)

    # ── 2. Static checks (order matters for message clarity) ──────────────────
    if not link["is_active"]:
        return {"status": "deactivated"}

    if _is_expired(link["expires_at"]):
        return {"status": "expired"}

    # ── 3. Is this client already registered for this link? ───────────────────
    async with db.execute(
        "SELECT access_count FROM link_clients WHERE link_uuid = ? AND client_id = ?",
        (uuid, body.client_id),
    ) as cur:
        existing_client = await cur.fetchone()

    is_registered = existing_client is not None

    # ── 4. Current unique client count ────────────────────────────────────────
    async with db.execute(
        "SELECT COUNT(*) AS cnt FROM link_clients WHERE link_uuid = ?", (uuid,)
    ) as cur:
        client_count = (await cur.fetchone())["cnt"]

    # ── 5. New client — check client cap before allowing ─────────────────────
    if not is_registered and link["max_clients"] and client_count >= link["max_clients"]:
        return {"status": "client_limit"}

    # ── 6. Use cap — applies to everyone (new and returning) ─────────────────
    if link["max_uses"] and link["use_count"] >= link["max_uses"]:
        return {"status": "exhausted"}

    # ── 7. Persist: register / update client, increment global use count ──────
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if not is_registered:
        await db.execute(
            """INSERT INTO link_clients (link_uuid, client_id, ip_address, user_agent)
               VALUES (?, ?, ?, ?)""",
            (uuid, body.client_id, ip_address, user_agent),
        )
    else:
        await db.execute(
            """UPDATE link_clients
               SET last_seen = datetime('now'), access_count = access_count + 1
               WHERE link_uuid = ? AND client_id = ?""",
            (uuid, body.client_id),
        )

    await db.execute(
        "UPDATE share_links SET use_count = use_count + 1 WHERE uuid = ?", (uuid,)
    )
    await db.commit()

    return {
        "status":     "ok",
        "item_title": link["item_title"],
        "item_type":  link["item_type"],
        "expires_at": link["expires_at"],
    }
