import asyncio
import logging
import httpx
from app.config import JELLYFIN_URL, JELLYFIN_API_KEY

logger = logging.getLogger(__name__)

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
        # Only populated when MediaStreams is included in the response (get_item, not
        # search) — applies to video items too, since ripped movies/episodes commonly
        # carry surround audio (DTS, EAC3, TrueHD) that browsers can't decode natively,
        # even though the video codec itself plays fine.
        "needs_transcode":  _check_needs_transcode(item),
    }


async def _search_by_title(
    query: str,
    client: httpx.AsyncClient,
    limit: int,
    item_types: str,
    parent_id: str | None,
) -> list[dict]:
    params = {
        "searchTerm":       query,
        "Recursive":        "true",
        "IncludeItemTypes": item_types,
        "Limit":            limit,
        "Fields":           "RunTimeTicks,ProductionYear,Artists",
        "api_key":          JELLYFIN_API_KEY,
    }
    if parent_id:
        params["ParentId"] = parent_id
    r = await client.get(f"{JELLYFIN_URL}/Items", params=params, timeout=10.0)
    r.raise_for_status()
    return [_parse_item(i) for i in r.json().get("Items", [])]


async def _search_by_artist(
    query: str,
    client: httpx.AsyncClient,
    limit: int,
    item_types: str,
    parent_id: str | None,
) -> list[dict]:
    # Only Audio/MusicVideo items carry an Artists field — nothing to do if the
    # requested item types don't include either.
    artist_types = [t for t in item_types.split(",") if t in ("Audio", "MusicVideo")]
    if not artist_types:
        return []

    # Step 1: find artist IDs matching the query
    artist_params = {"searchTerm": query, "Limit": 10, "api_key": JELLYFIN_API_KEY}
    if parent_id:
        artist_params["ParentId"] = parent_id
    r = await client.get(f"{JELLYFIN_URL}/Artists", params=artist_params, timeout=10.0)
    r.raise_for_status()
    artist_ids = [a["Id"] for a in r.json().get("Items", [])]
    if not artist_ids:
        return []

    # Step 2: fetch items by those artist IDs, restricted to the requested audio types
    item_params = {
        "ArtistIds":        ",".join(artist_ids),
        "Recursive":        "true",
        "IncludeItemTypes": ",".join(artist_types),
        "Limit":            limit,
        "Fields":           "RunTimeTicks,ProductionYear,Artists",
        "api_key":          JELLYFIN_API_KEY,
    }
    if parent_id:
        item_params["ParentId"] = parent_id
    r = await client.get(f"{JELLYFIN_URL}/Items", params=item_params, timeout=10.0)
    r.raise_for_status()
    return [_parse_item(i) for i in r.json().get("Items", [])]


async def search_items(
    query: str,
    limit: int = 30,
    item_types: list[str] | None = None,
    library_ids: list[str] | None = None,
) -> list[dict]:
    types_param = ",".join(item_types) if item_types else STREAMABLE_TYPES
    # No libraries selected = search the whole server; otherwise run one
    # scoped query per selected library (Jellyfin's ParentId filter takes a
    # single value, not a list).
    scopes: list[str | None] = library_ids if library_ids else [None]

    async with httpx.AsyncClient() as client:
        tasks = []
        for parent_id in scopes:
            tasks.append(_search_by_title(query, client, limit, types_param, parent_id))
            tasks.append(_search_by_artist(query, client, limit, types_param, parent_id))
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge every scope/branch, logging (not silently swallowing) any failures,
    # and deduplicate by ID in arrival order — title matches for a given scope
    # land before that scope's artist matches.
    seen, merged = set(), []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Jellyfin search failed for query %r: %s", query, result)
            continue
        for item in result:
            if item["id"] not in seen:
                seen.add(item["id"])
                merged.append(item)
    return merged[:limit]


async def get_libraries() -> list[dict]:
    """Return the server's top-level libraries (Movies, TV Shows, Music, etc.)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{JELLYFIN_URL}/Library/VirtualFolders", params={
            "api_key": JELLYFIN_API_KEY,
        }, timeout=10.0)
        r.raise_for_status()
        folders = r.json()
    return [
        {"id": f["ItemId"], "name": f["Name"], "collection_type": f.get("CollectionType")}
        for f in folders
    ]


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
    Video (compatible audio codec): static passthrough — transcoding video on-the-fly
        is expensive and most containers served by Jellyfin are already browser-compatible.
    Video (incompatible audio codec, e.g. DTS/EAC3/TrueHD): this function still returns
        static passthrough here — the frontend never actually fetches this URL for that
        case, it goes through the HLS playlist route instead (app/routes/hls.py), which
        remuxes with VideoCodec=copy&AudioCodec=aac so only the audio is transcoded.
        Byte-range seeking against a live transcode is undefined, same reasoning as audio.
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
