import os
from dotenv import load_dotenv

load_dotenv()

JELLYFIN_URL: str = os.getenv("JELLYFIN_URL", "http://localhost:8096").rstrip("/")
JELLYFIN_API_KEY: str = os.getenv("JELLYFIN_API_KEY", "")
ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "")
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH: str = os.getenv(
    "DB_PATH",
    os.path.join(_PROJECT_ROOT, "data", "links.db"),
)
BACKGROUNDS_DIR: str = os.getenv(
    "BACKGROUNDS_DIR",
    os.path.join(_PROJECT_ROOT, "backgrounds"),
)

# Character length of newly generated share link IDs (app/routes/admin.py).
# Only affects new links — existing ones keep working at whatever length they
# already are. Bounded to keep IDs resistant to brute-force guessing against
# the public endpoints (paired with rate limiting below) without going longer
# than necessary.
_LINK_ID_LENGTH_MIN = 8
_LINK_ID_LENGTH_MAX = 16
LINK_ID_LENGTH: int = int(os.getenv("LINK_ID_LENGTH", "12"))
if not (_LINK_ID_LENGTH_MIN <= LINK_ID_LENGTH <= _LINK_ID_LENGTH_MAX):
    raise ValueError(
        f"LINK_ID_LENGTH must be between {_LINK_ID_LENGTH_MIN} and {_LINK_ID_LENGTH_MAX} "
        f"(got {LINK_ID_LENGTH}). Shorter IDs are brute-forceable against the public "
        f"endpoints; there's no real benefit to going higher than {_LINK_ID_LENGTH_MAX}."
    )

# Basic per-IP rate limiting for the public, unauthenticated endpoints that
# could otherwise be used to brute-force guess link IDs.
RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
