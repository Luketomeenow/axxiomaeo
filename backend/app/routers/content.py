import asyncio
import re
from types import SimpleNamespace

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.content import ContentDraft, ContentPiece, ContentQueue
from app.services.content_service import ContentGenerationService, recover_stale_generating_drafts

router = APIRouter(prefix="/api/content", tags=["content"])

# Limit concurrent Claude generations — set via CONTENT_GENERATION_CONCURRENCY.
_MAX_CONCURRENT_GENERATIONS = max(1, get_settings().content_generation_concurrency)
_generate_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_GENERATIONS)


class GenerateRequest(BaseModel):
    brand_id: str
    content_type: str
    target_query: str
    title: str = ""
    city: str = ""
    state: str = ""


class RejectRequest(BaseModel):
    notes: str = ""


class ApproveRequest(BaseModel):
    brand_ids: list[str] | None = None
    publish_all: bool = False


class GapQueueRequest(BaseModel):
    brand_id: str
    target_query: str
    content_type: str = "faq_hub"
    title: str = ""
    priority: int = 3
    citation_record_id: int | None = None


class UpdateDraftHtmlRequest(BaseModel):
    html_content: str


@router.post("/queue/from-gap")
async def queue_from_gap(
    req: GapQueueRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Add a citation gap query to the content queue for generation."""
    item = ContentQueue(
        brand_id=req.brand_id,
        content_type=req.content_type,
        target_query=req.target_query,
        title=req.title or req.target_query,
        priority=max(1, min(5, req.priority)),
        source_citation_id=req.citation_record_id,
        status="pending",
    )
    db.add(item)
    await db.flush()
    return {
        "id": item.id,
        "brand_id": item.brand_id,
        "target_query": item.target_query,
        "status": item.status,
    }


@router.get("/queue")
async def get_content_queue(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(select(ContentQueue).order_by(ContentQueue.priority, ContentQueue.scheduled_for))
    items = result.scalars().all()
    return [
        {
            "id": i.id,
            "brand_id": i.brand_id,
            "content_type": i.content_type,
            "target_query": i.target_query,
            "title": i.title,
            "priority": i.priority,
            "status": i.status,
            "scheduled_for": i.scheduled_for.isoformat() if i.scheduled_for else None,
        }
        for i in items
    ]


async def _count_active_generations(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(ContentDraft).where(ContentDraft.status == "generating")
    )
    return int(result.scalar() or 0)


@router.get("/drafts")
async def list_drafts(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    await recover_stale_generating_drafts(db)
    query = select(ContentDraft).order_by(ContentDraft.created_at.desc())
    if status:
        query = query.where(ContentDraft.status == status)
    result = await db.execute(query)
    drafts = result.scalars().all()

    queue_ids = [d.queue_id for d in drafts if d.queue_id]
    queue_priorities: dict[int, int] = {}
    if queue_ids:
        queue_result = await db.execute(
            select(ContentQueue).where(ContentQueue.id.in_(queue_ids))
        )
        for item in queue_result.scalars().all():
            queue_priorities[item.id] = item.priority

    return [
        {
            "id": d.id,
            "brand_id": d.brand_id,
            "content_type": d.content_type,
            "title": d.title,
            "target_query": d.target_query,
            "status": d.status,
            "validation_result": d.validation_result,
            "priority": queue_priorities.get(d.queue_id) if d.queue_id else None,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in drafts
    ]


@router.get("/published")
async def list_published(
    brand_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Live WordPress posts created via Approve & Publish."""
    query = (
        select(ContentPiece)
        .where(ContentPiece.status == "published")
        .order_by(ContentPiece.published_at.desc().nullslast(), ContentPiece.created_at.desc())
    )
    if brand_id:
        query = query.where(ContentPiece.brand_id == brand_id)
    result = await db.execute(query)
    pieces = result.scalars().all()
    return [
        {
            "id": p.id,
            "brand_id": p.brand_id,
            "content_type": p.content_type,
            "title": p.title,
            "target_query": p.target_query,
            "slug": p.slug,
            "wp_post_id": p.wp_post_id,
            "wp_post_url": p.wp_post_url,
            "word_count": p.word_count,
            "schema_types": p.schema_types or [],
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "last_refreshed_at": p.last_refreshed_at.isoformat() if p.last_refreshed_at else None,
        }
        for p in pieces
    ]


@router.get("/drafts/{draft_id}")
async def get_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    draft = await db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {
        "id": draft.id,
        "brand_id": draft.brand_id,
        "content_type": draft.content_type,
        "title": draft.title,
        "target_query": draft.target_query,
        "slug": draft.slug,
        "html_content": draft.html_content,
        "schema_json": draft.schema_json,
        "validation_result": draft.validation_result,
        "validation_attempts": draft.validation_attempts,
        "images_json": draft.images_json or [],
        "featured_media_id": draft.featured_media_id,
        "status": draft.status,
        "review_notes": draft.review_notes,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


async def _generate_task(
    brand_id: str,
    content_type: str,
    target_query: str,
    title: str,
    city: str,
    state: str,
    queue_id: int | None = None,
    existing_draft_id: int | None = None,
):
    import logging

    from app.database import AsyncSessionLocal
    from app.models.approval import WorkerError

    logger = logging.getLogger(__name__)

    async with _generate_semaphore:
        try:
            async with AsyncSessionLocal() as session:
                service = ContentGenerationService(session)
                await service.generate_draft(
                    brand_id,
                    content_type,
                    target_query,
                    title,
                    queue_id=queue_id,
                    city=city,
                    state=state,
                    existing_draft_id=existing_draft_id,
                )
        except Exception as exc:
            logger.exception("Background content generation failed")
            try:
                async with AsyncSessionLocal() as session:
                    session.add(
                        WorkerError(
                            worker_name="content_generate",
                            error_message=str(exc)[:500],
                            error_details={
                                "brand_id": brand_id,
                                "target_query": target_query,
                                "queue_id": queue_id,
                                "draft_id": existing_draft_id,
                            },
                        )
                    )
                    await session.commit()
            except Exception:
                logger.exception("Failed to record worker error")


def _parse_local_market(item: ContentQueue) -> tuple[str, str]:
    """Extract city/state from local_page queue titles or queries."""
    if item.content_type != "local_page":
        return "", ""
    for text in (item.title or "", item.target_query or ""):
        match = re.search(r"\bin\s+(.+?)\s+([A-Z]{2})\b", text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).upper()
        tail = re.search(r"(\w+(?:\s+\w+)*?)\s+([A-Z]{2})$", text.strip(), re.IGNORECASE)
        if tail:
            city_part = tail.group(1).strip()
            city = city_part.split()[-1] if " " in city_part else city_part
            return city, tail.group(2).upper()
    return "", ""


@router.post("/generate")
async def generate_content(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if await _count_active_generations(db) >= _MAX_CONCURRENT_GENERATIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"{_MAX_CONCURRENT_GENERATIONS} drafts are already generating. "
                "Wait for one to finish before starting another."
            ),
        )
    background_tasks.add_task(
        _generate_task,
        req.brand_id,
        req.content_type,
        req.target_query,
        req.title,
        req.city,
        req.state,
    )
    return {"status": "generating", "message": "Content generation started"}


@router.post("/queue/{queue_id}/generate")
async def generate_from_queue(
    queue_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    item = await db.get(ContentQueue, queue_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.status not in ("pending", "needs_review"):
        raise HTTPException(status_code=400, detail=f"Item is already {item.status}")

    existing = await db.execute(
        select(ContentDraft).where(
            ContentDraft.queue_id == queue_id,
            ContentDraft.status.in_(("generating", "pending_review", "needs_review")),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="A draft for this queue item already exists — check Content Review",
        )
    if await _count_active_generations(db) >= _MAX_CONCURRENT_GENERATIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"{_MAX_CONCURRENT_GENERATIONS} drafts are already generating. "
                "Wait for one to finish before starting another."
            ),
        )

    city, state = _parse_local_market(item)
    item.status = "in_progress"
    await db.flush()

    background_tasks.add_task(
        _generate_task,
        item.brand_id,
        item.content_type or "faq_hub",
        item.target_query or "",
        item.title or "",
        city,
        state,
        item.id,
    )
    return {"status": "generating", "queue_id": queue_id, "message": "Content generation started"}


@router.patch("/drafts/{draft_id}")
async def update_draft_html(
    draft_id: int,
    req: UpdateDraftHtmlRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = ContentGenerationService(db)
    try:
        draft = await service.update_draft_html(draft_id, req.html_content)
        return {
            "id": draft.id,
            "status": draft.status,
            "validation_result": draft.validation_result,
            "schema_json": draft.schema_json,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    req: ApproveRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = ContentGenerationService(db)
    body = req or ApproveRequest()
    try:
        return await service.approve_and_publish(
            draft_id,
            user.get("sub", "unknown"),
            brand_ids=body.brand_ids,
            publish_all=body.publish_all,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: int,
    req: RejectRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = ContentGenerationService(db)
    try:
        draft = await service.reject_draft(draft_id, user.get("sub", "unknown"), req.notes)
        return {"status": "rejected", "id": draft.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/drafts/{draft_id}/regenerate")
async def regenerate_draft(
    draft_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    draft = await db.get(ContentDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if await _count_active_generations(db) >= _MAX_CONCURRENT_GENERATIONS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"{_MAX_CONCURRENT_GENERATIONS} drafts are already generating. "
                "Wait for one to finish before regenerating."
            ),
        )

    city, state = "", ""
    if draft.content_type == "local_page":
        city, state = _parse_local_market(
            SimpleNamespace(
                content_type=draft.content_type,
                target_query=draft.target_query,
                title=draft.title,
            )
        )

    background_tasks.add_task(
        _generate_task,
        draft.brand_id,
        draft.content_type or "faq_hub",
        draft.target_query or "",
        draft.title or "",
        city,
        state,
        draft.queue_id,
        draft_id,
    )
    return {"status": "regenerating", "draft_id": draft_id}
