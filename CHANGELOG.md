# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Docker deployment support: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Admin search can be narrowed by media type (Movies, Episodes, Music, Music Videos) and by library, via a new `GET /api/admin/libraries` endpoint
- New share links default to a 7-day expiration, a 15-view cap, and a 5-unique-viewer cap, each with a "no limit" checkbox to disable it
- Jellyfin search failures are now logged instead of silently returning an empty result set
- `og:description`/`twitter:description`/`<meta name="description">` on share link previews, and a `max-image-preview:large` robots directive so Google will render the preview image
- Four independent deployment-wide config switches (`content_config.json`) for the visual flavor system — `glitch_enabled`, `background_enabled`, `logo_flash_enabled`, `flavor_text_enabled` — each defaulting to off so a fresh clone renders a plain watch page out of the box
- Basic per-IP rate limiting (`app/rate_limit.py`) on the public register and cover-art endpoints, configurable via `RATE_LIMIT_MAX_REQUESTS`/`RATE_LIMIT_WINDOW_SECONDS`
- In-app settings page in the admin portal (gear icon, top-right) for viewing/editing the same values that live in `.env` and `content_config.json` — the latter applies immediately, the former requires a restart and is marked with a `*` on any field that's been saved but isn't active yet

### Changed
- Project renamed from `web_share_app`/`dopelink` to **medurlsa** — the default `site_title`, the service/system-user name (`install.sh`, `SECURITY.md`, `Dockerfile`, `docker-entrypoint.sh`), and the `frontend/package.json`/`docker-compose.yml` service names all updated to match
- Link previews (Open Graph) show the site name as the title again, with the specific track/artist detail moved into the new description instead
- `og:type` changed from `video.other` to `website`, for better compatibility with link-preview crawlers (notably WhatsApp)
- Consolidated default values (site title, timing, fonts) to a single source per runtime, removing redundant hardcoded fallbacks that had spread across the backend and frontend
- Admin login and link-creation errors now show the actual server-provided message and distinguish an unreachable backend from a genuine authentication failure, instead of a generic "Invalid token"
- New share links now get a short, configurable-length random ID (`LINK_ID_LENGTH`, 8–16 chars, default 12) instead of a 36-character UUIDv4 — existing links are unaffected and keep resolving at their original length

### Fixed
- Race condition in the admin search box where a slow, stale response could overwrite a newer, more relevant one
- Docker: settings-page saves to `.env` were silently lost on `docker compose down`/`up`, since `env_file:` only injects variables at container creation and doesn't give the container a live view of the host file — `.env` is now bind-mounted like `data/`/`backgrounds/` already were. `content_config.json`'s (optional) mount had the same gap, plus was accidentally `:ro`, which would have blocked settings-page writes to it outright
- Docker: saving `.env` settings crashed the request (surfacing as a misleading "could not reach the server" in the UI) once `.env` was bind-mounted — `python-dotenv`'s `set_key()` writes via a temp-file-plus-rename swap, which fails with "Invalid cross-device link" against a single-file bind mount. Settings now write `.env` in place instead
- `content_config.json`'s bind mount is now uncommented by default. It was previously commented out because a missing host file would cause Docker to auto-create an empty *directory* at that path, crashing the app on startup (`os.path.exists()` treats a directory as "present" and then fails to `open()` it as a file). `content_config.py` now checks `os.path.isfile()` instead, so a missing file falls back to defaults exactly as intended, and `save_content_config()` raises a clear error instead of crashing if the settings page tries to write before a real file exists
- Docker: added a dedicated `./branding` bind mount for `logo_path`, separate from `./backgrounds` — the latter is scanned wholesale for the background picker and random background selection, so a logo living there would show up as a selectable/randomly-pickable background. `get_public_config()` also now excludes the logo's basename from `available_backgrounds` defensively, regardless of which directory it ends up in
