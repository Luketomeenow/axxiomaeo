"""Azure OpenAI image generation (gpt-image-2) for AEO content.

Calls the Azure OpenAI images endpoint:
    POST {AZURE_IMAGE_ENDPOINT}
    api-key: <AZURE_IMAGE_API_KEY>
    body: {"prompt", "model": <deployment>, "size", "quality", "n": 1}

gpt-image models return the image as base64 (data[0].b64_json); we decode it to
bytes. Contract matches the other providers: is_configured() -> bool and
generate_image(prompt) -> (bytes, ext).
"""

import base64
import logging

import httpx

from app.config import get_settings
from app.services.cost_service import record_cost_event
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)


class AzureImageService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.azure_image_api_key
        self.endpoint = settings.azure_image_endpoint
        self.deployment = settings.azure_image_deployment
        self.size = settings.azure_image_size
        self.quality = settings.azure_image_quality

    def is_configured(self) -> bool:
        return bool(self.api_key and self.endpoint)

    async def generate_image(self, prompt: str) -> tuple[bytes, str]:
        if not self.is_configured():
            raise RuntimeError("AZURE_IMAGE_API_KEY / AZURE_IMAGE_ENDPOINT not configured")

        async def do_request():
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                resp = await client.post(
                    self.endpoint,
                    headers={"api-key": self.api_key, "Content-Type": "application/json"},
                    json={
                        "prompt": prompt,
                        "model": self.deployment,
                        "size": self.size,
                        "quality": self.quality,
                        "n": 1,
                    },
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"Azure image generate failed ({resp.status_code}): {resp.text[:300]}")
                data = resp.json()
                items = data.get("data") or []
                if not items or not isinstance(items[0], dict):
                    raise RuntimeError(f"Azure image returned no data: {str(data)[:200]}")
                item = items[0]
                if item.get("b64_json"):
                    return base64.b64decode(item["b64_json"]), "png"
                if item.get("url"):
                    dl = await client.get(item["url"])
                    dl.raise_for_status()
                    return dl.content, "png"
                raise RuntimeError("Azure image response had no b64_json or url")

        result = await retry_with_backoff(do_request, max_retries=2)
        await record_cost_event("azure", "image_generation", units=1, model=self.deployment)
        return result
