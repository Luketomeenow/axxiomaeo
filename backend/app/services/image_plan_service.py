"""Claude-based image slot planning with AEO alt/caption text."""

import json
import logging
import re

from app.config import get_settings
from app.models.brand import Brand
from app.services.claude_service import ClaudeService

logger = logging.getLogger(__name__)

IMAGE_PLAN_PROMPT = """You are an AEO content strategist for {brand_name}, an elevator service company.

Given the article HTML and target query, plan {max_images} images to insert.
Return ONLY valid JSON (no markdown fences):

{{
  "images": [
    {{
      "slot": "hero",
      "placement": "after_h1",
      "prompt": "Professional photo description for DALL-E — elevator industry, no logos, no text overlays",
      "alt": "125-200 char factual alt text aligned to target query",
      "title": "Short image title",
      "caption": "1-2 sentence figcaption for AI crawlers and readers"
    }}
  ]
}}

RULES:
- slot: hero | inline_1 | inline_2
- placement: after_h1 | after_h2_index (use h2_index 0-based for inline images)
- prompt: photorealistic, professional elevator maintenance/repair/inspection scene, no brand logos
- alt and caption must be factual, include target-query terms where natural
- Plan exactly {max_images} images (hero first, then inline after key H2 sections)

Target query: "{target_query}"
Content type: {content_type}
"""


def _parse_plan_json(raw: str) -> list[dict]:
    text = raw.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    images = data.get("images", [])
    if not isinstance(images, list):
        return []
    return [img for img in images if isinstance(img, dict) and img.get("prompt")]


class ImagePlanService:
    def __init__(self):
        self.claude = ClaudeService()
        self.settings = get_settings()

    async def plan_images(
        self,
        html: str,
        target_query: str,
        brand: Brand,
        content_type: str,
    ) -> list[dict]:
        max_images = max(1, self.settings.content_max_images)
        prompt = IMAGE_PLAN_PROMPT.format(
            brand_name=brand.name,
            max_images=max_images,
            target_query=target_query,
            content_type=content_type,
        )
        response = await self.claude.client.messages.create(
            model=self.claude.model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt}\n\nArticle HTML (first 4000 chars):\n{html[:4000]}",
                }
            ],
        )
        raw = response.content[0].text
        try:
            return _parse_plan_json(raw)[:max_images]
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse image plan JSON: %s", exc)
            return []
