# Technical Reference

This document describes the architecture, tech stack, and design decisions behind Medurlsa.

---

## What the app does

The app is a media share link proxy for Jellyfin. It allows an administrator to generate unique, public-facing URLs that stream media from a private Jellyfin server directly in the browser. The Jellyfin server, its URL, and its API credentials are never exposed to the viewer.

Core behaviours:
- Share links are identified by a UUID and stored in a local database
- Each link can be configured with an expiration date, a maximum number of total views, and a maximum number of unique viewers
- Viewers are identified by a UUID stored in their browser's localStorage
- The app proxies the media stream from Jellyfin in real time — no buffering to disk
- Album/cover art is also proxied through the app
- An admin portal allows searching the Jellyfin library, creating links, and managing existing ones
- Public share pages support optional visual flavor features: animated backgrounds, a styled title banner with VHS glitch effects, floating flavor text, and a logo overlay

---

## Request flow

### Viewer loading a share link

```
Browser loads /stream/{uuid}
  → FastAPI injects OG meta tags into index.html, returns it
  → React app boots, reads UUID from URL
  → POST /api/links/{uuid}/register  (sends localStorage client ID)
      → server validates link (exists, active, not expired, not exhausted)
      → server checks client ID against link_clients table
      → if new client: checks max_clients cap, registers client
      → increments use_count, returns item info + flavor config
  → React renders player + flavor components
  → <video> or <audio> element sets src to /api/stream/{uuid}?client_id={id}
      → server re-validates link and confirms client is registered
      → server opens streaming connection to Jellyfin (/Videos/{id}/stream?static=true)
      → server pipes bytes in 64KB chunks to browser
      → browser Range requests for seeking are forwarded to Jellyfin unchanged
  → /api/image/{uuid} fetches and proxies cover art from Jellyfin
  → /api/backgrounds/{filename} serves background file from local directory
  → /api/public/config provides site title, flavor text pool, and timing config
```

### Admin creating a share link

```
Admin loads /admin
  → React app renders login form
  → Admin submits token → validated against ADMIN_TOKEN in .env
  → GET /api/admin/libraries fetches the server's top-level libraries once,
    for the library filter checklist (Jellyfin /Library/VirtualFolders)
  → Admin searches by title, optionally narrowed by media type (chips) and/or
    library (checklist) → GET /api/admin/search?q={query}&item_types=...&library_ids=...
      → server queries Jellyfin /Items?searchTerm=... (and /Artists for
        artist-name matches) once per selected library — Jellyfin's ParentId
        filter takes one value, not a list — merging and deduplicating results
      → returns list of streamable items (Movie, Episode, Audio, MusicVideo)
  → Admin selects item, configures link options, submits
  → POST /api/admin/links
      → server fetches item metadata from Jellyfin /Items?Ids={id}
      → generates UUID, stores link in SQLite
      → returns shareable URL: {PUBLIC_BASE_URL}/stream/{uuid}
```

---

## Tech stack

### Python 3.12

The backend language. Chosen for its ecosystem of async-friendly web libraries, broad availability on Linux distributions (including Alpine), and consistency with the sigillist project this app is developed alongside.

---

### FastAPI

The web framework. FastAPI sits above Uvicorn and handles:
- Route definition and URL parameter parsing
- Request body validation via Pydantic
- Dependency injection (the `get_db` database connection, `require_admin` auth check)
- Automatic OpenAPI schema generation (disabled in production)

FastAPI is built on Starlette, which provides the underlying ASGI primitives, static file serving, and streaming response support. It was chosen over Flask because it is natively async — critical for the streaming proxy, which must hold open a long-lived connection to Jellyfin while simultaneously forwarding data to the client. A synchronous framework would block a worker thread for the entire duration of a stream.

---

### Uvicorn

The ASGI server. Uvicorn is the process that actually listens on the network port, accepts TCP connections, parses HTTP, and hands requests to FastAPI via the ASGI interface. It implements the async event loop (via uvloop on supported platforms) that allows a single process to handle multiple concurrent streams without threading.

