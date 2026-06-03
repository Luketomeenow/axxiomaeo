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
    return [
        {
            "id": d.id,
            "brand_id": d.brand_id,
            "content_type": d.content_type,
            "title": d.title,
            "target_query": d.target_query,
            "status": d.status,
            "validation_result": d.validation_result,
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


async def _generate_task(brand_id: str, content_type: str, target_query: str, title: str, city: str, state: str):
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        service = ContentGenerationService(session)
        await service.generate_draft(brand_id, content_type, target_query, title, city=city, state=state)
        await session.commit()


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
