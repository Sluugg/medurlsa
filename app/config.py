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
