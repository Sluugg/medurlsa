import html
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import admin, stream, watch
from app.routes import public_config as public_config_router

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
_INDEX_HTML   = os.path.join(FRONTEND_DIST, "index.html")

_FALLBACK_FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="3" fill="#0a0514"/>'
    '<text x="16" y="23" font-size="18" text-anchor="middle" fill="#bf5fff">▶</text>'
    '</svg>'
)

_STREAM_UUID_RE = re.compile(r"^stream/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

if os.getenv("DEV_MODE"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:80", "http://localhost"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(watch.router,               prefix="/api")
app.include_router(stream.router,              prefix="/api")
app.include_router(admin.router,               prefix="/api")
app.include_router(public_config_router.router, prefix="/api")

# ── Favicon ───────────────────────────────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from app.content_config import CONTENT_CONFIG
    import mimetypes
    logo_path = CONTENT_CONFIG.get("logo_path")
    if logo_path and os.path.isfile(str(logo_path)):
        mime, _ = mimetypes.guess_type(str(logo_path))
        return FileResponse(str(logo_path), media_type=mime or "image/png")
    return Response(content=_FALLBACK_FAVICON.encode(), media_type="image/svg+xml")

# ── Serve built React frontend ────────────────────────────────────────────────
if os.path.isdir(FRONTEND_DIST):
    _assets = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    _fonts = os.path.join(FRONTEND_DIST, "fonts")
    if os.path.isdir(_fonts):
        app.mount("/fonts", StaticFiles(directory=_fonts), name="fonts")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Inject OG meta tags for share link pages so social previews work
        if _STREAM_UUID_RE.match(full_path) and os.path.isfile(_INDEX_HTML):
            from app.content_config import CONTENT_CONFIG
            from app.config import PUBLIC_BASE_URL

            uuid       = full_path.split("/", 1)[1]
            site_title = html.escape(CONTENT_CONFIG.get("site_title", "dopelink"))
            og_image   = html.escape(f"{PUBLIC_BASE_URL}/api/image/{uuid}")
            og_url     = html.escape(f"{PUBLIC_BASE_URL}/stream/{uuid}")

            with open(_INDEX_HTML, "r", encoding="utf-8") as f:
                raw_html = f.read()

            og = (
                f'<meta property="og:type"        content="video.other" />\n'
                f'<meta property="og:site_name"   content="{site_title}" />\n'
                f'<meta property="og:title"       content="{site_title}" />\n'
                f'<meta property="og:image"       content="{og_image}" />\n'
                f'<meta property="og:url"         content="{og_url}" />\n'
                f'<meta name="twitter:card"       content="summary_large_image" />\n'
                f'<meta name="twitter:title"      content="{site_title}" />\n'
                f'<meta name="twitter:image"      content="{og_image}" />\n'
            )
            raw_html = raw_html.replace("</head>", og + "</head>", 1)
            return HTMLResponse(content=raw_html)

        return FileResponse(_INDEX_HTML)
