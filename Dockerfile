# ── Frontend build stage ─────────────────────────────────────────────────────
# Node is only needed to produce the static bundle; it never ships in the
# runtime image.
FROM node:20-alpine AS frontend-build
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
# allocation) so the host-side ./data and ./backgrounds directories can be
# chowned to a known value before the bind mounts are attached — see README.
RUN groupadd --gid 1000 webshare \
    && useradd --uid 1000 --gid webshare --no-create-home --shell /usr/sbin/nologin webshare

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# data/ and backgrounds/ are expected to be mounted as volumes (see
# docker-compose.yml) — created here so the app has somewhere to write before
# any volume is attached, and so ownership is correct either way.
RUN mkdir -p /app/data /app/backgrounds && chown -R webshare:webshare /app

USER webshare

# Unprivileged port — map 80/443 to this from outside the container (a
# docker-compose port mapping or an external reverse proxy), rather than
# trying to bind a privileged port as root inside the container.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/public/config', timeout=2)" || exit 1

# Single worker: SQLite does not safely support concurrent writes from
# multiple processes (see start.sh / install.sh for the same constraint).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
