import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece
from app.services.claude_service import ClaudeService
from app.services.content_service import ContentGenerationService
from app.services.notification_service import NotificationService, record_worker_error

logger = logging.getLogger(__name__)


async def run_content_refresh():
    """Re-optimize and re-publish stale content (freshness is a real AI-citation
    signal): updated stats/years, extra FAQ coverage, stronger direct answers.

    Rotation is least-recently-touched first, keyed on
    coalesce(last_refreshed_at, published_at) — the old selection filtered on
    published_at alone with no ordering, so the same arbitrary two pieces were
    re-eligible (and re-picked) every single week while everything else aged.
    """
    settings = get_settings()
    logger.info("Starting content refresh job")
    cutoff = datetime.utcnow() - timedelta(days=max(1, settings.content_refresh_days))
    last_touched = func.coalesce(ContentPiece.last_refreshed_at, ContentPiece.published_at)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ContentPiece)
            .where(
                ContentPiece.status == "published",
                ContentPiece.published_at.isnot(None),
                last_touched < cutoff,
            )
            .order_by(last_touched.asc())
            .limit(max(1, settings.content_refresh_max_per_run))
        )
        pieces = result.scalars().all()

    if not pieces:
        logger.info("No stale content to refresh")
        return

    claude = ClaudeService()
    refreshed: list[str] = []
    skipped_no_draft = 0
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
                skipped_no_draft += 1
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
                refreshed.append(f"{p.brand_id}: {p.title or p.slug}")
                logger.info("Refreshed content piece %s for brand %s", p.id, p.brand_id)
            except Exception as e:
                logger.exception("Refresh failed for content piece %s", p.id)
                await record_worker_error(
                    session,
                    "content_refresh",
                    f"Refresh failed for piece {p.id} ({p.brand_id}): {e}",
                    error_details={"piece_id": p.id, "brand_id": p.brand_id},
                    notify=False,  # System Health's errors stage surfaces these
                )
                await session.commit()

    logger.info(
        "Content refresh complete: %s piece(s) updated, %s skipped (no stored draft html)",
        len(refreshed),
        skipped_no_draft,
    )
    if refreshed:
        async with AsyncSessionLocal() as session:
            await NotificationService(session).create(
                type="content_refresh",
                title=f"{len(refreshed)} post(s) re-optimized for freshness",
                body="\n".join(refreshed)[:1500],
            )
            await session.commit()

    # NOTE: this worker used to conditionally trigger a full citation
    # re-audit here (gap-sourced pieces >30 days old). Audits now run weekly
    # on Mondays, so the Sunday-night extra run would just double Bright
    # Data spend for data that's hours from arriving anyway.
