import httpx
from app.config import JELLYFIN_URL, JELLYFIN_API_KEY

# Item types that can be directly streamed
STREAMABLE_TYPES = "Movie,Episode,Audio,MusicVideo"


async def search_items(query: str, limit: int = 30) -> list[dict]:
    params = {
        "searchTerm": query,
        "Recursive": "true",
        "IncludeItemTypes": STREAMABLE_TYPES,
        "Limit": limit,
        "Fields": "RunTimeTicks,ProductionYear,Overview",
        "api_key": JELLYFIN_API_KEY,
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{JELLYFIN_URL}/Items", params=params, timeout=10.0)
        r.raise_for_status()
        items = r.json().get("Items", [])

    results = []
    for item in items:
        ticks = item.get("RunTimeTicks")
        results.append({
            "id":               item["Id"],
            "title":            item.get("Name", "Unknown"),
            "type":             item.get("Type", "Unknown"),
            "year":             item.get("ProductionYear"),
            "duration_seconds": int(ticks / 10_000_000) if ticks else None,
        })
    return results


async def get_item(item_id: str) -> dict | None:
    params = {"api_key": JELLYFIN_API_KEY}
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{JELLYFIN_URL}/Items/{item_id}", params=params, timeout=10.0)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        item = r.json()

    ticks = item.get("RunTimeTicks")
    return {
        "id":               item["Id"],
        "title":            item.get("Name", "Unknown"),
        "type":             item.get("Type", "Unknown"),
        "year":             item.get("ProductionYear"),
        "duration_seconds": int(ticks / 10_000_000) if ticks else None,
    }


def build_stream_url(item_id: str, item_type: str) -> str:
    """Construct the internal Jellyfin stream URL for proxying."""
    if item_type == "Audio":
        path = f"/Audio/{item_id}/stream"
    else:
        path = f"/Videos/{item_id}/stream"
    return f"{JELLYFIN_URL}{path}?static=true&api_key={JELLYFIN_API_KEY}"
