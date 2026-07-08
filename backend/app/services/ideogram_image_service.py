"""Ideogram image generation (Ideogram 3.0) for AEO content.

The v3 generate endpoint (POST /v1/ideogram-v3/generate) takes
multipart/form-data (NOT JSON) and returns an ephemeral image URL at
data[0].url, which we download to bytes. Auth is the raw key in an `Api-Key`
header (no Bearer/Key prefix).

Contract matches the other providers: is_configured() -> bool and
generate_image(prompt) -> (bytes, ext).
"""

import logging

import httpx

from app.config import get_settings
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)


def _ext_from_content_type(content_type: str | None, fallback: str = "png") -> str:
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


class IdeogramImageService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.ideogram_api_key
        self.endpoint = settings.ideogram_endpoint
        self.aspect_ratio = settings.ideogram_aspect_ratio
        self.rendering_speed = settings.ideogram_rendering_speed
        self.style_type = settings.ideogram_style_type
        self.magic_prompt = settings.ideogram_magic_prompt

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate_image(self, prompt: str) -> tuple[bytes, str]:
        if not self.api_key:
            raise RuntimeError("IDEOGRAM_API_KEY not configured")

        async def do_request():
            # V3 requires multipart/form-data. Passing each field as a
            # (None, value) part makes httpx encode plain text fields as
            # multipart without any file upload — and it sets the
            # `multipart/form-data; boundary=...` Content-Type itself, so we
            # must NOT set Content-Type by hand.
            form = {
                "prompt": (None, prompt),
                "aspect_ratio": (None, self.aspect_ratio),
                "rendering_speed": (None, self.rendering_speed),
                "style_type": (None, self.style_type),
                "magic_prompt": (None, self.magic_prompt),
                "num_images": (None, "1"),
            }
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
                resp = await client.post(
                    self.endpoint,
                    headers={"Api-Key": self.api_key},
                    files=form,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"Ideogram generate failed ({resp.status_code}): {resp.text[:300]}")
                data = resp.json()
                images = data.get("data") or []
                url = images[0].get("url") if images and isinstance(images[0], dict) else None
                if not url:
                    raise RuntimeError(f"Ideogram returned no image url: {str(data)[:200]}")
                # URLs are ephemeral — download the bytes now.
                dl = await client.get(url)
                dl.raise_for_status()
                ext = _ext_from_content_type(dl.headers.get("content-type"), "png")
                return dl.content, ext

        return await retry_with_backoff(do_request, max_retries=2)
