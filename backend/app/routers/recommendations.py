"""Recommendations Inbox — approve a ranked citation-gap rec into action.

GET  /api/recommendations            ranked, explained content recommendations
POST /api/recommendations/{key}/approve   enqueue + generate a draft; the draft
                                           lands in Content Review (pending_review)
                                           for human approval before publish
POST /api/recommendations/{key}/dismiss    suppress the rec for a cooldown window

Approve reuses the daily topic-discovery enqueue shape (source/source_detail
provenance) and the existing background generation trigger. Unlike the daily
worker (which may auto-publish its own queue items), an approved recommendation
always stops at Content Review — approving the rec approves generating the
draft, not publishing it.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.approval import ApprovalEvent
from app.models.content import ContentQueue
from app.routers.content import _generate_task, _parse_local_market
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("")
async def list_recommendations(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    items = await service.list_recommendations(limit=limit)
    return {"recommendations": items, "count": len(items)}


@router.post("/{key}/approve")
async def approve_recommendation(
    key: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    rec = await service.get_recommendation(key)
    if not rec:
        raise HTTPException(
            status_code=404,
            detail="Recommendation not found — it may already be queued, published, or dismissed",
        )

    user_id = user.get("sub", "unknown")
    queue = ContentQueue(
        brand_id=rec["brand_id"],
        content_type=rec["content_type"],
        target_query=rec["query"],
        title=rec["title"],
        priority=rec["priority"],
        source="citation_gap",
        source_detail=rec["source_detail"],
        source_citation_id=rec.get("source_citation_id"),
        status="in_progress",
    )
    db.add(queue)
    await db.flush()  # assign queue.id before the audit row + background task

    service.record_action(key, "approved", user_id, brand_id=rec["brand_id"], query=rec["query"])
    db.add(
        ApprovalEvent(
            entity_type="recommendation",
            entity_id=queue.id,
            action="recommendation_approved",
            user_id=user_id,
            notes=(rec["query"] or "")[:500],
        )
    )
    await db.flush()

    # get_db commits when this handler returns, before background tasks run, so
    # _generate_task's own session sees the committed queue row (same ordering
    # the /content/queue/{id}/generate endpoint relies on).
    city, state = _parse_local_market(queue)
    background_tasks.add_task(
        _generate_task,
        queue.brand_id,
        queue.content_type or "faq_hub",
        queue.target_query or "",
        queue.title or "",
        city,
        state,
        queue.id,
    )
    return {
        "status": "approved",
        "queue_id": queue.id,
        "message": "Generating draft — review and publish it from Content Review",
    }


@router.post("/{key}/dismiss")
async def dismiss_recommendation(
    key: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    service = RecommendationService(db)
    # Look up brand/query for the audit row if the rec is still live; even if it
    # has already fallen off, still record the dismiss so the key stays
    # suppressed for the cooldown window.
    rec = await service.get_recommendation(key)
    service.record_action(
        key,
        "dismissed",
        user.get("sub", "unknown"),
        brand_id=(rec or {}).get("brand_id"),
        query=(rec or {}).get("query"),
    )
    return {"status": "dismissed", "key": key}
