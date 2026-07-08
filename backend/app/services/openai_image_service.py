"""OpenAI image generation for AEO content."""

import base64
import logging

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.cost_service import record_cost_event
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)


class OpenAIImageService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model = settings.openai_image_model
        self.size = settings.openai_image_size
        self.quality = settings.openai_image_quality
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    async def generate_image(self, prompt: str) -> tuple[bytes, str]:
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY not configured")

        async def do_request():
            response = await self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=self.size,
                quality=self.quality,
                n=1,
            )
            item = response.data[0]
            if item.b64_json:
                return base64.b64decode(item.b64_json), "png"
            if item.url:
                import httpx

                async with httpx.AsyncClient(timeout=60.0) as client:
                    img = await client.get(item.url)
                    img.raise_for_status()
                    return img.content, "png"
            raise RuntimeError("OpenAI image response had no b64_json or url")

        result = await retry_with_backoff(do_request, max_retries=2)
        await record_cost_event("openai", "image_generation", units=1, model=self.model)
        return result
