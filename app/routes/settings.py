"""
Admin settings — view and update the same values that live in .env and
content_config.json, without needing shell/file access.

GET /api/admin/settings   Current values from both files (secrets masked)
PUT /api/admin/settings   Write updates back to both files

Reconciliation model: these two files stay the actual source of truth. This
route reads and writes them directly — there's no separate settings store to
keep in sync.

- content_config.json changes take effect immediately: save_content_config()
  (app/content_config.py) writes the file and reloads CONTENT_CONFIG in
  place, so every module that already imported it sees the update on its
  next request.
- .env changes do NOT take effect until the process restarts. Every
  .env-backed value (JELLYFIN_URL, ADMIN_TOKEN, LINK_ID_LENGTH, etc.) is read
  once into a plain module-level constant in app/config.py at import time,
  and several other modules import those constants directly — writing a new
  value to the file on disk doesn't change a constant some other module
  already imported. This is the same reason a stale JELLYFIN_URL kept being
  used during local dev until uvicorn was restarted.
"""

import os

from dotenv import dotenv_values
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_admin
from app.config import (
    ADMIN_TOKEN,
    BACKGROUNDS_DIR,
    DB_PATH,
    ENV_PATH,
    JELLYFIN_API_KEY,
    JELLYFIN_URL,
    LINK_ID_LENGTH,
    PUBLIC_BASE_URL,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from app.content_config import CONTENT_CONFIG, save_content_config
from app.models import SettingsUpdateRequest

router = APIRouter()

# Shown in place of a real secret in GET responses. A PUT that echoes this
# back unchanged means "leave it as-is" — only a genuinely different value
# (including an explicit empty string) overwrites it.
_MASKED = "•" * 8


def _quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _write_env_file(path: str, updates: dict) -> None:
    """
    Update or add key=value lines in an existing .env file, writing directly
    in place rather than via python-dotenv's set_key(). set_key() writes a
    temp file in the same directory and atomically os.replace()s it over the
    target — the standard safe way to write a config file, but it breaks
    when .env is a single-file Docker bind mount (docker-compose.yml): the
    temp file lives on the container's own filesystem while the bind-mounted
    target is a separate mount point, so the rename becomes a cross-device
    rename, which Linux refuses (OSError: Invalid cross-device link). This
    writes into the existing file/inode directly instead, which bind mounts
    handle fine — at the cost of the crash-safety atomic replace would give,
    an acceptable trade for a low-frequency, user-initiated write.
    """
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={_quote_env_value(str(remaining.pop(key)))}\n"

    for key, value in remaining.items():
        lines.append(f"{key}={_quote_env_value(str(value))}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _pending_env_keys() -> list[str]:
    """
    Compare the .env file on disk against the values actually active in this
    running process (the constants app/config.py already imported at
    startup). Any key that differs has been saved but won't take effect
    until a restart re-runs load_dotenv() picks it up — see this module's
    docstring. Only ever returns key names, never values, so this is safe to
    run over the secret fields too.
    """
    if not os.path.exists(ENV_PATH):
        return []
    on_disk = dotenv_values(ENV_PATH)
    # JELLYFIN_URL/PUBLIC_BASE_URL get .rstrip("/") applied when loaded
    # (app/config.py) — apply the same normalization before comparing, or an
    # unchanged trailing slash in the file would look like a pending change.
    active = {
        "JELLYFIN_URL":              JELLYFIN_URL,
        "JELLYFIN_API_KEY":          JELLYFIN_API_KEY,
        "ADMIN_TOKEN":               ADMIN_TOKEN,
        "PUBLIC_BASE_URL":           PUBLIC_BASE_URL,
        "DB_PATH":                   DB_PATH,
        "BACKGROUNDS_DIR":           BACKGROUNDS_DIR,
        "LINK_ID_LENGTH":            str(LINK_ID_LENGTH),
        "RATE_LIMIT_MAX_REQUESTS":   str(RATE_LIMIT_MAX_REQUESTS),
        "RATE_LIMIT_WINDOW_SECONDS": str(RATE_LIMIT_WINDOW_SECONDS),
    }
    normalize = {"JELLYFIN_URL", "PUBLIC_BASE_URL"}

    pending = []
    for key, active_value in active.items():
        disk_value = on_disk.get(key)
        if disk_value is None:
            continue  # not set in the file at all — using the code default, nothing pending
        if key in normalize:
            disk_value = disk_value.rstrip("/")
        if disk_value != active_value:
            pending.append(key)
    return pending


@router.get("/admin/settings")
async def get_settings(_: str = Depends(require_admin)):
    return {
        "env": {
            "JELLYFIN_URL":              JELLYFIN_URL,
            "JELLYFIN_API_KEY":          _MASKED if JELLYFIN_API_KEY else "",
            "ADMIN_TOKEN":               _MASKED if ADMIN_TOKEN else "",
            "PUBLIC_BASE_URL":           PUBLIC_BASE_URL,
            "DB_PATH":                   DB_PATH,
            "BACKGROUNDS_DIR":           BACKGROUNDS_DIR,
            "LINK_ID_LENGTH":            LINK_ID_LENGTH,
            "RATE_LIMIT_MAX_REQUESTS":   RATE_LIMIT_MAX_REQUESTS,
            "RATE_LIMIT_WINDOW_SECONDS": RATE_LIMIT_WINDOW_SECONDS,
        },
        "env_pending": _pending_env_keys(),
        "content_config": {
            "site_title":          CONTENT_CONFIG["site_title"],
            "logo_path":           CONTENT_CONFIG["logo_path"],
            "glitch_enabled":      CONTENT_CONFIG["glitch_enabled"],
            "background_enabled":  CONTENT_CONFIG["background_enabled"],
            "logo_flash_enabled":  CONTENT_CONFIG["logo_flash_enabled"],
            "flavor_text_enabled": CONTENT_CONFIG["flavor_text_enabled"],
            "flavor_texts":        CONTENT_CONFIG["flavor_texts"],
        },
    }


@router.put("/admin/settings")
async def update_settings(
    body: SettingsUpdateRequest,
    _: str = Depends(require_admin),
):
    restart_required = False

    if body.env is not None:
        updates = body.env.model_dump(exclude_unset=True)
        for secret_key in ("JELLYFIN_API_KEY", "ADMIN_TOKEN"):
            if updates.get(secret_key) == _MASKED:
                del updates[secret_key]  # placeholder echoed back — leave unchanged
        if updates:
            _write_env_file(ENV_PATH, updates)
            restart_required = True

    content_config_updated = False
    if body.content_config is not None:
        updates = body.content_config.model_dump(exclude_unset=True)
        if updates:
            try:
                save_content_config(updates)
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc))
            content_config_updated = True

    return {
        "restart_required":       restart_required,
        "content_config_updated": content_config_updated,
    }
