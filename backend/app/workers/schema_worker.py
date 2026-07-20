import logging
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece
from app.models.schema_job import SchemaDeployment, SchemaJob
from app.services.content_service import _inject_brand_phone
from app.services.notification_service import NotificationService, record_worker_error
from app.services.schema_crawl import check_page_jsonld, new_crawl_client
from app.services.schema_service import build_combined_schema

logger = logging.getLogger(__name__)


async def run_schema_validation():
    logger.info("Starting monthly schema validation")
    async with AsyncSessionLocal() as session, new_crawl_client() as crawl_client:
        try:
            brands = await session.execute(select(Brand))
            notifications = NotificationService(session)

            for brand in brands.scalars().all():
                result = await session.execute(
                    select(ContentPiece).where(
                        ContentPiece.brand_id == brand.id,
                        ContentPiece.status == "published",
                    )
                )
                pieces = result.scalars().all()

                for piece in pieces:
                    if not piece.wp_post_url:
                        continue
                    try:
                        state, fetch_detail = await check_page_jsonld(crawl_client, piece.wp_post_url)

                        if state == "valid":
                            session.add(
                                SchemaJob(
                                    brand_id=brand.id,
                                    wp_post_id=piece.wp_post_id,
                                    wp_post_url=piece.wp_post_url,
                                    schema_types=piece.schema_types or [],
                                    validation_status="valid",
                                    validated_at=datetime.utcnow(),
                                )
                            )
                        elif state == "unreachable":
                            # Couldn't see the page (blocked/HTTP error) — that
                            # says nothing about its schema, so record the error
                            # without queuing a pointless regeneration.
                            session.add(
                                SchemaJob(
                                    brand_id=brand.id,
                                    wp_post_id=piece.wp_post_id,
                                    wp_post_url=piece.wp_post_url,
                                    validation_status="error",
                                    error_details=fetch_detail,
                                    validated_at=datetime.utcnow(),
                                )
                            )
                        else:
                            # Rebuild from the piece's stored draft HTML — building
                            # from an empty string yields a hollow Article-only schema.
                            draft_q = await session.execute(
                                select(ContentDraft)
                                .where(
                                    ContentDraft.brand_id == brand.id,
                                    ContentDraft.slug == piece.slug,
                                    ContentDraft.html_content.isnot(None),
                                )
                                .order_by(ContentDraft.updated_at.desc())
                                .limit(1)
                            )
                            draft = draft_q.scalar_one_or_none()
                            if draft and draft.html_content:
                                source_html = _inject_brand_phone(draft.html_content, brand.phone)
                                schema_json, schema_types = build_combined_schema(
                                    source_html, brand, piece.title or "", piece.content_type or "faq_hub"
                                )
                                session.add(
                                    SchemaDeployment(
                                        brand_id=brand.id,
                                        wp_post_id=piece.wp_post_id,
                                        wp_post_url=piece.wp_post_url,
                                        schema_type=",".join(schema_types),
                                        schema_json=schema_json,
                                        title=f"Regenerated schema: {piece.title}",
                                        status="pending_review",
                                    )
                                )
                                error_details = "Missing JSON-LD — regeneration pending review"
                            else:
                                error_details = (
                                    "Missing JSON-LD and no stored draft HTML — "
                                    "regenerate the content draft to rebuild schema"
                                )
                            session.add(
                                SchemaJob(
                                    brand_id=brand.id,
                                    wp_post_id=piece.wp_post_id,
                                    wp_post_url=piece.wp_post_url,
                                    validation_status="error",
                                    error_details=error_details,
                                    validated_at=datetime.utcnow(),
                                )
                            )
                    except Exception as e:
                        session.add(
                            SchemaJob(
                                brand_id=brand.id,
                                wp_post_id=piece.wp_post_id,
                                wp_post_url=piece.wp_post_url,
                                validation_status="error",
                                error_details=str(e),
                                validated_at=datetime.utcnow(),
                            )
                        )

            await notifications.create(
                type="schema_validation",
                title="Monthly schema validation complete",
                body="Review any pending schema deployments",
                entity_type="schema_deployment",
            )
            await session.commit()
            logger.info("Schema validation complete")
        except Exception as e:
            logger.exception("Schema validation failed: %s", e)
            await record_worker_error(session, "schema_validation", str(e))
            await session.commit()
