# web_share_app

A lightweight web app for generating public share links to media in a Jellyfin library. Share links stream media directly in the browser without exposing your Jellyfin API key or session credentials.

## What it does

- Admin portal (`/admin`) lets you search your Jellyfin library and generate shareable links
- Search can be narrowed by media type (Movies, Episodes, Music, Music Videos) and by library, for large libraries
- Each link gets a unique UUID — the public URL looks like `https://yourdomain.com/stream/abc123`
- The app proxies the media stream from Jellyfin server-side, so the API key is never exposed to viewers
- Links can be configured with an expiration date, a max number of total views, and a max number of unique viewers
- Viewers are tracked by a browser-generated ID (stored in localStorage) — no accounts or logins required for viewers
- Expired or exhausted links show a clear message rather than a generic error

## Requirements

- A Jellyfin server with a dedicated service account API key
- Either **Docker**, or **Python 3.11+ and Node.js 18+** for a native install — you don't need both

## System dependencies (native install only)

Skip this section if you're using Docker. Install Python 3.11+ and Node.js 18+ before running `start.sh` or `install.sh`.

### Debian / Ubuntu

```bash
apt update && apt install -y python3 python3-pip nodejs npm
```

### Alpine Linux

Build tools are needed to compile Python packages with C extensions (can be removed after):

```bash
apk add python3 py3-pip nodejs npm gcc musl-dev libffi-dev python3-dev
```

Once `start.sh` has finished installing Python packages, you can remove the build tools to keep the container trim:

```bash
apk del gcc musl-dev libffi-dev python3-dev
```

---

## Deployment

### 1. Clone and configure (both options)

```bash
git clone https://your-gitea/username/web_share_app.git
cd web_share_app
cp .env.example .env
```

Edit `.env` and fill in your values:

```
JELLYFIN_URL       — URL of your Jellyfin server (e.g. http://192.168.1.10:8096)
JELLYFIN_API_KEY   — API key from a Jellyfin service account (Dashboard → API Keys)
ADMIN_TOKEN        — Password for the /admin portal, choose something strong
PUBLIC_BASE_URL    — The public URL of this app (used when generating share links)
DB_PATH            — Path to the SQLite database file (default: data/links.db)
```

`DB_PATH` and `BACKGROUNDS_DIR` are only meaningful for a native install — the Docker Compose setup overrides both to fixed in-container paths and maps them to host directories via volumes instead (see below).

### 2a. Docker

```bash
mkdir -p data backgrounds
chown -R 1000:1000 data backgrounds
docker compose up -d --build
```

The `chown` step matters: the container runs as a non-root user pinned to UID/GID 1000, and Docker bind mounts use the *host* directory's ownership as-is — skip it and the app won't be able to write the SQLite database.

This builds the image (frontend assets are built inside a throwaway Node stage, not on your host), starts the container listening on `8000` inside, and maps it to `8000` on the host — edit the `ports:` line in `docker-compose.yml` if you want a different host port, or put a reverse proxy in front for TLS/port 80/443. `./data` and `./backgrounds` are bind-mounted so links and background files persist across rebuilds. A single worker is used inside the container for the same reason as the native install (see below).

To use a custom `content_config.json` (site title, logo, flavor text, timing), copy `content_config.example.json` to `content_config.json` first, then uncomment its volume line in `docker-compose.yml` — Docker will mount an empty directory instead of a file if the source doesn't exist yet, which breaks config loading.

### 2b. Native install

For a quick foreground run (useful for testing):

```bash
chmod +x start.sh
./start.sh
```

This installs dependencies, builds the frontend, and starts the server on `0.0.0.0:80` in the foreground.

For a persistent background service (systemd on Debian/Ubuntu, OpenRC on Alpine), run `install.sh` as root instead — it creates a dedicated `webshare` service user, installs and enables the service, and scaffolds `.env` for you if it doesn't already exist:

```bash
sudo ./install.sh
```

The `install.sh` service runs on **port 8000**, not 80 — this lets it run as the unprivileged `webshare` user without needing root capabilities. Put a reverse proxy (nginx, Caddy) in front to expose it on 80/443. `start.sh`, by contrast, binds port 80 directly for a quick foreground run, which does need `sudo` (or running as root) on Linux.

### 3. Access

- Admin portal: `http://your-server/admin` (`start.sh`) or `http://your-server:8000/admin` (`install.sh` / Docker, unless you've put a reverse proxy in front mapping it to 80/443)
- Share links: `http://your-server/stream/<uuid>` (generated from the admin portal)

## Development mode

Run backend and frontend separately for hot reload:

```bash
# Terminal 1 — backend (port 80 needs root; frontend/vite.config.js proxies /api there)
sudo uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Terminal 2 — frontend
cd frontend && npm run dev   # serves on http://localhost:5173
```

`DEV_MODE=true` additionally enables CORS for `localhost:5173`/`:80` in `app/main.py`, which is only needed if you're calling the API directly instead of through Vite's `/api` proxy.

## Notes

- The SQLite database is created automatically at first run in the `data/` directory (or `/app/data` inside the Docker container, bind-mounted to `./data` on the host)
- The `data/` and `backgrounds/` directories, `.env`, and `content_config.json` are all gitignored — back them up separately
- Only one server process is supported (SQLite limitation) — sufficient for personal/small use. This also means the app can't be horizontally scaled by running multiple container replicas against the same database file.
