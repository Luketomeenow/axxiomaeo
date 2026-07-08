"""Claude-based image slot planning with AEO alt/caption text."""

import json
import logging
import re

from app.config import get_settings
from app.models.brand import Brand
from app.services.claude_service import ClaudeService

logger = logging.getLogger(__name__)

IMAGE_PLAN_PROMPT = """You are a photo art director for {brand_name}, an elevator service company serving {markets}.

Plan {max_images} distinct, photorealistic images for this specific article. Return ONLY valid JSON (no markdown fences):

{{
  "images": [
    {{
      "slot": "hero",
      "placement": "after_h1",
      "prompt": "Rich, specific photo brief: subject + setting + composition + lighting/mood",
      "alt": "125-200 char factual alt text aligned to target query",
      "title": "Short image title",
      "caption": "1-2 sentence figcaption for AI crawlers and readers"
    }}
  ]
}}

RULES:
- slot: hero | inline_1 | inline_2 ; placement: after_h1 | after_h2_index (0-based h2_index for inline)
- Plan exactly {max_images} images (hero first, then inline after key H2 sections).

VARIETY IS REQUIRED — the biggest failure is every article getting the same generic "technician next to an elevator" photo. Instead:
- Derive each image's SUBJECT from what THIS article/section is actually about. Examples by theme: modernization → a sleek, newly-renovated cab interior with modern fixtures; inspection/code/compliance → an inspector reviewing documentation or a certificate on the wall; cost/contracts → a building manager reviewing plans at a desk; emergency/repair → a service van or a technician responding on-site; vertical (hospital/hotel/office/multifamily) → that specific building type's lobby and elevators; maintenance → hands servicing machine-room equipment. Choose subjects that fit the real headings.
- Each of the {max_images} images must be visually DIFFERENT from the others: vary subject, setting, angle, and distance. Hero = a wide establishing shot; inline images = closer detail/context shots. Never repeat the same scene.
- Reflect the brand's locale where natural ({markets}) — realistic North American commercial/residential settings, not generic stock.
- Vary lighting/time-of-day/composition between images for a non-templated feel.

Every prompt must include: no on-image text, no watermarks, no brand logos or signage (text and logos render unreliably).
- alt and caption must be factual and include target-query terms where natural.

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
        markets = ", ".join(brand.markets) if brand.markets else "the United States"
        prompt = IMAGE_PLAN_PROMPT.format(
            brand_name=brand.name,
            markets=markets,
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
