import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.database import init_db
from app.routes import admin, stream, watch

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

# CORS: only needed during development (Vite on :5173 <-> FastAPI on :8000).
# In production everything is served from the same origin.
if os.getenv("DEV_MODE"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:80", "http://localhost"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(watch.router,  prefix="/api")
app.include_router(stream.router, prefix="/api")
app.include_router(admin.router,  prefix="/api")

# ── Serve built React frontend ────────────────────────────────────────────────
if os.path.isdir(FRONTEND_DIST):
    _assets = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
