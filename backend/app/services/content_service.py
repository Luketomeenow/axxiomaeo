import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalEvent
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece, ContentQueue
from app.models.schema_job import SchemaJob
from app.services.claude_service import ClaudeService, validate_answer_first
from app.services.notification_service import NotificationService
from app.services.schema_service import build_combined_schema
from app.services.wordpress_service import WordPressService
from app.utils.helpers import count_words, h2_question_ratio

logger = logging.getLogger(__name__)


class ContentGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.claude = ClaudeService()
        self.wp = WordPressService()
        self.notifications = NotificationService(db)

    async def generate_draft(
        self,
        brand_id: str,
        content_type: str,
        target_query: str,
        title: str = "",
        queue_id: int | None = None,
        city: str = "",
        state: str = "",
    ) -> ContentDraft:
        brand = await self.db.get(Brand, brand_id)
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")

        draft = ContentDraft(
            brand_id=brand_id,
            content_type=content_type,
            target_query=target_query,
            title=title or target_query,
            status="generating",
            queue_id=queue_id,
        )
        self.db.add(draft)
        await self.db.flush()

        html_content = ""
        is_valid = False
        failure_reason = ""

        for attempt in range(2):
            if attempt == 0:
                html_content = await self.claude.generate_content(
                    content_type=content_type,
                    brand_name=brand.name,
                    target_query=target_query,
                    markets=brand.markets or [],
                    title=title,
                    city=city,
                    state=state,
                )
            else:
                html_content = await self.claude.regenerate_with_correction(
                    failure_reason=failure_reason,
                    target_query=target_query,
                    brand_name=brand.name,
                    previous_content=html_content,
                )

            is_valid, failure_reason = await validate_answer_first(html_content, target_query)
            draft.validation_attempts = attempt + 1
            if is_valid:
                break

        schema_json, schema_types = build_combined_schema(
            html_content, brand, draft.title or target_query, content_type
        )
        slug = self.wp.generate_slug(draft.title or target_query, brand.name)

        draft.html_content = html_content
        draft.schema_json = schema_json
        draft.slug = slug
        ratio, h2_questions, h2_total = h2_question_ratio(html_content)
        draft.validation_result = {
            "valid": is_valid,
            "reason": failure_reason,
            "schema_types": schema_types,
            "word_count": count_words(html_content),
            "h2_question_ratio": round(ratio, 2),
            "h2_questions": h2_questions,
            "h2_total": h2_total,
        }

        if is_valid:
            draft.status = "pending_review"
            await self.notifications.create(
                type="draft_ready",
                title=f"Content ready for review: {draft.title}",
                body=f"Brand: {brand.name} | Query: {target_query}",
                entity_type="content_draft",
                entity_id=draft.id,
            )
        else:
            draft.status = "needs_review"
            await self.notifications.create(
                type="validation_failed",
                title=f"Content needs manual review: {draft.title}",
                body=f"Validation failed after 2 attempts: {failure_reason}",
                entity_type="content_draft",
                entity_id=draft.id,
            )

        if queue_id:
            queue_item = await self.db.get(ContentQueue, queue_id)
            if queue_item:
                queue_item.status = "ready" if is_valid else "needs_review"

        await self.db.flush()
        return draft

    async def approve_and_publish(self, draft_id: int, user_id: str) -> ContentPiece:
        draft = await self.db.get(ContentDraft, draft_id)
        if not draft:
            raise ValueError("Draft not found")
        if draft.status not in ("pending_review", "needs_review", "approved"):
            raise ValueError(f"Cannot publish draft in status: {draft.status}")

        brand = await self.db.get(Brand, draft.brand_id)
        if not brand:
            raise ValueError("Brand not found")

        existing = await self.db.execute(
            select(ContentPiece).where(
                ContentPiece.brand_id == draft.brand_id,
                ContentPiece.slug == draft.slug,
            )
        )
        piece = existing.scalar_one_or_none()

        if piece and piece.wp_post_id:
            result = await self.wp.update_post(
                brand, piece.wp_post_id, draft.html_content or "", draft.schema_json or ""
            )
        else:
            result = await self.wp.create_post(
                brand=brand,
                title=draft.title or "",
                content=draft.html_content or "",
                slug=draft.slug or "",
                schema_json=draft.schema_json or "",
            )

        schema_types = (draft.validation_result or {}).get("schema_types", [])
        if piece:
            piece.status = "published"
            piece.last_refreshed_at = datetime.utcnow()
            piece.wp_post_url = result.get("post_url")
        else:
            piece = ContentPiece(
                brand_id=draft.brand_id,
                content_type=draft.content_type,
                title=draft.title,
                target_query=draft.target_query,
                slug=draft.slug,
                wp_post_id=result.get("post_id"),
                wp_post_url=result.get("post_url"),
                word_count=count_words(draft.html_content or ""),
                schema_types=schema_types,
                status="published",
                published_at=datetime.utcnow(),
            )
            self.db.add(piece)

        draft.status = "published"
        draft.reviewer_id = user_id

        if draft.queue_id:
            queue_item = await self.db.get(ContentQueue, draft.queue_id)
            if queue_item:
                queue_item.status = "done"

        self.db.add(
            ApprovalEvent(
                entity_type="content_draft",
                entity_id=draft_id,
                action="approved",
                user_id=user_id,
            )
        )

        await self.wp.ping_bing_sitemap(brand)
        await self.notifications.create(
            type="published",
            title=f"Published: {draft.title}",
            body=f"Live at {result.get('post_url')}",
            entity_type="content_draft",
            entity_id=draft_id,
        )
        await self.db.flush()
        return piece

    async def reject_draft(self, draft_id: int, user_id: str, notes: str = "") -> ContentDraft:
        draft = await self.db.get(ContentDraft, draft_id)
        if not draft:
            raise ValueError("Draft not found")
        draft.status = "rejected"
        draft.reviewer_id = user_id
        draft.review_notes = notes
        self.db.add(
            ApprovalEvent(
                entity_type="content_draft",
                entity_id=draft_id,
                action="rejected",
                user_id=user_id,
                notes=notes,
            )
        )
        await self.db.flush()
        return draft