Uvicorn is not recommended as a primary static file server at scale because it routes all requests through Python rather than using OS-level sendfile calls. For this application this is acceptable because:
- Concurrent viewer count is low (personal use)
- Background files carry a 24-hour Cache-Control header — each client fetches each file once, then serves from browser cache
- The reverse proxy upstream (Cloudflare, Caddy, etc.) handles TLS termination and may also cache static assets
- The performance-critical path — the media stream proxy — is exactly what Uvicorn's async model is designed for

A single worker process is used (`--workers 1`) because SQLite does not safely support concurrent writes from multiple processes.

---

### httpx

The async HTTP client used to communicate with Jellyfin. httpx is used for:
- Searching the Jellyfin library (`/Items?searchTerm=...`)
- Fetching item metadata (`/Items?Ids=...`)
- Fetching image tags for cover art
- Opening and streaming media from Jellyfin to the client

The streaming proxy pattern is the critical use case. When a viewer requests `/api/stream/{uuid}`, the server opens a persistent streaming connection to Jellyfin using `client.send(request, stream=True)` and forwards chunks to the browser as they arrive via an async generator. The connection to Jellyfin stays open for as long as the client is watching. httpx's async streaming interface makes this straightforward without threads or subprocesses.

The `Range` header from the browser is forwarded unchanged to Jellyfin, enabling seeking. Jellyfin responds with `206 Partial Content` and the appropriate byte range, which is then forwarded to the browser.

---

### aiosqlite

An async wrapper around Python's built-in `sqlite3` module. It runs SQLite operations in a thread pool so they do not block the async event loop. Without this, a database read during a stream request could stall all other concurrent connections.

---

### SQLite

The database. Stores share links, per-link client access records, and the user/role scaffolding tables. SQLite was chosen because:
- No separate database process is required — it is a single file
- Memory footprint is negligible
- Write volume is extremely low (link creation, view registration)
- Concurrent reads are well-handled in WAL (Write-Ahead Logging) mode
- Backup is a file copy

WAL mode is enabled at startup (`PRAGMA journal_mode=WAL`) so that read queries (checking link validity on each stream request) do not block on the occasional write (registering a new viewer).

The database schema includes a `users` and `roles` table that is not yet connected to any routes. This scaffolding exists so that a future multi-user system with role-based permissions can be implemented by wiring up `app/auth.py` without changing the database structure or any route signatures.

---

### python-dotenv

Loads the `.env` file into environment variables at process startup. This keeps secrets (Jellyfin API key, admin token) out of the codebase and makes environment-specific configuration straightforward to manage on a deployed server.

---

### React 18

The frontend UI framework. The entire frontend is a single-page application (SPA) — React handles routing and rendering entirely in the browser after the initial HTML load. FastAPI serves the built static files and falls back to `index.html` for all non-API routes, allowing React Router to handle navigation.

React was chosen for consistency with the sigillist project and because the admin portal's interactive features (debounced search, background thumbnail grid, modal state management) are significantly cleaner to build with a component model than with vanilla JS.

---

### React Router

Handles client-side routing within the SPA. Two primary routes:
- `/stream/:uuid` — public watch page
- `/admin` — admin portal

All other paths fall through to `NotFoundPage`.

---

### Vite

The frontend build tool and development server. Vite compiles JSX, bundles JavaScript modules, processes CSS through PostCSS/Tailwind, and outputs optimised static files to `frontend/dist/`. It is only required at build time — the output is plain HTML, CSS, and JavaScript that requires no Node.js at runtime on the server.

In development mode, Vite runs a hot-reload server on port 5173 and proxies `/api` requests to the FastAPI backend, allowing frontend changes to be reflected instantly without rebuilding.

---

### Tailwind CSS

A utility-first CSS framework. Rather than writing custom CSS classes, styles are applied via predefined utility classes directly in JSX (`bg-gray-900`, `rounded-xl`, `text-sm`, etc.). Tailwind's build step scans the source files and outputs only the CSS classes actually used, keeping the production CSS bundle small.

