"""
Public configuration and static asset endpoints.

GET /api/public/config          Returns site config consumed by the frontend
GET /api/backgrounds/{filename} Serves background images/videos from BACKGROUNDS_DIR
GET /api/logo                   Serves the configured logo image
"""

import mimetypes
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import BACKGROUNDS_DIR
from app.content_config import CONTENT_CONFIG

router = APIRouter()

_VIDEO_EXTS   = {".webm", ".mp4", ".mov", ".avi"}
_IMAGE_EXTS   = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}
_ALLOWED_EXTS = _VIDEO_EXTS | _IMAGE_EXTS


@router.get("/public/config")
async def get_public_config():
    """Return all config the watch page needs: site identity, flavor texts, timing, backgrounds."""
    available_backgrounds: list[str] = []
    if os.path.isdir(BACKGROUNDS_DIR):
        for fname in sorted(os.listdir(BACKGROUNDS_DIR)):
            if os.path.splitext(fname)[1].lower() in _ALLOWED_EXTS:
                available_backgrounds.append(fname)

    logo_path = CONTENT_CONFIG.get("logo_path")
    has_logo  = bool(logo_path and os.path.isfile(str(logo_path)))

    return {
        "site_title":            CONTENT_CONFIG.get("site_title", "dopelink"),
        "has_logo":              has_logo,
        "flavor_texts":          CONTENT_CONFIG.get("flavor_texts", []),
        "available_backgrounds": available_backgrounds,
        "timing":                CONTENT_CONFIG.get("timing", {}),
        "fonts":                 CONTENT_CONFIG.get("fonts", {}),
    }


@router.get("/backgrounds/{filename}")
async def serve_background(filename: str):
    """Serve a background file with 24-hour caching. Guards against path traversal."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="File type not allowed.")

    candidate  = os.path.join(BACKGROUNDS_DIR, filename)
    real_path  = os.path.realpath(candidate)
    real_dir   = os.path.realpath(BACKGROUNDS_DIR)

    # Ensure the resolved path is actually inside BACKGROUNDS_DIR
    if not real_path.startswith(real_dir + os.sep):
        raise HTTPException(status_code=400, detail="Invalid path.")

    if not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="Background not found.")

    mime, _ = mimetypes.guess_type(filename)
    return FileResponse(
        real_path,
        media_type=mime or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/logo")
async def serve_logo():
    """Serve the configured logo image."""
    logo_path = CONTENT_CONFIG.get("logo_path")
    if not logo_path or not os.path.isfile(str(logo_path)):
        raise HTTPException(status_code=404, detail="Logo not configured.")
    mime, _ = mimetypes.guess_type(str(logo_path))
    return FileResponse(str(logo_path), media_type=mime or "image/png")
