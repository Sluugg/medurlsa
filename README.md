# medurlsa

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
git clone https://your-gitea/username/medurlsa.git
cd medurlsa
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
docker compose up -d --build
```

No manual setup needed for `./data`/`./backgrounds` — the container runs as a non-root user (UID/GID 1000), and its entrypoint fixes ownership on those mounted directories at every start before dropping privileges, so a fresh (or Docker-auto-created, root-owned) directory just works.

This builds the image (frontend assets are built inside a throwaway Node stage, not on your host), starts the container listening on `8000` inside, and maps it to `8000` on the host — edit the `ports:` line in `docker-compose.yml` if you want a different host port, or put a reverse proxy in front for TLS/port 80/443. `./data` and `./backgrounds` are bind-mounted so links and background files persist across rebuilds. A single worker is used inside the container for the same reason as the native install (see below).

`.env` is bind-mounted too (not just referenced via `env_file:`), so changes made through the admin settings page persist across `docker compose down`/`up` — `env_file:` alone only injects variables when the container is created, it doesn't give the container a live view of the file, so without the mount a settings-page save would silently vanish the next time the container is recreated.

`content_config.json` (site title, logo, flavor text, timing) is bind-mounted too, and works fine with no setup — if it doesn't exist on the host yet, the app just uses its built-in defaults, same as a native install. If you want to *save* content_config changes through the admin settings page, though, create a real file first: `cp content_config.example.json content_config.json`. Without that, a save would fail with a clear error rather than silently vanishing — Docker auto-creates a missing bind-mount source as an empty directory, and there's no file there yet for the settings page to write into.

`logo_path` needs to point somewhere the container can actually see — use `./branding` (bind-mounted, created automatically), not the bare project root, which isn't visible to the container at all. Deliberately a separate directory from `./backgrounds`: that one is scanned wholesale for the background picker and random background selection, so a logo dropped in there would show up as a selectable (and randomly pickable) background too. Set `logo_path` to e.g. `branding/logo.png`.

### 2b. Native install

For a quick foreground run (useful for testing):

```bash
chmod +x start.sh
./start.sh
```

This installs dependencies, builds the frontend, and starts the server on `0.0.0.0:80` in the foreground.

For a persistent background service (systemd on Debian/Ubuntu, OpenRC on Alpine), run `install.sh` as root instead — it creates a dedicated `medurlsa` service user, installs and enables the service, and scaffolds `.env` for you if it doesn't already exist:

```bash
sudo ./install.sh
```

The `install.sh` service runs on **port 8000**, not 80 — this lets it run as the unprivileged `medurlsa` user without needing root capabilities. Put a reverse proxy (nginx, Caddy) in front to expose it on 80/443. `start.sh`, by contrast, binds port 80 directly for a quick foreground run, which does need `sudo` (or running as root) on Linux.

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

## Support

If this project is useful to you, consider supporting its development:

- ☕ [Ko-fi](https://ko-fi.com/sluugg)
- Ethereum: `0x6613e260DE9a165B287C3B77f191c2A83B25B749`

## License

MIT — see [LICENSE](LICENSE).
