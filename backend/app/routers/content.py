import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.content import ContentDraft, ContentQueue
from app.services.content_service import ContentGenerationService

router = APIRouter(prefix="/api/content", tags=["content"])


class GenerateRequest(BaseModel):
    brand_id: str
    content_type: str
    target_query: str
    title: str = ""
    city: str = ""
    state: str = ""


class RejectRequest(BaseModel):
    notes: str = ""


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


@router.get("/drafts")
async def list_drafts(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
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
):
    from app.database import AsyncSessionLocal

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
        )
        await session.commit()


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


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    draft_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = ContentGenerationService(db)
    try:
        piece = await service.approve_and_publish(draft_id, user.get("sub", "unknown"))
        return {"status": "published", "post_id": piece.wp_post_id, "post_url": piece.wp_post_url}
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

    async def task():
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            service = ContentGenerationService(session)
            await service.generate_draft(
                draft.brand_id,
                draft.content_type or "faq_hub",
                draft.target_query or "",
                draft.title or "",
                queue_id=draft.queue_id,
            )
            await session.commit()

    background_tasks.add_task(task)
    return {"status": "regenerating"}
