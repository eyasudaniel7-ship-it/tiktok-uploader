import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from src.config import DEFAULT_PROVIDER, CAPTION_MAX_LENGTH

logger = logging.getLogger(__name__)


@dataclass
class Metadata:
    caption: str
    hashtags: list[str]
    cover_timestamp_ms: int = 1000
    privacy_level: str = "PUBLIC_TO_EVERYONE"
    disable_duet: bool = False
    disable_stitch: bool = False
    disable_comment: bool = False


def generate_metadata(
    file_path: Path,
    brand_context: dict,
    language: str = "en",
    provider: Optional[str] = None,
) -> Metadata:
    resolved = provider or DEFAULT_PROVIDER
    handler = PROVIDERS.get(resolved) or PROVIDERS["gemini"]
    return handler(file_path, brand_context, language)


def _build_prompt(brand_context: dict, language: str, filename: str) -> str:
    lang_instruction = (
        "Write the caption in Amharic (use Unicode/Ge'ez script)."
        if language == "am"
        else "Write the caption in English."
    )

    return f"""You are a TikTok sales copywriter for {brand_context.get('brand', 'a brand')}. Your goal is to sell products and rank high on TikTok search.

Brand: {brand_context.get('brand', 'Unknown')}
Niche: {brand_context.get('niche', '')}
Audience: {brand_context.get('audience', '')}
Tone: {brand_context.get('tone', '')}

Filename: {filename}

{lang_instruction}

An image of the actual product is attached. Examine it carefully — identify the product type, color, material, style, and any visible details or text. Use what you see to write an accurate, specific caption.

Rules:
- SALES: Lead with a hook that sparks curiosity or desire. Mention benefits, not just features. Create urgency (limited stock, trend ending, must-have). End with a strong CTA (link in bio, DM, shop now).
- SEO: Include 2-3 high-intent search keywords naturally in the caption (e.g. "best gift for her in Ethiopia", "affordable perfume Addis Ababa"). Think about what customers actually type into TikTok search.
- Caption: max {CAPTION_MAX_LENGTH} characters, conversational, emojis welcome but don't overdo it
- Hashtags: 3-8 tags, include 2 high-volume broad tags + 2-3 niche tags + brand tag
- Output ONLY valid JSON with no markdown, no code fences, no extra text:
{{"caption": "...", "hashtags": ["#tag1", "#tag2", ...]}}"""


def generate_with_gemini(
    file_path: Path, brand_context: dict, language: str
) -> Metadata:
    try:
        from google import genai
        from google.genai import types
        import PIL.Image

        api_key = __import__("os").getenv("GOOGLE_API_KEY")
        if not api_key:
            return _fallback_metadata(file_path, language)

        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(brand_context, language, file_path.name)

        image_types = {".jpg", ".jpeg", ".png", ".webp"}
        if file_path.suffix.lower() in image_types:
            image = PIL.Image.open(file_path)
            contents = [prompt, image]
        else:
            contents = [prompt]

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )

        return _parse_response(response.text, file_path, language)

    except Exception as e:
        logger.warning("Gemini generation failed: %s — using fallback", e)
        return _fallback_metadata(file_path, language)


def generate_with_openai(
    file_path: Path, brand_context: dict, language: str
) -> Metadata:
    try:
        from openai import OpenAI
        client = OpenAI()
        prompt = _build_prompt(brand_context, language, file_path.name)

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )
        return _parse_response(resp.choices[0].message.content, file_path, language)
    except Exception as e:
        logger.warning("OpenAI generation failed: %s — using fallback", e)
        return _fallback_metadata(file_path, language)


def generate_with_claude(
    file_path: Path, brand_context: dict, language: str
) -> Metadata:
    try:
        import anthropic
        client = anthropic.Anthropic()
        prompt = _build_prompt(brand_context, language, file_path.name)

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_response(resp.content[0].text, file_path, language)
    except Exception as e:
        logger.warning("Claude generation failed: %s — using fallback", e)
        return _fallback_metadata(file_path, language)


def generate_with_ollama(
    file_path: Path, brand_context: dict, language: str
) -> Metadata:
    try:
        import requests as req
        prompt = _build_prompt(brand_context, language, file_path.name)
        resp = req.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=60,
        )
        text = resp.json().get("response", "")
        return _parse_response(text, file_path, language)
    except Exception as e:
        logger.warning("Ollama generation failed: %s — using fallback", e)
        return _fallback_metadata(file_path, language)


def _parse_response(text: str, file_path: Path, language: str) -> Metadata:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Could not parse AI response as JSON — using fallback")
        return _fallback_metadata(file_path, language)

    caption = (data.get("caption") or "").strip()[:CAPTION_MAX_LENGTH]
    hashtags = data.get("hashtags", [])

    if not caption:
        return _fallback_metadata(file_path, language)

    return Metadata(
        caption=caption,
        hashtags=hashtags[:8],
        cover_timestamp_ms=1000,
        privacy_level="PUBLIC_TO_EVERYONE",
    )


def _fallback_metadata(file_path: Path, language: str) -> Metadata:
    stem = file_path.stem.replace("_am", "").replace("_en", "").replace("_", " ").title()
    return Metadata(
        caption=f"Check out this {stem}! Link in bio to shop!",
        hashtags=["#fyp", "#tiktok", "#shopping"],
        cover_timestamp_ms=1000,
        privacy_level="PUBLIC_TO_EVERYONE",
    )


PROVIDERS = {
    "gemini": generate_with_gemini,
    "openai": generate_with_openai,
    "claude": generate_with_claude,
    "ollama": generate_with_ollama,
}
