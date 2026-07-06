"""
Central configuration for WMark Bot.
Loads everything from environment variables (.env file).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val else default


def _list_ids(name: str) -> set[int]:
    raw = os.getenv(name, "")
    return {int(x.strip()) for x in raw.split(",") if x.strip()}


# ---- Telegram ----
API_ID = _int("API_ID", 0)
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# ---- WebApp ----
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080").rstrip("/")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = _int("WEBAPP_PORT", 8080)

# ---- Database ----
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./storage/wmarkbot.db")

# ---- Storage paths ----
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
WATERMARKS_DIR = STORAGE_DIR / "watermarks"
OUTPUT_DIR = STORAGE_DIR / "output"
for d in (STORAGE_DIR, UPLOADS_DIR, WATERMARKS_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- Plans ----
PLAN_LIMITS = {
    "free": {
        "templates": _int("FREE_PLAN_TEMPLATE_LIMIT", 3),
        "channels": _int("FREE_PLAN_CHANNEL_LIMIT", 1),
        "daily_mb": _int("FREE_PLAN_DAILY_MB", 200),
    },
    "normal": {
        "templates": _int("NORMAL_PLAN_TEMPLATE_LIMIT", 15),
        "channels": _int("NORMAL_PLAN_CHANNEL_LIMIT", 15),
        "daily_mb": _int("NORMAL_PLAN_DAILY_MB", 3072),
    },
    "pro": {
        "templates": _int("PRO_PLAN_TEMPLATE_LIMIT", 100),
        "channels": _int("PRO_PLAN_CHANNEL_LIMIT", 100),
        "daily_mb": _int("PRO_PLAN_DAILY_MB", 20480),
    },
}

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 50)
ADMIN_IDS = _list_ids("ADMIN_IDS")
JWT_SECRET = os.getenv("JWT_SECRET", "insecure_dev_secret_change_me")

# Watermark position presets -> (anchor keyword used by the image engine)
POSITIONS = [
    "top-left", "top-center", "top-right",
    "middle-left", "center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
    "random", "fill",
]