Custom animations (`vhsGlitch`, `colorCycle`) and the synthwave color palette CSS custom properties are defined in `frontend/src/index.css` alongside the Tailwind directives, since they are too dynamic to express as utility classes.

---

### PostCSS / Autoprefixer

PostCSS is the CSS processing pipeline that Tailwind runs through. Autoprefixer is a PostCSS plugin that automatically adds vendor prefixes (`-webkit-`, `-moz-`, etc.) to CSS properties that require them for cross-browser compatibility. Both are build-time only — they produce no runtime overhead.

---

## Configuration files

### `.env`

Operational configuration. Contains secrets and environment-specific values that must not be committed to version control:

| Variable | Purpose |
|---|---|
| `JELLYFIN_URL` | Internal URL of the Jellyfin server |
| `JELLYFIN_API_KEY` | API key from a Jellyfin service account |
| `ADMIN_TOKEN` | Password for the admin portal |
| `PUBLIC_BASE_URL` | Public-facing URL of this app (used in generated share links) |
| `DB_PATH` | Path to the SQLite database file |
| `BACKGROUNDS_DIR` | Directory containing background image/video files |
| `LINK_ID_LENGTH` | Character length of newly generated share link IDs (8–16, default 12). Existing links are unaffected — this only governs newly created ones |
| `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS` | Per-IP request budget applied to the public register and cover-art endpoints, which are otherwise unauthenticated brute-force targets for guessing link IDs |

### `content_config.json`

Editorial and presentation configuration. Controls what viewers see and how visual effects behave. Not committed to version control (gitignored). Falls back to hardcoded defaults if absent.

| Key | Purpose |
|---|---|
| `site_title` | Text displayed in the title banner on the watch page |
| `logo_path` | Path to a logo image file for the LogoFlash overlay and favicon. Under Docker, point this at `./branding` (bind-mounted), not `./backgrounds` — `get_public_config()` (`app/routes/public_config.py`) excludes the logo's basename from `available_backgrounds` defensively, but a dedicated directory means there's no reason to rely on that exclusion in the first place |
| `glitch_enabled` | Deployment-wide switch for the title glitch/jitter/color-cycle + pearl border effects. Defaults to `false` so a fresh clone with no `content_config.json` renders a plain watch page. Not gated by the per-link `flavor_enabled` DB column — only the deployment-wide switch matters here |
| `background_enabled` | Deployment-wide switch for the fullscreen background. Independent of the other three switches; combined with the per-link `flavor_enabled` DB column (both must be true) |
| `logo_flash_enabled` | Deployment-wide switch for the logo overlay. Same combination rule as `background_enabled` |
| `flavor_text_enabled` | Deployment-wide switch for the floating flavor-text feature. Same combination rule as `background_enabled` |
| `flavor_texts` | Pool of strings that float across the screen during playback |
| `timing.glitch` | Interval range and duration for the VHS glitch effect on the title |
| `timing.color_cycle` | Interval range, duration, and step rate for synthwave color cycling |
| `timing.flavor_text` | Interval range and hold duration for floating flavor text |
| `timing.logo_flash` | Interval range and hold duration for the logo overlay |

---

## Admin settings page

`GET`/`PUT /api/admin/settings` (`app/routes/settings.py`), surfaced in the admin portal behind the gear icon, lets an admin view and edit a subset of `.env` and `content_config.json` without shell/file access. Both files remain the actual source of truth — this is a UI in front of them, not a separate settings store.

The two files behave differently once written:
- **`content_config.json` changes apply immediately.** `save_content_config()` writes the file and calls `reload_content_config()`, which mutates the existing `CONTENT_CONFIG` dict in place (clear + update, not reassignment) — every module that already did `from app.content_config import CONTENT_CONFIG` holds a reference to that same dict object, so the change is visible on the very next request, no restart needed.
- **`.env` changes require a restart.** Every `.env`-backed value is read once into a plain module-level constant in `app/config.py` at import time, and several other modules import those constants directly — writing a new value to the file doesn't change a constant some other module already imported. The settings endpoint writes via `python-dotenv`'s `set_key()` and reports `restart_required: true`, but can't make the change take effect itself.

