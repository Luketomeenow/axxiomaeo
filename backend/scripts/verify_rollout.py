#!/usr/bin/env python3
"""Verify AEO/GEO rollout readiness: DB, WordPress API, GEO tracker, MU plugin hint."""
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


async def main():
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

    print("\nNext steps: wordpress/ROLLOUT_VERIFICATION.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
