from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

LUBANJA_BRAND_CONTEXT = {
    "brand": "Lubanja",
    "niche": "Gifts, accessories, perfumes",
    "audience": "Ethiopian customers, Amharic and English speakers",
    "tone": "Warm, gift-worthy, aspirational but affordable",
    "platform": "TikTok",
}

@dataclass
class Account:
    name: str
    client_key: str
    client_secret: str
    access_token: str
    refresh_token: str
    content_folder: Path
    brand_context: dict
    default_language: str = "am"

API_MODE = os.getenv("API_MODE", "mock")

MAX_POSTS_PER_DAY = 15
MAX_VIDEO_SIZE_BYTES = 4 * 1024 ** 3
MAX_VIDEO_DURATION_S = 600
ALLOWED_VIDEO_FORMATS = {".mp4", ".mov"}
ALLOWED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}
CHUNK_SIZE_BYTES = 10 * 1024 * 1024
CAPTION_MAX_LENGTH = 2200
RATE_LIMIT_WAIT_S = 60
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 120
RETRY_DELAY_S = 10
MAX_CONSECUTIVE_FAILURES = 2
BATCH_SIZE = 10

TIKTOK_API_BASE = "https://open-api.tiktok.com"
UPLOAD_VIDEO_INIT = f"{TIKTOK_API_BASE}/v2/post/publish/inbox/video/init/"
UPLOAD_CONTENT_INIT = f"{TIKTOK_API_BASE}/v2/post/publish/content/init/"
STATUS_FETCH = f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/"
TOKEN_REFRESH = f"{TIKTOK_API_BASE}/v2/oauth/token/"

ERROR_ACTIONS = {
    "ok": "continue",
    "too_many_requests": "wait_retry",
    "spam_risk_too_many_posts": "stop",
    "media_processing_failed": "skip",
    "access_token_invalid": "refresh_retry",
    "permission_denied": "stop",
}

LOG_STATUSES = [
    "UPLOADED",
    "UPLOADED_RETRY",
    "FAILED",
    "SKIPPED_ALREADY_DONE",
    "SKIPPED_BAD_FORMAT",
    "SKIPPED_TOO_LARGE",
    "TOKEN_REFRESHED",
    "STOPPED_CONSECUTIVE_FAILURES",
]

DEFAULT_PROVIDER = "gemini"

def build_accounts() -> dict[str, Account]:
    def env_val(key: str) -> str:
        return os.getenv(key, "")

    lubanja = Account(
        name="lubanja",
        client_key=env_val("LUBANJA_CLIENT_KEY"),
        client_secret=env_val("LUBANJA_CLIENT_SECRET"),
        access_token=env_val("LUBANJA_ACCESS_TOKEN"),
        refresh_token=env_val("LUBANJA_REFRESH_TOKEN"),
        content_folder=PROJECT_ROOT / "content" / "lubanja",
        brand_context=LUBANJA_BRAND_CONTEXT,
        default_language="am",
    )

    return {"lubanja": lubanja}

ACCOUNTS = build_accounts()
ACTIVE_ACCOUNT_NAME = "lubanja"

def get_active_account() -> Account:
    return ACCOUNTS[ACTIVE_ACCOUNT_NAME]

def is_mock_mode() -> bool:
    return API_MODE == "mock"