To make "saved but not yet active" visible in the UI, `GET /api/admin/settings` also returns `env_pending`: a list of key names where the on-disk `.env` value differs from what's actually active in the running process (compared via `dotenv_values()`, which parses the file without touching `os.environ`). The frontend marks those fields with a `*`. This comparison never needs to expose either value for the two secret fields (`JELLYFIN_API_KEY`, `ADMIN_TOKEN`) — it only returns whether they differ, not what they are.

Secrets are masked in the GET response (a placeholder, not the real value) and skipped on write if the PUT echoes that same placeholder back unchanged — only a genuinely different submitted value (including an explicit empty string) overwrites one.

**Docker-specific caveats**:

- `ENV_PATH`/`_CONFIG_PATH` are computed relative to the app's own location (`/app/.env`, `/app/content_config.json` inside a container). `docker-compose.yml`'s `env_file: .env` only injects variables into the container's environment at creation time — it does not give the container a live view of the host file. Without an explicit bind mount for both files, a write from the settings page lands only on the container's own throwaway filesystem layer and is silently lost the next time the container is recreated (`docker compose down` + `up`), even though `env_pending` correctly showed it as saved right up until that point. `docker-compose.yml` mounts both files for exactly this reason.
- Writing `.env` uses a custom in-place writer (`_write_env_file()` in `app/routes/settings.py`), not `python-dotenv`'s `set_key()`. `set_key()` writes via a temp-file-plus-`os.replace()` swap — correct and crash-safe for a normal file, but it fails with `OSError: Invalid cross-device link` against a single-file bind mount, since the temp file (created in the same directory) and the bind-mounted target end up on different filesystems and a cross-device rename isn't possible.
- Docker auto-creates a missing bind-mount source as an empty **directory**, not a file. `content_config.py`'s `_load()` checks `os.path.isfile()`, not `os.path.exists()`, specifically so this auto-created directory is treated the same as a genuinely absent file (falls back to defaults) instead of crashing on `open()`. `save_content_config()` similarly checks this and raises a clear `RuntimeError` (surfaced as a proper error response, not a crash) if asked to write before a real file exists at that path.

---

## Database schema

### `share_links`

Primary table. One row per share link.

| Column | Type | Description |
|---|---|---|
| `uuid` | TEXT PK | The public-facing link identifier |
| `item_id` | TEXT | Jellyfin item ID |
| `item_type` | TEXT | Jellyfin item type (Movie, Episode, Audio, etc.) |
| `item_title` | TEXT | Display title |
| `created_at` | TEXT | ISO datetime, UTC |
| `expires_at` | TEXT | ISO datetime or NULL (no expiry) |
| `max_uses` | INTEGER | Total view cap or NULL (unlimited) |
| `max_clients` | INTEGER | Unique viewer cap or NULL (unlimited) |
| `use_count` | INTEGER | Running total of view events |
| `is_active` | INTEGER | 1 = active, 0 = deactivated by admin |
| `notes` | TEXT | Admin notes |
| `flavor_enabled` | INTEGER | 1 = show visual flavor features, 0 = vanilla page |
| `background` | TEXT | Specific background filename or NULL (random) |
| `flavor_text` | TEXT | Link-specific flavor text or NULL (random from pool) |

### `link_clients`

One row per unique client per link. Tracks viewer identity and access history.

| Column | Type | Description |
|---|---|---|
| `link_uuid` | TEXT FK | References `share_links.uuid`, CASCADE DELETE |
| `client_id` | TEXT | Browser-generated UUID from localStorage |
| `ip_address` | TEXT | IP at time of first registration (metadata only, not used for identity) |
| `user_agent` | TEXT | User-Agent string at registration (metadata only) |
| `first_seen` | TEXT | ISO datetime of first access |
| `last_seen` | TEXT | ISO datetime of most recent access |
| `access_count` | INTEGER | Number of times this client has loaded the watch page |

