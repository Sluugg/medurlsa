import os
import aiosqlite
from app.config import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS share_links (
    uuid        TEXT PRIMARY KEY,
    item_id     TEXT    NOT NULL,
    item_type   TEXT    NOT NULL,
    item_title  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT,
    max_uses    INTEGER,
    max_clients INTEGER,
    use_count   INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS link_clients (
    link_uuid    TEXT NOT NULL REFERENCES share_links(uuid) ON DELETE CASCADE,
    client_id    TEXT NOT NULL,
    ip_address   TEXT,
    user_agent   TEXT,
    first_seen   TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen    TEXT NOT NULL DEFAULT (datetime('now')),
    access_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (link_uuid, client_id)
);

-- ------------------------------------------------------------
-- User / roles scaffolding (not used by any routes yet).
-- Wire up auth.py when ready to implement multi-user support.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'creator',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS roles (
    name        TEXT PRIMARY KEY,
    description TEXT,
    permissions TEXT  -- JSON array of permission strings
);

INSERT OR IGNORE INTO roles (name, description, permissions) VALUES
    ('admin',   'Full access',        '["create_links","delete_links","deactivate_links","view_analytics","manage_users"]'),
    ('creator', 'Manage own links',   '["create_links","delete_links","deactivate_links","view_analytics"]'),
    ('viewer',  'View analytics only','["view_analytics"]');
"""


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        # Safe migrations — ignored if columns already exist
        for ddl in [
            "ALTER TABLE share_links ADD COLUMN flavor_enabled INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE share_links ADD COLUMN background TEXT",
            "ALTER TABLE share_links ADD COLUMN flavor_text TEXT",
            "ALTER TABLE share_links ADD COLUMN item_artist TEXT",
            "ALTER TABLE share_links ADD COLUMN needs_transcode INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE share_links ADD COLUMN duration_seconds INTEGER",
        ]:
            try:
                await db.execute(ddl)
            except Exception:
                pass
        await db.commit()


async def get_db():
    """FastAPI dependency — yields an open aiosqlite connection per request."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
