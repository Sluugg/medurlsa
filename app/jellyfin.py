import asyncio
import httpx
from app.config import JELLYFIN_URL, JELLYFIN_API_KEY

# Item types that can be directly streamed
STREAMABLE_TYPES = "Movie,Episode,Audio,MusicVideo"

# Codecs that all modern browsers can decode natively without transcoding
_BROWSER_AUDIO_CODECS = {"aac", "mp3", "opus", "vorbis", "flac"}


def _check_needs_transcode(item: dict) -> bool:
    """Return True if the item's audio codec is not natively supported by browsers."""
    for stream in item.get("MediaStreams", []):
        if stream.get("Type") == "Audio":
            codec = (stream.get("Codec") or "").lower()
            return codec not in _BROWSER_AUDIO_CODECS
    return False


def _parse_item(item: dict) -> dict:
    ticks     = item.get("RunTimeTicks")
    artists   = item.get("Artists", [])
    item_type = item.get("Type", "Unknown")
    return {
        "id":               item["Id"],
        "title":            item.get("Name", "Unknown"),
        "type":             item_type,
        "year":             item.get("ProductionYear"),
        "duration_seconds": int(ticks / 10_000_000) if ticks else None,
        "artist":           ", ".join(artists) if artists else None,
        # Only populated when MediaStreams is included in the response (get_item, not search)
        "needs_transcode":  _check_needs_transcode(item) if item_type == "Audio" else False,
    }


async def _search_by_title(query: str, client: httpx.AsyncClient, limit: int) -> list[dict]:
    r = await client.get(f"{JELLYFIN_URL}/Items", params={
        "searchTerm":       query,
        "Recursive":        "true",
        "IncludeItemTypes": STREAMABLE_TYPES,
        "Limit":            limit,
        "Fields":           "RunTimeTicks,ProductionYear,Artists",
        "api_key":          JELLYFIN_API_KEY,
    }, timeout=10.0)
    r.raise_for_status()
    return [_parse_item(i) for i in r.json().get("Items", [])]


async def _search_by_artist(query: str, client: httpx.AsyncClient, limit: int) -> list[dict]:
    # Step 1: find artist IDs matching the query
    r = await client.get(f"{JELLYFIN_URL}/Artists", params={
        "searchTerm": query,
        "Limit":      10,
        "api_key":    JELLYFIN_API_KEY,
    }, timeout=10.0)
    r.raise_for_status()
    artist_ids = [a["Id"] for a in r.json().get("Items", [])]
    if not artist_ids:
        return []

    # Step 2: fetch streamable items by those artist IDs
    r = await client.get(f"{JELLYFIN_URL}/Items", params={
        "ArtistIds":        ",".join(artist_ids),
        "Recursive":        "true",
        "IncludeItemTypes": "Audio,MusicVideo",
        "Limit":            limit,
        "Fields":           "RunTimeTicks,ProductionYear,Artists",
        "api_key":          JELLYFIN_API_KEY,
    }, timeout=10.0)
    r.raise_for_status()
    return [_parse_item(i) for i in r.json().get("Items", [])]


async def search_items(query: str, limit: int = 30) -> list[dict]:
    async with httpx.AsyncClient() as client:
        title_results, artist_results = await asyncio.gather(
            _search_by_title(query, client, limit),
            _search_by_artist(query, client, limit),
            return_exceptions=True,
        )

    # Handle partial failures — if one branch errored, treat it as empty
    title_list  = title_results  if isinstance(title_results,  list) else []
    artist_list = artist_results if isinstance(artist_results, list) else []

    # Merge and deduplicate by ID; title matches appear first
    seen, merged = set(), []
    for item in title_list + artist_list:
        if item["id"] not in seen:
            seen.add(item["id"])
            merged.append(item)
    return merged[:limit]


async def get_item(item_id: str) -> dict | None:
    # Use /Items?Ids= consistently — /Items/{id} requires UserId in some Jellyfin versions.
    # MediaStreams is included here (not in search) because codec detection is only needed
    # at link-creation time, and it adds payload overhead to search results.
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{JELLYFIN_URL}/Items", params={
            "Ids":    item_id,
            "Fields": "RunTimeTicks,ProductionYear,Artists,MediaStreams",
            "api_key": JELLYFIN_API_KEY,
        }, timeout=10.0)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        items = r.json().get("Items", [])

    if not items:
        return None
    return _parse_item(items[0])


def build_stream_url(
    item_id: str,
    item_type: str,
    needs_transcode: bool = False,
    start_ticks: int = 0,
) -> str:
    """Construct the internal Jellyfin stream URL for proxying.

    Audio (compatible codec): static=true — raw file bytes, Range-seekable.
    Audio (incompatible codec, e.g. ALAC): transcode to raw ADTS AAC.
        StartTimeTicks lets Jellyfin begin encoding from an arbitrary position,
        which the MSE-based frontend player uses for seek support.
    Video: static passthrough — transcoding video on-the-fly is expensive and
        most containers served by Jellyfin are already browser-compatible.
    """
    if item_type == "Audio" and needs_transcode:
        # MP3 (audio/mpeg) is used rather than AAC ADTS (audio/aac) because
        # Chrome's MSE implementation for audio/mpeg handles long tracks and
        # buffer eviction more reliably.  Chrome's audio/aac SourceBuffer has
        # an ~12 MB hard limit which a 6-minute track at 256 kbps hits exactly.
        params = f"AudioCodec=mp3&Container=mp3&api_key={JELLYFIN_API_KEY}"
        if start_ticks:
            params += f"&StartTimeTicks={start_ticks}"
        return f"{JELLYFIN_URL}/Audio/{item_id}/stream?{params}"
    if item_type == "Audio":
        return f"{JELLYFIN_URL}/Audio/{item_id}/stream?static=true&api_key={JELLYFIN_API_KEY}"
    return f"{JELLYFIN_URL}/Videos/{item_id}/stream?static=true&api_key={JELLYFIN_API_KEY}"