### `users` / `roles` (scaffolding)

Not connected to any routes. Exists to support a future multi-user system with role-based access control without requiring a schema migration. The `roles` table is pre-populated with `admin`, `creator`, and `viewer` roles, each with a JSON array of permission strings. When implemented, `app/auth.py` is the only file that needs to change — route signatures remain identical.

---

## Client identification

Viewers are identified by a UUID generated in the browser on first visit and stored in `localStorage` under the key `share_client_id`. This ID persists across page reloads and browser restarts but is cleared if the user wipes browser storage or uses a private browsing session.

This approach was chosen over IP-based fingerprinting because:
- Multiple users behind the same NAT share one public IP
- IP addresses change frequently on mobile connections
- The localStorage UUID correctly identifies a browser profile, not a network location

The tradeoff is that clearing localStorage or using private browsing generates a new client ID, which consumes an additional slot against `max_clients`. This is considered a known and acceptable limitation rather than a security bypass — it results in faster exhaustion of the client limit, not circumvention of it.

The client ID is stored server-side in `link_clients`. It is not a secret — it is only used for access tracking, not authentication. The security boundary is the link ID itself: a CSPRNG-generated (`secrets.token_urlsafe`), URL-safe random string, `LINK_ID_LENGTH` characters long (8–16, default 12) — see `app/routes/admin.py`. Older links generated before this change remain full 36-character UUIDv4 strings; both formats resolve identically since `uuid` is a plain `TEXT` primary key with no length constraint. Because this ID is the sole access control, the public endpoints that don't otherwise require a registered client (`/api/links/{uuid}/register`, `/api/image/{uuid}`) are rate-limited per IP (`RATE_LIMIT_MAX_REQUESTS`/`RATE_LIMIT_WINDOW_SECONDS`, see `app/rate_limit.py`) to slow brute-force guessing.

---

## Streaming proxy

The media stream endpoint (`GET /api/stream/{uuid}?client_id={id}`) operates as a transparent byte-forwarding proxy:

1. Validates the link (exists, active, not expired)
2. Confirms the client ID is registered in `link_clients`
3. Constructs the Jellyfin stream URL server-side (`/Videos/{id}/stream?static=true&api_key={key}`)
4. Forwards any `Range` header from the browser to Jellyfin
5. Opens a persistent streaming connection to Jellyfin via httpx
6. Yields response bytes in 64KB chunks to the browser as they arrive
7. Forwards `Content-Type`, `Content-Length`, `Content-Range`, and `Accept-Ranges` headers

The `Range` header forwarding is what enables seeking. When the viewer drags the playback position, the browser makes a new request with a `Range: bytes=X-Y` header. The server forwards this to Jellyfin, which responds with `206 Partial Content` and the requested byte range. This cycle happens entirely in memory with no disk I/O.

Use count is incremented at watch page registration, not per range request — a full viewing session counts as one use regardless of how many times the viewer seeks.

---

## Open Graph / link previews

When a social platform or messaging app (Discord, iMessage, Slack, Telegram) scrapes a `/stream/{uuid}` URL for a link preview, it makes a plain HTTP GET request and reads the HTML `<head>`. Because the app is a React SPA, the normal response is a mostly-empty `index.html` — scrapers see nothing useful.

To fix this, FastAPI intercepts requests to `/stream/{uuid}` paths, reads the built `index.html`, injects Open Graph meta tags (`og:title`, `og:image`, `og:type`, `og:url`, `twitter:card`, `twitter:image`) before `</head>`, and returns the modified HTML. Regular browsers load this same HTML and the React app boots normally — the extra meta tags are invisible to the user but visible to scrapers.

The `og:image` points to `/api/image/{uuid}`, which proxies the cover art from Jellyfin. Scrapers fetch this URL server-side, so it works regardless of whether the Jellyfin server is publicly accessible.
