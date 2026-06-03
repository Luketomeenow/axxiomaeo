import logging
from datetime import datetime

import httpx
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.approval import WorkerError
from app.models.brand import Brand
from app.models.content import ContentPiece
from app.models.schema_job import SchemaDeployment, SchemaJob
from app.services.notification_service import NotificationService
from app.services.schema_service import build_combined_schema

logger = logging.getLogger(__name__)


async def run_schema_validation():
    logger.info("Starting monthly schema validation")
    async with AsyncSessionLocal() as session:
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
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(piece.wp_post_url)
                            has_schema = 'type="application/ld+json"' in resp.text

                        if has_schema:
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
                        else:
                            schema_json, schema_types = build_combined_schema(
                                "", brand, piece.title or "", piece.content_type or "faq_hub"
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
                            session.add(
                                SchemaJob(
                                    brand_id=brand.id,
                                    wp_post_id=piece.wp_post_id,
                                    wp_post_url=piece.wp_post_url,
                                    validation_status="error",
                                    error_details="Missing JSON-LD — regeneration pending review",
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
            session.add(WorkerError(worker_name="schema_validation", error_message=str(e)))
            await session.commit()
