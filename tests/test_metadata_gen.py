import pytest
from pathlib import Path
from src.metadata_gen import (
    _fallback_metadata,
    _parse_response,
    _build_prompt,
)
from src.config import LUBANJA_BRAND_CONTEXT


class TestFallbackMetadata:
    def test_returns_caption_and_hashtags(self):
        meta = _fallback_metadata(Path("test_am.mp4"), "am")
        assert meta.caption
        assert len(meta.hashtags) >= 3
        assert meta.privacy_level == "PUBLIC_TO_EVERYONE"

    def test_strips_language_suffix_from_filename(self):
        meta = _fallback_metadata(Path("cool_product_en.mp4"), "en")
        assert "Cool Product" in meta.caption


class TestParseResponse:
    def test_parses_valid_json(self):
        text = '{"caption": "Test caption!", "hashtags": ["#test1", "#test2"]}'
        meta = _parse_response(text, Path("test.mp4"), "en")
        assert meta.caption == "Test caption!"
        assert meta.hashtags == ["#test1", "#test2"]

    def test_strips_code_fences(self):
        text = '```json\n{"caption": "Fenced!", "hashtags": ["#a"]}\n```'
        meta = _parse_response(text, Path("test.mp4"), "en")
        assert meta.caption == "Fenced!"

    def test_fallback_on_bad_json(self):
        meta = _parse_response("not json at all", Path("test.mp4"), "en")
        assert "Check out this" in meta.caption


class TestBuildPrompt:
    def test_includes_brand_context(self):
        prompt = _build_prompt(LUBANJA_BRAND_CONTEXT, "en", "video_001.mp4")
        assert "Lubanja" in prompt
        assert "Gifts" in prompt
        assert "English" in prompt
        assert "video_001.mp4" in prompt

    def test_amharic_instruction(self):
        prompt = _build_prompt(LUBANJA_BRAND_CONTEXT, "am", "video_001_am.mp4")
        assert "Amharic" in prompt
