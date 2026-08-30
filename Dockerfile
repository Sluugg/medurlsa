# ── Frontend build stage ─────────────────────────────────────────────────────
# Node is only needed to produce the static bundle; it never ships in the
# runtime image.
FROM node:26-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

# Dedicated non-root user — mirrors install.sh's native systemd/OpenRC setup.
# UID/GID are pinned (rather than left to `--system`'s unpredictable
# allocation) so the entrypoint's chown below targets a known, stable value.
# docker-entrypoint.py drops from root to this user at container start using
# plain os.setuid()/os.setgid() — no gosu/apt-get needed, and no extra
# network fetch at build time.
RUN groupadd --gid 1000 medurlsa \
    && useradd --uid 1000 --gid medurlsa --no-create-home --shell /usr/sbin/nologin medurlsa

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY assets/ ./assets/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# data/ and backgrounds/ are expected to be mounted as volumes (see
# docker-compose.yml) — created here so the app has somewhere to write before
# any volume is attached. If a bind mount later covers these with a
# differently-owned host directory, the entrypoint re-chowns at every start.
RUN mkdir -p /app/data /app/backgrounds /app/branding && chown -R medurlsa:medurlsa /app

COPY docker-entrypoint.py /usr/local/bin/docker-entrypoint.py
RUN chmod +x /usr/local/bin/docker-entrypoint.py

# Unprivileged port — map 80/443 to this from outside the container (a
# docker-compose port mapping or an external reverse proxy), rather than
# trying to bind a privileged port as root inside the container.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/public/config', timeout=2)" || exit 1

# Container starts as root (only to let the entrypoint fix volume ownership)
# and immediately drops to medurlsa before the app itself ever runs.
ENTRYPOINT ["python3", "/usr/local/bin/docker-entrypoint.py"]

# Single worker: SQLite does not safely support concurrent writes from
# multiple processes (see start.sh / install.sh for the same constraint).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
