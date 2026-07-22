import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.approval import ApprovalEvent
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece, ContentQueue
from app.services.claude_service import ClaudeService, validate_answer_first
from app.services.content_enrichment import (
    _brand_host,
    ensure_author_byline,
    ensure_tldr_block,
    inject_internal_links,
    normalize_article_headings,
    normalize_author_byline,
    sanitize_links,
    strip_phone_placeholder,
)
from app.services.link_verification import verify_external_links
from app.services.content_image_pipeline import ContentImagePipeline
from app.services.notification_service import NotificationService
from app.services.schema_service import build_combined_schema
from app.services.wordpress_service import WordPressService
from app.utils.helpers import count_words, h2_question_ratio

logger = logging.getLogger(__name__)

STALE_GENERATING_MINUTES = 3


async def _set_queue_status(queue_id: int, status: str) -> None:
    """Update queue row in a short separate transaction (avoids lock timeouts)."""
    from app.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            item = await session.get(ContentQueue, queue_id)
            if item:
                item.status = status
            await session.commit()
    except Exception:
        logger.exception("Failed to update queue %s → %s", queue_id, status)


async def recover_stale_generating_drafts(db: AsyncSession) -> int:
    """Mark abandoned generating drafts so the UI can offer Regenerate."""
    cutoff = datetime.utcnow() - timedelta(minutes=STALE_GENERATING_MINUTES)
    result = await db.execute(
        select(ContentDraft).where(
            ContentDraft.status == "generating",
            ContentDraft.created_at < cutoff,
        )
    )
    count = 0
    for draft in result.scalars():
        if draft.html_content:
            continue
        draft.status = "needs_review"
        draft.validation_result = {
            "valid": False,
            "reason": "Generation was interrupted or timed out. Use Regenerate to try again.",
        }
        if draft.queue_id:
            await _set_queue_status(draft.queue_id, "needs_review")
        count += 1
    if count:
        await db.flush()
        logger.info("Recovered %s stale generating draft(s)", count)
    return count


def _usable_phone(phone: str | None) -> str | None:
    cleaned = (phone or "").strip()
    if not cleaned or cleaned == "[BRAND_PHONE]":
        return None
    return cleaned


def _inject_brand_phone(html: str, phone: str | None) -> str:
    if not html:
        return html
    cleaned = _usable_phone(phone)
    if cleaned:
        return html.replace("[BRAND_PHONE]", cleaned)
    return strip_phone_placeholder(html)


def _known_paths(pages: list[dict]) -> set[str]:
    """Site-relative paths of a brand's existing WP posts/pages, normalized
    (no trailing slash) to match sanitize_links' internal-link check."""
    from urllib.parse import urlparse

    paths: set[str] = set()
    for page in pages or []:
        url = page.get("url") or ""
        path = urlparse(url).path.rstrip("/")
        if path:
            paths.add(path)
        slug = (page.get("slug") or "").strip("/")
        if slug:
            paths.add("/" + slug)
    return paths


class ContentGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.claude = ClaudeService()
        self.wp = WordPressService()
        self.notifications = NotificationService(db)

    def _resolve_publish_targets(
        self,
        draft_brand_id: str,
        brand_ids: list[str] | None,
        publish_all: bool,
    ) -> list[str]:
        if publish_all:
            configured = self.settings.wp_configured_brand_ids()
            if not configured:
                raise ValueError("No WordPress credentials configured for any brand")
            return configured

        if brand_ids:
            seen: set[str] = set()
            targets: list[str] = []
            for brand_id in brand_ids:
                if brand_id not in seen:
                    seen.add(brand_id)
                    targets.append(brand_id)
            return targets

        return [draft_brand_id]

    async def _publish_draft_to_brand(self, draft: ContentDraft, brand_id: str) -> dict:
        brand = await self.db.get(Brand, brand_id)
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")
        if not self.settings.wp_publish_configured(brand_id):
            raise ValueError(f"WordPress credentials not configured for {brand_id}")

        html_content = _inject_brand_phone(draft.html_content or "", brand.phone)
        html_content = normalize_article_headings(html_content, draft.title or "")
        html_content = normalize_author_byline(html_content, brand)
        # Last-gate cleanup of markdown/malformed links (existence-checked at
        # generation; here we just clean, so verified links survive).
        html_content = sanitize_links(html_content, brand)
        # External links are re-probed at publish time — a URL can die between
        # generation and approval, and this is the last gate before the web.
        html_content = await verify_external_links(html_content, skip_hosts={_brand_host(brand)})
        schema_json, schema_types = build_combined_schema(
            html_content,
            brand,
            draft.title or "",
            draft.content_type or "faq_hub",
        )
        slug = draft.slug or self.wp.generate_slug(draft.title or "", brand.name)

        existing = await self.db.execute(
            select(ContentPiece).where(
                ContentPiece.brand_id == brand_id,
                ContentPiece.slug == slug,
            )
        )
        piece = existing.scalar_one_or_none()

        if piece and piece.wp_post_id:
            try:
                result = await self.wp.update_post(
                    brand,
                    piece.wp_post_id,
                    html_content,
                    schema_json,
                    featured_media=draft.featured_media_id,
                )
            except ValueError as exc:
                if "invalid post id" not in str(exc).lower():
                    raise
                # Stored id is stale (post deleted/recreated on the WP side) —
                # self-heal by slug like the schema carrier does; if the slug
                # is gone from WP too, publish fresh instead of failing.
                live = await self.wp.find_by_slug(brand, slug)
                if live:
                    piece.wp_post_id = live["id"]
                    result = await self.wp.update_post(
                        brand,
                        live["id"],
                        html_content,
                        schema_json,
                        featured_media=draft.featured_media_id,
                    )
                else:
                    result = await self.wp.create_post(
                        brand=brand,
                        title=draft.title or "",
                        content=html_content,
                        slug=slug,
                        schema_json=schema_json,
                        featured_media=draft.featured_media_id,
                    )
        else:
            result = await self.wp.create_post(
                brand=brand,
                title=draft.title or "",
                content=html_content,
                slug=slug,
                schema_json=schema_json,
                featured_media=draft.featured_media_id,
            )

        if piece:
            piece.status = "published"
            piece.last_refreshed_at = datetime.utcnow()
            piece.wp_post_url = result.get("post_url")
            piece.wp_post_id = result.get("post_id") or piece.wp_post_id
        else:
            source_citation_id = None
            if draft.queue_id:
                queue_item = await self.db.get(ContentQueue, draft.queue_id)
                if queue_item:
                    source_citation_id = queue_item.source_citation_id
            piece = ContentPiece(
                brand_id=brand_id,
                content_type=draft.content_type,
                title=draft.title,
                target_query=draft.target_query,
                slug=slug,
                wp_post_id=result.get("post_id"),
                wp_post_url=result.get("post_url"),
                word_count=count_words(html_content),
                schema_types=schema_types,
                status="published",
                published_at=datetime.utcnow(),
                source_citation_id=source_citation_id,
            )
            self.db.add(piece)

        await self.wp.ping_bing_sitemap(brand)
        return {
            "post_id": result.get("post_id"),
            "post_url": result.get("post_url"),
            "brand_id": brand_id,
        }

    async def generate_draft(
        self,
        brand_id: str,
        content_type: str,
        target_query: str,
        title: str = "",
        queue_id: int | None = None,
        city: str = "",
        state: str = "",
        existing_draft_id: int | None = None,
    ) -> ContentDraft:
        brand = await self.db.get(Brand, brand_id)
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")

        brand_name = brand.name
        brand_markets = brand.markets or []
        brand_phone = brand.phone
        draft_title = title or target_query

        if existing_draft_id:
            draft = await self.db.get(ContentDraft, existing_draft_id)
            if not draft:
                raise ValueError(f"Draft {existing_draft_id} not found")
            draft.status = "generating"
            draft.html_content = None
            draft.schema_json = None
            draft.slug = None
            draft.validation_result = None
            draft.validation_attempts = 0
            draft.images_json = []
            draft.featured_media_id = None
            draft_id = draft.id
            queue_id = draft.queue_id or queue_id
        else:
            draft = ContentDraft(
                brand_id=brand_id,
                content_type=content_type,
                target_query=target_query,
                title=draft_title,
                status="generating",
                queue_id=queue_id,
            )
            self.db.add(draft)
            await self.db.flush()
            draft_id = draft.id

        # Commit before Claude — Supabase statement timeout kills long open transactions.
        await self.db.commit()

        html_content = ""
        is_valid = False
        failure_reason = ""
        validation_attempts = 0

        try:
            for attempt in range(2):
                validation_attempts = attempt + 1
                if attempt == 0:
                    html_content = await self.claude.generate_content(
                        content_type=content_type,
                        brand_name=brand_name,
                        target_query=target_query,
                        markets=brand_markets,
                        title=title,
                        city=city,
                        state=state,
                    )
                else:
                    html_content = await self.claude.regenerate_with_correction(
                        failure_reason=failure_reason,
                        target_query=target_query,
                        brand_name=brand_name,
                        previous_content=html_content,
                    )

                is_valid, failure_reason = await validate_answer_first(
                    html_content, target_query, content_type
                )
                if is_valid:
                    break
        except Exception as exc:
            logger.exception("Claude generation failed for draft %s", draft_id)
            draft = await self.db.get(ContentDraft, draft_id)
            if draft:
                draft.status = "needs_review"
                draft.validation_attempts = validation_attempts
                draft.validation_result = {
                    "valid": False,
                    "reason": str(exc),
                }
                await self.db.flush()
                await self.db.commit()
                if queue_id:
                    await _set_queue_status(queue_id, "needs_review")
            raise

        phone_missing = "[BRAND_PHONE]" in html_content and not _usable_phone(brand_phone)
        html_content = _inject_brand_phone(html_content, brand_phone)

        brand = await self.db.get(Brand, brand_id)
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")

        related_posts = await self.wp.get_existing_pages(brand, post_type="posts")
        related_pages = await self.wp.get_existing_pages(brand, post_type="pages")
        related = (related_posts + related_pages)[:8]
        html_content = ensure_tldr_block(html_content, target_query)
        html_content = ensure_author_byline(html_content, brand, brand.author_name)
        html_content = inject_internal_links(html_content, brand, related)
        # Drop any invented/broken links the model wrote before they can 404 —
        # internal links validated against the brand's real published
        # pages/posts, external links probed against the live web.
        html_content = sanitize_links(html_content, brand, _known_paths(related_posts + related_pages))
        html_content = await verify_external_links(html_content, skip_hosts={_brand_host(brand)})

        image_pipeline = ContentImagePipeline()
        image_result = await image_pipeline.enrich_with_images(
            html_content,
            brand,
            target_query,
            content_type,
            draft_title,
        )
        html_content = image_result.html
        images_json = image_result.images_json
        featured_media_id = image_result.featured_media_id
        images_status = image_result.status

        html_content = normalize_article_headings(html_content, draft_title)
        schema_json, schema_types = build_combined_schema(
            html_content, brand, draft_title, content_type
        )
        slug = self.wp.generate_slug(draft_title, brand_name)

        draft = await self.db.get(ContentDraft, draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found after generation")

        draft.html_content = html_content
        draft.schema_json = schema_json
        draft.slug = slug
        draft.images_json = images_json
        draft.featured_media_id = featured_media_id
        draft.validation_attempts = validation_attempts
        ratio, h2_questions, h2_total = h2_question_ratio(html_content)
        image_count = len(images_json)
        draft.validation_result = {
            "valid": is_valid,
            "reason": failure_reason,
            "schema_types": schema_types,
            "word_count": count_words(html_content),
            "h2_question_ratio": round(ratio, 2),
            "h2_questions": h2_questions,
            "h2_total": h2_total,
            "images_status": images_status,
            "image_count": image_count,
            "images_with_alt": sum(1 for img in images_json if img.get("alt")),
            # Reviewer heads-up: CTAs were de-phoned because the brand has no
            # phone configured — set one in Brand Settings and regenerate.
            "phone_missing": phone_missing,
        }

        if is_valid:
            draft.status = "pending_review"
            await self.notifications.create(
                type="draft_ready",
                title=f"Content ready for review: {draft.title}",
                body=f"Brand: {brand_name} | Query: {target_query}",
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

        await self.db.flush()
        await self.db.commit()

        if queue_id:
            await _set_queue_status(queue_id, "ready" if is_valid else "needs_review")

        draft = await self.db.get(ContentDraft, draft_id)
        return draft

    async def approve_and_publish(
        self,
        draft_id: int,
        user_id: str,
        brand_ids: list[str] | None = None,
        publish_all: bool = False,
    ) -> dict:
        draft = await self.db.get(ContentDraft, draft_id)
        if not draft:
            raise ValueError("Draft not found")
        if draft.status not in ("pending_review", "approved"):
            raise ValueError(f"Cannot publish draft in status: {draft.status}")
        if draft.validation_result and draft.validation_result.get("valid") is False:
            raise ValueError(
                "Cannot publish: validation failed. Fix content or regenerate before publishing."
            )

        targets = self._resolve_publish_targets(draft.brand_id, brand_ids, publish_all)
        results: list[dict] = []

        for brand_id in targets:
            try:
                published = await self._publish_draft_to_brand(draft, brand_id)
                results.append({**published, "error": None})
            except Exception as exc:
                logger.exception("Publish failed for draft %s → %s", draft_id, brand_id)
                results.append({"brand_id": brand_id, "post_id": None, "post_url": None, "error": str(exc)})

        successes = [r for r in results if not r.get("error")]
        if not successes:
            errors = "; ".join(f"{r['brand_id']}: {r['error']}" for r in results)
            raise ValueError(f"Publish failed for all targets. {errors}")

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

        urls = [r["post_url"] for r in successes if r.get("post_url")]
        await self.notifications.create(
            type="published",
            title=f"Published: {draft.title}",
            body="; ".join(urls) if urls else f"Published to {len(successes)} site(s)",
            entity_type="content_draft",
            entity_id=draft_id,
        )
        await self.db.flush()

        skipped = [r for r in results if r.get("error")]
        return {
            "status": "published",
            "published_count": len(successes),
            "results": results,
            "post_id": successes[0].get("post_id"),
            "post_url": successes[0].get("post_url"),
            "skipped": skipped,
        }

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

    async def return_to_review(self, piece_id: int, user_id: str) -> dict:
        """Unpublish a published piece: set its live WP post back to draft and
        return the originating draft to pending_review."""
        piece = await self.db.get(ContentPiece, piece_id)
        if not piece:
            raise ValueError("Published item not found")
        if piece.status != "published":
            raise ValueError(f"Item is not published (status: {piece.status})")

        brand = await self.db.get(Brand, piece.brand_id)
        wp_set_to_draft = False
        if brand and piece.wp_post_id:
            try:
                await self.wp.set_post_status(brand, piece.wp_post_id, "draft")
                wp_set_to_draft = True
            except Exception:
                logger.exception(
                    "Failed to set WP post %s (%s) to draft", piece.wp_post_id, piece.brand_id
                )
        piece.status = "unpublished"

        # Return the originating draft to the review inbox so it can be re-approved.
        draft = None
        if piece.slug:
            result = await self.db.execute(
                select(ContentDraft)
                .where(
                    ContentDraft.brand_id == piece.brand_id,
                    ContentDraft.slug == piece.slug,
                    ContentDraft.status == "published",
                )
                .order_by(ContentDraft.created_at.desc())
            )
            draft = result.scalars().first()
        if draft:
            draft.status = "pending_review"
            draft.reviewer_id = user_id

        self.db.add(
            ApprovalEvent(
                entity_type="content_piece",
                entity_id=piece_id,
                action="returned_to_review",
                user_id=user_id,
            )
        )
        await self.notifications.create(
            type="returned_to_review",
            title=f"Returned to review: {piece.title}",
            body=(
                f"{brand.name if brand else piece.brand_id}: WP post "
                f"{'set to draft' if wp_set_to_draft else '(WP update failed — check credentials)'}."
            ),
            entity_type="content_piece",
            entity_id=piece_id,
        )
        await self.db.flush()
        return {
            "status": "unpublished",
            "piece_id": piece_id,
            "draft_id": draft.id if draft else None,
            "wp_set_to_draft": wp_set_to_draft,
        }

    async def update_draft_html(self, draft_id: int, html_content: str) -> ContentDraft:
        draft = await self.db.get(ContentDraft, draft_id)
        if not draft:
            raise ValueError("Draft not found")
        if draft.status not in ("pending_review", "needs_review"):
            raise ValueError("Cannot edit draft in current status")

        brand = await self.db.get(Brand, draft.brand_id)
        if not brand:
            raise ValueError("Brand not found")

        html_content = _inject_brand_phone(html_content, brand.phone)
        html_content = normalize_article_headings(html_content, draft.title or "")
        html_content = normalize_author_byline(html_content, brand)
        html_content = sanitize_links(html_content, brand)
        html_content = await verify_external_links(html_content, skip_hosts={_brand_host(brand)})
        is_valid, failure_reason = await validate_answer_first(
            html_content, draft.target_query or "", draft.content_type or "faq_hub"
        )
        schema_json, schema_types = build_combined_schema(
            html_content, brand, draft.title or "", draft.content_type or "faq_hub"
        )
        ratio, h2_questions, h2_total = h2_question_ratio(html_content)
        draft.html_content = html_content
        draft.schema_json = schema_json
        draft.validation_result = {
            "valid": is_valid,
            "reason": failure_reason,
            "schema_types": schema_types,
            "word_count": count_words(html_content),
            "h2_question_ratio": round(ratio, 2),
            "h2_questions": h2_questions,
            "h2_total": h2_total,
        }
        draft.status = "pending_review" if is_valid else "needs_review"
        await self.db.flush()
        return draft
