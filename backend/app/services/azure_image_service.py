"""Azure OpenAI image generation (gpt-image-2) for AEO content.

Calls the Azure OpenAI images endpoint:
    POST {AZURE_IMAGE_ENDPOINT}
    api-key: <AZURE_IMAGE_API_KEY>
    body: {"prompt", "model": <deployment>, "size", "quality", "n": 1}

gpt-image models return the image as base64 (data[0].b64_json); we decode it to
bytes. Contract matches the other providers: is_configured() -> bool and
generate_image(prompt) -> (bytes, ext).
"""

import asyncio
import base64
import logging

import httpx

from app.config import get_settings
from app.services.cost_service import record_cost_event

logger = logging.getLogger(__name__)


def _parse_retry_after(headers) -> float | None:
    val = headers.get("retry-after")
    if not val:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


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

        body = {
            "prompt": prompt,
            "model": self.deployment,
            "size": self.size,
            "quality": self.quality,
            "n": 1,
        }
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        last_error: Exception | None = None

        # gpt-image-2 on lower tiers has a small per-minute rate limit, and we
        # generate ~3 images/article back-to-back. On 429 we wait it out (honoring
        # Retry-After) so a burst self-throttles instead of losing images; other
        # 4xx raise immediately; transient network errors get a short backoff.
        for attempt in range(5):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    resp = await client.post(self.endpoint, headers=headers, json=body)
                    if resp.status_code == 429:
                        wait = _parse_retry_after(resp.headers) or min(15 * (attempt + 1), 60)
                        logger.warning(
                            "Azure image rate-limited (429) — waiting %.0fs (attempt %d/5)", wait, attempt + 1
                        )
                        last_error = RuntimeError(f"Azure image rate limited (429): {resp.text[:200]}")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status_code >= 400:
                        raise RuntimeError(f"Azure image generate failed ({resp.status_code}): {resp.text[:300]}")
                    data = resp.json()
                    items = data.get("data") or []
                    if not items or not isinstance(items[0], dict):
                        raise RuntimeError(f"Azure image returned no data: {str(data)[:200]}")
                    item = items[0]
                    if item.get("b64_json"):
                        result = (base64.b64decode(item["b64_json"]), "png")
                    elif item.get("url"):
                        dl = await client.get(item["url"])
                        dl.raise_for_status()
                        result = (dl.content, "png")
                    else:
                        raise RuntimeError("Azure image response had no b64_json or url")
                await record_cost_event("azure", "image_generation", units=1, model=self.deployment)
                return result
            except RuntimeError:
                raise  # non-429 API/response error — don't retry
            except Exception as e:  # transient network/timeout
                last_error = e
                await asyncio.sleep(2 * (attempt + 1))

        raise last_error or RuntimeError("Azure image generation failed after retries")
