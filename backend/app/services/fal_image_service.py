"""fal.ai image generation (Flux 2 Pro / Imagen 4) for AEO content.

fal.ai's sync endpoint (https://fal.run/<model>) returns the result directly
for fast image models. We handle a queue/async response defensively too, in
case a model routes long jobs through the queue.

Contract matches OpenAIImageService: is_configured() -> bool and
generate_image(prompt) -> (bytes, ext).
"""

import asyncio
import logging

import httpx

from app.config import get_settings
from app.services.cost_service import record_cost_event
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)

_SYNC_BASE = "https://fal.run"
_QUEUE_BASE = "https://queue.fal.run"


def _ext_from_content_type(content_type: str | None, fallback: str) -> str:
    if not content_type:
        return fallback
    ct = content_type.lower()
    if "png" in ct:
        return "png"
    if "webp" in ct:
        return "webp"
    if "jpeg" in ct or "jpg" in ct:
        return "jpg"
    return fallback


class FalImageService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.fal_api_key
        self.model = settings.fal_image_model
        self.image_size = settings.fal_image_size
        self.output_format = settings.fal_output_format

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"}

    async def _await_queue_result(self, client: httpx.AsyncClient, data: dict) -> dict:
        """If fal routed this to the queue, poll status then fetch the result."""
        status_url = data.get("status_url") or (
            f"{_QUEUE_BASE}/{self.model}/requests/{data['request_id']}/status"
            if data.get("request_id") else None
        )
        result_url = data.get("response_url") or (
            f"{_QUEUE_BASE}/{self.model}/requests/{data['request_id']}"
            if data.get("request_id") else None
        )
        if not status_url or not result_url:
            raise RuntimeError(f"fal queue response missing request id: {str(data)[:200]}")
        for _ in range(60):  # ~5 min at 5s
            st = (await client.get(status_url, headers={"Authorization": f"Key {self.api_key}"})).json()
            if st.get("status") == "COMPLETED":
                return (await client.get(result_url, headers={"Authorization": f"Key {self.api_key}"})).json()
            if st.get("status") in ("FAILED", "ERROR"):
                raise RuntimeError(f"fal queue job failed: {str(st)[:200]}")
            await asyncio.sleep(5)
        raise RuntimeError("fal queue job not completed in time")

    async def generate_image(self, prompt: str) -> tuple[bytes, str]:
        if not self.api_key:
            raise RuntimeError("FAL_API_KEY not configured")

        async def do_request():
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                resp = await client.post(
                    f"{_SYNC_BASE}/{self.model}",
                    headers=self._headers(),
                    json={
                        "prompt": prompt,
                        "image_size": self.image_size,
                        "output_format": self.output_format,
                        "enable_safety_checker": True,
                        "num_images": 1,
                    },
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"fal generate failed ({resp.status_code}): {resp.text[:300]}")
                data = resp.json()
                # Sync path returns {"images": [...]}; queue path returns a request id.
                if "images" not in data and (data.get("request_id") or data.get("status_url")):
                    data = await self._await_queue_result(client, data)
                images = data.get("images") or []
                if not images or not images[0].get("url"):
                    raise RuntimeError(f"fal returned no image url: {str(data)[:200]}")
                img = images[0]
                ext = _ext_from_content_type(img.get("content_type"), self.output_format)
                dl = await client.get(img["url"])
                dl.raise_for_status()
                return dl.content, ext

        result = await retry_with_backoff(do_request, max_retries=2)
        await record_cost_event("fal", "image_generation", units=1, model=self.model)
        return result
