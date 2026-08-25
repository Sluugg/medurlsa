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

### Changed
- Link previews (Open Graph) now show "[artist] - [title]" instead of the generic site name
- `og:type` changed from `video.other` to `website`, for better compatibility with link-preview crawlers (notably WhatsApp)
- Consolidated default values (site title, timing, fonts) to a single source per runtime, removing redundant hardcoded fallbacks that had spread across the backend and frontend
- Admin login and link-creation errors now show the actual server-provided message and distinguish an unreachable backend from a genuine authentication failure, instead of a generic "Invalid token"

### Fixed
- Race condition in the admin search box where a slow, stale response could overwrite a newer, more relevant one
