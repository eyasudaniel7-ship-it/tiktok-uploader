import tempfile
import pytest
from pathlib import Path
from src.uploader import TikTokUploader
from src.auth import TikTokAuth
from src.config import Account, LUBANJA_BRAND_CONTEXT


@pytest.fixture
def mock_account():
    return Account(
        name="test",
        client_key="test_key",
        client_secret="test_secret",
        access_token="test_token",
        refresh_token="test_refresh",
        content_folder=Path(tempfile.mkdtemp()),
        brand_context=LUBANJA_BRAND_CONTEXT,
        default_language="en",
    )


class TestMockUpload:
    def test_mock_video_upload_returns_publish_id(self, mock_account):
        auth = TikTokAuth(mock_account)
        uploader = TikTokUploader(auth, mock_account)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video data")
            dummy = Path(f.name)
        result = uploader.upload_video(dummy, "Test caption", ["#test"])
        assert result["status"] == "SEND_TO_USER_INBOX"
        assert result["publish_id"].startswith("mock_")
        assert result["file"] == dummy.name
        dummy.unlink()

    def test_mock_photo_upload_returns_publish_id(self, mock_account):
        auth = TikTokAuth(mock_account)
        uploader = TikTokUploader(auth, mock_account)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake photo data")
            dummy = Path(f.name)
        result = uploader.upload_photo(dummy, "Test caption", ["#test"])
        assert result["status"] == "SEND_TO_USER_INBOX"
        assert result["publish_id"].startswith("mock_")
        dummy.unlink()

    def test_handle_error_returns_action(self, mock_account):
        auth = TikTokAuth(mock_account)
        uploader = TikTokUploader(auth, mock_account)
        assert uploader.handle_error("ok") == "continue"
        assert uploader.handle_error("too_many_requests") == "wait_retry"
        assert uploader.handle_error("unknown_code") == "stop"
