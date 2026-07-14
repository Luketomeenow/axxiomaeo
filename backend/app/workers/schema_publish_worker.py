"""Daily schema auto-publish (1 brand-schema per brand, per day).

Gated behind SCHEMA_AUTO_PUBLISH_ENABLED (default false). When on, each run
publishes at most one missing or outdated brand-level schema per brand straight
to its WordPress site as a noindex carrier page, then announces it on Discord.

It's self-healing and idempotent: the desired set (Organization, LocalBusiness,
5 Services) has deterministic titles/slugs, so the worker publishes the first
slot that is missing or whose JSON-LD has drifted from the brand's current
settings, and does nothing once every slot is live and current. The manual
Schema Approval Inbox keeps working alongside this.
"""

import logging
from datetime import datetime

from slugify import slugify
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.schema_job import SchemaDeployment, SchemaJob
from app.services.notification_service import NotificationService, record_worker_error
from app.services.schema_service import build_brand_schema_set
from app.services.wordpress_service import WordPressService, schema_carrier_meta

logger = logging.getLogger(__name__)


def _slug_for(brand_id: str, item: dict) -> str:
    """Deterministic carrier-page slug per schema slot (matches the manual
    approve path's _deployment_slug, so both target the same WordPress page)."""
    schema_type = item["schema_type"]
    if schema_type == "Organization":
        return f"schema-organization-{brand_id}"
    if schema_type == "LocalBusiness":
        return f"schema-localbusiness-{brand_id}"
    if schema_type == "Service":
        service_name = item["title"].split(" - ", 1)[-1].strip()
        return slugify(f"schema-service-{service_name}-{brand_id}", max_length=80)
    return slugify(f"schema-{schema_type.lower()}-{brand_id}", max_length=80)


def _pick_target(desired: list[dict], existing: dict[str, SchemaDeployment]):
    """First slot that needs publishing: never deployed, deployed but the
    JSON-LD changed, or recorded without a live URL. None => brand is current."""
    for item in desired:
        dep = existing.get(item["title"])
        if (
            dep is None
            or not dep.wp_post_url
            or (dep.schema_json or "").strip() != item["schema_json"].strip()
        ):
            return item, dep
    return None, None


async def _publish_one(wp: WordPressService, brand: Brand, item: dict, dep: SchemaDeployment | None) -> dict:
    """Create or update the brand's carrier page for this schema slot."""
    schema_json = item["schema_json"]
    post_id = dep.wp_post_id if dep else None

    # Reuse an existing carrier page (recorded or found by slug) so re-runs
    # update in place instead of creating duplicate WordPress pages.
    if not post_id:
        found = await wp.find_by_slug(brand, _slug_for(brand.id, item), post_type="pages")
        if found:
            post_id = found["id"]

    if post_id:
        result = await wp.update_post(brand, post_id, schema_json=schema_json, post_type="pages")
        # update_post doesn't carry the noindex meta — re-assert it (matches approve).
        await wp._request(brand, "POST", f"pages/{post_id}", json={"meta": schema_carrier_meta()})
        return result

    return await wp.create_post(
        brand=brand,
        title=item["title"],
        content="",
        slug=_slug_for(brand.id, item),
        schema_json=schema_json,
        post_type="pages",
        noindex=True,
    )


async def run_daily_schema_publish():
    settings = get_settings()
    if not settings.schema_auto_publish_enabled:
        logger.info("Daily schema publish disabled (SCHEMA_AUTO_PUBLISH_ENABLED=false)")
        return

    logger.info("Starting daily schema publish (up to 1 per brand)")
    wp = WordPressService()

    async with AsyncSessionLocal() as session:
        brands = list((await session.execute(select(Brand).order_by(Brand.id))).scalars().all())

    for brand in brands:
        # One session per brand: a failure on one brand can't roll back a
        # publish that already hit WordPress for another.
        async with AsyncSessionLocal() as session:
            try:
                desired = build_brand_schema_set(brand)

                rows = await session.execute(
                    select(SchemaDeployment)
                    .where(
                        SchemaDeployment.brand_id == brand.id,
                        SchemaDeployment.status == "approved",
                    )
                    .order_by(SchemaDeployment.created_at.asc())
                )
                existing: dict[str, SchemaDeployment] = {}
                for d in rows.scalars().all():
                    if d.title:
                        existing[d.title] = d  # newest wins (ascending order)

                item, dep = _pick_target(desired, existing)
                if item is None:
                    logger.info("Schema for %s already current — nothing to publish", brand.id)
                    continue

                result = await _publish_one(wp, brand, item, dep)
                post_id = result.get("post_id")
                post_url = result.get("post_url")

                if dep is None:
                    dep = SchemaDeployment(
                        brand_id=brand.id,
                        schema_type=item["schema_type"],
                        title=item["title"],
                    )
                    session.add(dep)
                dep.schema_json = item["schema_json"]
                dep.status = "approved"
                dep.reviewer_id = "auto-schema"
                dep.wp_post_id = post_id
                dep.wp_post_url = post_url
                await session.flush()  # populate dep.id for the notification link

                # Deployed with valid JSON-LD (the mu-plugin renders it on all 5
                # brands). Schema Health's validation crawl is the ground-truth
                # re-check; this row keeps freshly-published pages accurate.
                session.add(
                    SchemaJob(
                        brand_id=brand.id,
                        wp_post_id=post_id,
                        wp_post_url=post_url,
                        schema_types=[item["schema_type"]],
                        validation_status="valid",
                        deployed_at=datetime.utcnow(),
                    )
                )

                # type="published" is what fans out to the Discord channel.
                await NotificationService(session).create(
                    type="published",
                    title=f"Schema published: {brand.name} — {item['schema_type']}",
                    body=post_url or "",
                    entity_type="schema_deployment",
                    entity_id=dep.id,
                )
                await session.commit()
                logger.info(
                    "Auto-published %s schema for %s → %s", item["schema_type"], brand.id, post_url
                )
            except Exception as e:
                logger.exception("Daily schema publish failed for %s: %s", brand.id, e)
                await record_worker_error(session, "daily_schema_publish", f"{brand.id}: {e}")
                await session.commit()
