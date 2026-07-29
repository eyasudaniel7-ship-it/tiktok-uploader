import math
import time
import logging
from pathlib import Path
from typing import Optional
import requests

from src.auth import TikTokAuth
from src.config import (
    Account,
    is_mock_mode,
    UPLOAD_VIDEO_INIT,
    UPLOAD_CONTENT_INIT,
    STATUS_FETCH,
    CHUNK_SIZE_BYTES,
    POLL_INTERVAL_S,
    POLL_TIMEOUT_S,
    ERROR_ACTIONS,
)

logger = logging.getLogger(__name__)


class TikTokUploader:
    def __init__(self, auth: TikTokAuth, account: Account):
        self.auth = auth
        self.account = account
        self._session = requests.Session()

    def upload_video(self, file_path: Path, caption: str, hashtags: list[str]) -> dict:
        if is_mock_mode():
            return self._mock_upload(file_path, "video")

        publish_id, upload_url = self._init_video_upload(file_path)
        self._upload_chunked(upload_url, file_path, "video/mp4")
        status = self._poll_status(publish_id)
        return {
            "publish_id": publish_id,
            "status": status,
            "file": file_path.name,
        }

    def upload_photo(self, file_path: Path, caption: str, hashtags: list[str]) -> dict:
        if is_mock_mode():
            return self._mock_upload(file_path, "photo")

        publish_id, upload_url = self._init_photo_upload(file_path, caption, hashtags)
        self._upload_single(upload_url, file_path)
        status = self._poll_status(publish_id)
        return {
            "publish_id": publish_id,
            "status": status,
            "file": file_path.name,
        }

    def _init_video_upload(self, file_path: Path) -> tuple[str, str]:
        file_size = file_path.stat().st_size
        chunk_size = CHUNK_SIZE_BYTES
        total_chunks = math.ceil(file_size / chunk_size)

        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"

        body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            }
        }

        resp = self._session.post(UPLOAD_VIDEO_INIT, json=body, headers=headers, timeout=30)
        data = resp.json().get("data", {})

        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")

        if not publish_id or not upload_url:
            raise RuntimeError(f"Video init failed: {resp.text}")

        return publish_id, upload_url

    def _init_photo_upload(
        self, file_path: Path, caption: str, hashtags: list[str]
    ) -> tuple[str, str]:
        file_size = file_path.stat().st_size
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"

        body = {
            "post_mode": "MEDIA_UPLOAD",
            "media_type": "PHOTO",
            "post_info": {
                "title": caption,
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_stitch": False,
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "photo_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        if hashtags:
            body["post_info"]["hashtags"] = hashtags

        resp = self._session.post(UPLOAD_CONTENT_INIT, json=body, headers=headers, timeout=30)
        data = resp.json().get("data", {})

        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")

        if not publish_id or not upload_url:
            raise RuntimeError(f"Photo init failed: {resp.text}")

        return publish_id, upload_url

    def _upload_chunked(self, upload_url: str, file_path: Path, mime: str):
        file_size = file_path.stat().st_size
        chunk_size = CHUNK_SIZE_BYTES
        offset = 0
        chunk_index = 0

        with open(file_path, "rb") as f:
            while offset < file_size:
                chunk = f.read(chunk_size)
                end = offset + len(chunk) - 1

                headers = {
                    "Content-Range": f"bytes {offset}-{end}/{file_size}",
                    "Content-Type": mime,
                }

                resp = self._session.put(
                    f"{upload_url}&chunk={chunk_index}",
                    data=chunk,
                    headers=headers,
                    timeout=120,
                )
                resp.raise_for_status()

                offset += len(chunk)
                chunk_index += 1

    def _upload_single(self, upload_url: str, file_path: Path):
        file_size = file_path.stat().st_size
        headers = {
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Type": "image/jpeg",
        }
        with open(file_path, "rb") as f:
            resp = self._session.put(upload_url, data=f, headers=headers, timeout=120)
        resp.raise_for_status()

    def _poll_status(self, publish_id: str) -> str:
        headers = self.auth.get_auth_header()
        headers["Content-Type"] = "application/json"

        start = time.time()
        while time.time() - start < POLL_TIMEOUT_S:
            resp = self._session.post(
                STATUS_FETCH,
                json={"publish_id": publish_id},
                headers=headers,
                timeout=30,
            )
            data = resp.json().get("data", {})
            status = data.get("status", "")

            if status == "SEND_TO_USER_INBOX":
                return "SEND_TO_USER_INBOX"
            if status == "FAILED":
                err = data.get("error", {})
                raise RuntimeError(
                    f"Upload failed: {err.get('code', 'unknown')} - {err.get('message', '')}"
                )

            time.sleep(POLL_INTERVAL_S)

        raise TimeoutError(f"Status polling timed out for {publish_id}")

    def _mock_upload(self, file_path: Path, media_type: str) -> dict:
        import uuid
        logger.info("MOCK: would upload %s as %s", file_path.name, media_type)
        return {
            "publish_id": f"mock_{uuid.uuid4().hex[:12]}",
            "status": "SEND_TO_USER_INBOX",
            "file": file_path.name,
        }

    def handle_error(self, error_code: str) -> str:
        return ERROR_ACTIONS.get(error_code, "stop")
