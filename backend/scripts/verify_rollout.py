#!/usr/bin/env python3
"""Verify AEO/GEO rollout readiness: DB, WordPress API, GEO tracker, MU plugin hint, images."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal, check_db_connection
from app.models.brand import Brand
from app.services.citation_service import CitationService
from app.services.openai_image_service import OpenAIImageService


async def check_wordpress(brand: Brand) -> dict:
    settings = get_settings()
    if not settings.wp_publish_configured(brand.id):
        return {"brand": brand.id, "ok": False, "detail": "WP credentials not configured"}
    url = brand.wp_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(f"{url}/wp-json/wp/v2/pages?per_page=1")
            if resp.status_code != 200:
                return {"brand": brand.id, "ok": False, "detail": f"REST API {resp.status_code}"}
            # Probe a schema carrier or any page for MU plugin JSON-LD
            pages = resp.json()
            if pages:
                link = pages[0].get("link")
                if link:
                    page_resp = await client.get(link)
                    has_aeo = "aeo_schema_json" in page_resp.text or (
                        'type="application/ld+json"' in page_resp.text
                        and "Service" in page_resp.text
                    )
                    return {
                        "brand": brand.id,
                        "ok": True,
                        "detail": "REST OK",
                        "json_ld_on_sample_page": has_aeo,
                    }
            return {"brand": brand.id, "ok": True, "detail": "REST OK (no pages to probe)"}
    except Exception as e:
        return {"brand": brand.id, "ok": False, "detail": str(e)}


async def check_image_pipeline(test_image: bool) -> None:
    settings = get_settings()
    openai = OpenAIImageService()
    openai_ok = openai.is_configured()

    print("\nImage generation:")
    print(f"  [{'OK' if settings.image_generation_enabled else 'WARN'}] IMAGE_GENERATION_ENABLED="
          f"{settings.image_generation_enabled}")
    print(f"  [{'OK' if openai_ok else 'FAIL'}] OPENAI_API_KEY: "
          f"{'configured' if openai_ok else 'not set'} (model={settings.openai_image_model})")

    async with AsyncSessionLocal() as session:
        brands = list((await session.execute(select(Brand))).scalars().all())

    print(f"  Per brand (all 3 gates must pass for that brand's drafts to get images):")
    for brand in brands:
        wp_ok = settings.wp_publish_configured(brand.id)
        ready = settings.image_generation_enabled and openai_ok and wp_ok
        print(f"    [{'OK' if ready else 'WARN'}] {brand.id}: "
              f"WP creds {'configured' if wp_ok else 'MISSING'}")

    if not test_image:
        print("  (pass --test-image to run one real OpenAI generation, ~$0.02-0.19)")
        return
    if not openai_ok:
        print("  [SKIP] --test-image requested but OPENAI_API_KEY not set")
        return

    print("  Running one real test generation (no upload, bytes discarded)...")
    try:
        image_bytes = await openai.generate_image(
            "A clean, professional photo of a modern commercial elevator interior."
        )
        print(f"  [OK] Generated {len(image_bytes):,} bytes — OpenAI image generation is working")
    except Exception as e:
        print(f"  [FAIL] Generation failed: {e}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test-image", action="store_true",
        help="Also run one real OpenAI image generation to fully confirm access (small cost)",
    )
    args = parser.parse_args()

    settings = get_settings()
    print("=== Axxiom AEO Rollout Verification ===\n")

    try:
        await check_db_connection()
        print("[OK] Database connection")
    except Exception as e:
        print(f"[FAIL] Database: {e}")
        return 1

    cs = CitationService()
    tracker_ok = await cs.provider_available()
    provider = settings.citation_provider
    print(f"[{'OK' if tracker_ok else 'WARN'}] Citation provider ({provider}): "
          f"{'available' if tracker_ok else 'unavailable — set GEO_AEO_TRACKER_URL'}")

    async with AsyncSessionLocal() as session:
        brands = list((await session.execute(select(Brand))).scalars().all())

    print(f"\nWordPress ({len(brands)} brands):")
    for brand in brands:
        result = await check_wordpress(brand)
        status = "OK" if result["ok"] else "FAIL"
        extra = ""
        if result.get("json_ld_on_sample_page") is False:
            extra = " — no JSON-LD detected on sample page (install MU plugin?)"
        elif result.get("json_ld_on_sample_page"):
            extra = " — JSON-LD detected"
        print(f"  [{status}] {result['brand']}: {result['detail']}{extra}")

    await check_image_pipeline(args.test_image)

    print("\nNext steps: wordpress/ROLLOUT_VERIFICATION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
