import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.config import (
    Account,
    ALLOWED_VIDEO_FORMATS,
    ALLOWED_IMAGE_FORMATS,
    MAX_VIDEO_SIZE_BYTES,
)

logger = logging.getLogger(__name__)


@dataclass
class ContentItem:
    file_path: Path
    filename: str
    file_size_mb: float
    media_type: str
    language: str
    format_valid: bool
    size_valid: bool
    already_uploaded: bool = False
    skip_reason: Optional[str] = None


def scan_content(folder_path: Path, account: Account) -> list[ContentItem]:
    if not folder_path.exists():
        logger.warning("Content folder does not exist: %s", folder_path)
        return []

    uploaded_names = _load_uploaded_log(account.name)
    items: list[ContentItem] = []

    for f in sorted(folder_path.iterdir()):
        if not f.is_file():
            continue

        ext = f.suffix.lower()
        is_video = ext in ALLOWED_VIDEO_FORMATS
        is_image = ext in ALLOWED_IMAGE_FORMATS

        if not is_video and not is_image:
            items.append(_make_item(f, account.name, uploaded_names, format_valid=False))
            continue

        media_type = "video" if is_video else "photo"
        item = _make_item(f, account.name, uploaded_names, format_valid=True, media_type=media_type)

        if is_video and f.stat().st_size > MAX_VIDEO_SIZE_BYTES:
            item.size_valid = False
            item.skip_reason = "SKIPPED_TOO_LARGE"

        items.append(item)

    return items


def _make_item(
    f: Path,
    account_name: str,
    uploaded_names: set,
    format_valid: bool,
    media_type: str = "video",
) -> ContentItem:
    name = f.name
    language = _detect_language(name)

    size_mb = f.stat().st_size / (1024 * 1024)
    already = name in uploaded_names

    return ContentItem(
        file_path=f,
        filename=name,
        file_size_mb=round(size_mb, 1),
        media_type=media_type,
        language=language,
        format_valid=format_valid,
        size_valid=True,
        already_uploaded=already,
        skip_reason="SKIPPED_ALREADY_DONE" if already else None,
    )


def _detect_language(filename: str) -> str:
    stem = Path(filename).stem.lower()
    if stem.endswith("_am"):
        return "am"
    if stem.endswith("_en"):
        return "en"
    return "en"


def _load_uploaded_log(account_name: str) -> set[str]:
    log_path = Path(__file__).resolve().parents[1] / "logs" / "upload_log.jsonl"
    if not log_path.exists():
        return set()

    uploaded = set()
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("status", "").startswith("UPLOADED") and entry.get("filename"):
                    uploaded.add(entry["filename"])
            except json.JSONDecodeError:
                continue
    return uploaded
