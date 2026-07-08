"""Generate, upload, and inject AEO content images."""

import logging
from dataclasses import dataclass

from slugify import slugify

from app.config import get_settings
from app.models.brand import Brand
from app.services.image_plan_service import ImagePlanService
from app.services.fal_image_service import FalImageService
from app.services.openai_image_service import OpenAIImageService
from app.services.content_enrichment import inject_content_images
from app.services.wordpress_service import WordPressService

logger = logging.getLogger(__name__)


def _make_image_provider(settings):
    """Pick the configured image provider; fall back to any other configured
    one (logged) so a misconfig never silently stops image generation."""
    want = (settings.image_provider or "fal").lower()
    providers = {"fal": FalImageService(), "openai": OpenAIImageService()}
    chosen = providers.get(want) or providers["fal"]
    if chosen.is_configured():
        return chosen
    for name, provider in providers.items():
        if name != want and provider.is_configured():
            logger.warning("Image provider %r not configured — falling back to %r", want, name)
            return provider
    return chosen  # none configured; the is_configured() gate will skip


@dataclass
class ImagePipelineResult:
    html: str
    images_json: list[dict]
    featured_media_id: int | None
    status: str  # ok | skipped | no_plan | partial | failed


class ContentImagePipeline:
    def __init__(self):
        self.settings = get_settings()
        self.planner = ImagePlanService()
        self.image = _make_image_provider(self.settings)
        self.wp = WordPressService()

    def should_run(self) -> bool:
        return bool(self.settings.image_generation_enabled and self.image.is_configured())

    async def enrich_with_images(
        self,
        html: str,
        brand: Brand,
        target_query: str,
        content_type: str,
        draft_title: str,
    ) -> ImagePipelineResult:
        if not self.settings.image_generation_enabled:
            return ImagePipelineResult(html, [], None, "skipped")
        if not self.image.is_configured():
            logger.info("Image generation skipped — no image-provider key set (image_provider=%s)", self.settings.image_provider)
            return ImagePipelineResult(html, [], None, "skipped")
        if not self.settings.wp_publish_configured(brand.id):
            logger.info("Image generation skipped — no WP creds for brand %s", brand.id)
            return ImagePipelineResult(html, [], None, "skipped")

        try:
            plans = await self.planner.plan_images(html, target_query, brand, content_type)
            if not plans:
                # Config was fine (all 3 gates above passed) — Claude just
                # didn't return a usable image plan this attempt. Distinct
                # from "skipped" so reviewers get an accurate diagnosis
                # instead of a false "no OpenAI key or WP creds" message.
                return ImagePipelineResult(html, [], None, "no_plan")

            resolved: list[dict] = []
            featured_media_id: int | None = None

            for i, plan in enumerate(plans):
                slot = plan.get("slot", f"inline_{i}")
                try:
                    image_bytes, ext = await self.image.generate_image(plan["prompt"])
                    base_name = slugify(f"{draft_title}-{slot}", max_length=60) or "aeo-image"
                    filename = f"{base_name}.{ext}"
                    alt_text = (plan.get("alt") or plan["prompt"])[:200]
                    caption = (plan.get("caption") or alt_text)[:500]
                    title = (plan.get("title") or alt_text)[:200]

                    media = await self.wp.upload_media(
                        brand=brand,
                        image_bytes=image_bytes,
                        filename=filename,
                        alt_text=alt_text,
                        caption=caption,
                        description=caption,
                    )
                    entry = {
                        "slot": slot,
                        "wp_media_id": media["media_id"],
                        "url": media["source_url"],
                        "alt": alt_text,
                        "title": title,
                        "caption": caption,
                        "prompt": plan["prompt"],
                        "placement": plan.get("placement", "after_h1"),
                        "h2_index": plan.get("h2_index"),
                    }
                    resolved.append(entry)
                    if slot == "hero" or i == 0:
                        featured_media_id = media["media_id"]
                except Exception:
                    logger.exception("Failed to generate/upload image slot %s", slot)

            if not resolved:
                return ImagePipelineResult(html, [], None, "failed")

            enriched = inject_content_images(html, resolved)
            status = "ok" if len(resolved) == len(plans) else "partial"
            return ImagePipelineResult(enriched, resolved, featured_media_id, status)
        except Exception:
            logger.exception("Image pipeline failed for brand %s", brand.id)
            return ImagePipelineResult(html, [], None, "failed")
