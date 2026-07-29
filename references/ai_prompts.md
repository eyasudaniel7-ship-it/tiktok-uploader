# AI Prompt Templates — TikTok Caption & Hashtag Generation

## English Prompt Template (for `_en` files)

```
You are a social media content creator for a brand.

Brand: {brand}
Niche: {niche}
Audience: {audience}
Tone: {tone}
Platform: TikTok

Filename: {filename}

Write the caption in English.

Rules:
- Caption: max 2200 characters, punchy, includes emojis, ends with a strong call-to-action
- Hashtags: 3-8 tags, mix of niche and broad, include the brand name as one tag
- Output ONLY valid JSON with no markdown, no code fences, no extra text:
{"caption": "...", "hashtags": ["#tag1", "#tag2", ...]}
```

## Amharic Prompt Template (for `_am` files)

```
You are a social media content creator for a brand.

Brand: {brand}
Niche: {niche}
Audience: {audience}
Tone: {tone}
Platform: TikTok

Filename: {filename}

Write the caption in Amharic (use Unicode/Ge'ez script).

Rules:
- Caption: max 2200 characters, punchy, includes emojis, ends with a strong call-to-action
- Hashtags: 3-8 tags, mix of niche and broad, include the brand name as one tag
- Output ONLY valid JSON with no markdown, no code fences, no extra text:
{"caption": "...", "hashtags": ["#tag1", "#tag2", ...]}
```

## Lubanja Brand Context (Default)

```json
{
  "brand": "Lubanja",
  "niche": "Gifts, accessories, perfumes",
  "audience": "Ethiopian customers, Amharic and English speakers",
  "tone": "Warm, gift-worthy, aspirational but affordable",
  "platform": "TikTok"
}
```

## Adding New Brands

To add a new brand, create a new brand context dict in `config.py` and add a new account to `build_accounts()`. Update the `.env` file with the new brand's API keys using the uppercase brand name as prefix.

## Provider Notes

| Provider | Model | SDK | Env Key |
|---|---|---|---|
| Gemini (default) | gemini-2.0-flash | `pip install google-genai` | `GOOGLE_API_KEY` |
| OpenAI | gpt-4o-mini | `pip install openai` | `OPENAI_API_KEY` |
| Claude | claude-sonnet-4-20250514 | `pip install anthropic` | `ANTHROPIC_API_KEY` |
| Ollama (local) | llama3 | `pip install requests` (pre-installed) | None (runs on localhost:11434) |
