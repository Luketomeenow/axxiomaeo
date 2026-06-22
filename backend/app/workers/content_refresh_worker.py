import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece
from app.services.claude_service import ClaudeService
from app.services.content_service import ContentGenerationService

logger = logging.getLogger(__name__)

STALE_CONTENT_DAYS = 90
MAX_REFRESH_PER_RUN = 2


async def run_content_refresh():
    """Regenerate and re-publish stale content (Ahrefs: freshness matters for AI citations)."""
    logger.info("Starting content refresh job")
    cutoff = datetime.utcnow() - timedelta(days=STALE_CONTENT_DAYS)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ContentPiece).where(
                ContentPiece.status == "published",
                ContentPiece.published_at.isnot(None),
                ContentPiece.published_at < cutoff,
            )
        )
        pieces = result.scalars().all()[:MAX_REFRESH_PER_RUN]

    if not pieces:
        logger.info("No stale content to refresh")
        return

    claude = ClaudeService()
    refreshed = 0
    for piece in pieces:
        async with AsyncSessionLocal() as session:
            p = await session.get(ContentPiece, piece.id)
            if not p or not p.wp_post_id:
                continue

            draft_q = await session.execute(
                select(ContentDraft)
                .where(
                    ContentDraft.brand_id == p.brand_id,
                    ContentDraft.slug == p.slug,
                    ContentDraft.html_content.isnot(None),
                )
                .order_by(ContentDraft.updated_at.desc())
                .limit(1)
            )
            draft = draft_q.scalar_one_or_none()
            if not draft or not draft.html_content:
                continue

            brand = await session.get(Brand, p.brand_id)
            if not brand:
                continue

            try:
                html = await claude.refresh_content(
                    target_query=draft.target_query or p.title or "",
                    brand_name=brand.name,
                    content_type=draft.content_type or p.content_type or "faq_hub",
                    previous_content=draft.html_content,
                )
                draft.html_content = html
                svc = ContentGenerationService(session)
                await svc._publish_draft_to_brand(draft, p.brand_id)
                await session.commit()
                refreshed += 1
                logger.info("Refreshed content piece %s for brand %s", p.id, p.brand_id)
            except Exception:
                logger.exception("Refresh failed for content piece %s", p.id)

    logger.info("Content refresh complete: %s piece(s) updated", refreshed)

    async with AsyncSessionLocal() as session:
        recheck_cutoff = datetime.utcnow() - timedelta(days=30)
        gap_pieces = await session.execute(
            select(ContentPiece).where(
                ContentPiece.source_citation_id.isnot(None),
                ContentPiece.published_at.isnot(None),
                ContentPiece.published_at < recheck_cutoff,
            )
        )
        if gap_pieces.scalars().first():
            logger.info("Triggering citation re-audit after gap-sourced publishes")
            from app.workers.citation_worker import run_citation_audit

            await run_citation_audit()
