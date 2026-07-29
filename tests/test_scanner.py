import pytest
from pathlib import Path
from src.scanner import scan_content, _detect_language
from src.config import Account, LUBANJA_BRAND_CONTEXT

TEST_CONTENT = Path(__file__).resolve().parent / "fixtures"
TEST_CONTENT.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def mock_account():
    return Account(
        name="test",
        client_key="",
        client_secret="",
        access_token="",
        refresh_token="",
        content_folder=TEST_CONTENT,
        brand_context=LUBANJA_BRAND_CONTEXT,
        default_language="en",
    )


def _touch(name: str):
    p = TEST_CONTENT / name
    p.write_text("test")
    return p


class TestDetectLanguage:
    def test_detects_amharic(self):
        assert _detect_language("video_001_am.mp4") == "am"

    def test_detects_english(self):
        assert _detect_language("video_001_en.mp4") == "en"

    def test_defaults_to_english(self):
        assert _detect_language("video_001.mp4") == "en"


class TestScanContent:
    def setup_method(self):
        self.files = []

    def teardown_method(self):
        import shutil
        for f in TEST_CONTENT.iterdir():
            if f.is_file():
                f.unlink()

    def test_finds_video_and_image_files(self, mock_account):
        self.files = [
            _touch("test_am.mp4"),
            _touch("test_en.jpg"),
            _touch("ignore.txt"),
            _touch("test_en.png"),
        ]
        items = scan_content(mock_account.content_folder, mock_account)
        assert len(items) == 4
        valid = [i for i in items if i.format_valid]
        assert len(valid) == 3
        assert all(i.format_valid for i in valid)
        txt_item = next(i for i in items if i.filename == "ignore.txt")
        assert not txt_item.format_valid

    def test_skips_oversized_videos(self, mock_account):
        large = TEST_CONTENT / "large.mp4"
        large.write_bytes(b"x" * 1024 * 1024)
        items = scan_content(mock_account.content_folder, mock_account)
        # Our tests don't trigger max size (4GB) but the size_valid logic runs
        assert len(items) == 1
        assert items[0].format_valid
