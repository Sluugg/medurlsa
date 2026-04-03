# web_share_app

A lightweight web app for generating public share links to media in a Jellyfin library. Share links stream media directly in the browser without exposing your Jellyfin API key or session credentials.

## What it does

- Admin portal (`/admin`) lets you search your Jellyfin library and generate shareable links
- Each link gets a unique UUID — the public URL looks like `https://yourdomain.com/watch/abc123`
- The app proxies the media stream from Jellyfin server-side, so the API key is never exposed to viewers
- Links can be configured with an expiration date, a max number of total views, and a max number of unique viewers
- Viewers are tracked by a browser-generated ID (stored in localStorage) — no accounts or logins required for viewers
- Expired or exhausted links show a clear message rather than a generic error

## Requirements

- Python 3.11+
- Node.js 18+
- A Jellyfin server with a dedicated service account API key

## System dependencies

Install Python 3.11+ and Node.js 18+ before running `start.sh`.

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

### 1. Clone and configure

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

### 2. Start

```bash
chmod +x start.sh
./start.sh
```

This installs dependencies, builds the frontend, and starts the server on `0.0.0.0:80`.

> **Note:** Binding to port 80 requires root on Linux. If running as a non-root user, either use `sudo` or place a reverse proxy (nginx) in front and run the app on an unprivileged port.

### 3. Access

- Admin portal: `http://your-server/admin`
- Share links: `http://your-server/watch/<uuid>` (generated from the admin portal)

## Development mode

Run backend and frontend separately for hot reload:

```bash
# Terminal 1 — backend
DEV_MODE=true uvicorn app.main:app --reload --host 0.0.0.0 --port 80

# Terminal 2 — frontend
cd frontend && npm run dev   # serves on http://localhost:5173
```

## Notes

- The SQLite database is created automatically at first run in the `data/` directory
- The `data/` directory and `.env` are gitignored — back them up separately
- Only one server process is supported (SQLite limitation) — sufficient for personal/small use
