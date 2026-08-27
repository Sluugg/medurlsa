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

from dotenv import set_key
from fastapi import APIRouter, Depends

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
        "content_config": {
            "site_title":           CONTENT_CONFIG["site_title"],
            "logo_path":            CONTENT_CONFIG["logo_path"],
            "animations_enabled":   CONTENT_CONFIG["animations_enabled"],
            "flavor_texts_enabled": CONTENT_CONFIG["flavor_texts_enabled"],
            "flavor_texts":         CONTENT_CONFIG["flavor_texts"],
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
            if not os.path.exists(ENV_PATH):
                open(ENV_PATH, "a").close()
            for key, value in updates.items():
                set_key(ENV_PATH, key, str(value))
            restart_required = True

    content_config_updated = False
    if body.content_config is not None:
        updates = body.content_config.model_dump(exclude_unset=True)
        if updates:
            save_content_config(updates)
            content_config_updated = True

    return {
        "restart_required":       restart_required,
        "content_config_updated": content_config_updated,
    }
