from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.content import ContentQueue
from app.models.observed_question import ObservedQuestion

router = APIRouter(prefix="/api/customer-questions", tags=["customer-questions"])


@router.get("")
async def list_customer_questions(
    brand_id: str | None = None,
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(300, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Customer questions the platform holds (from calls, chats, forms), newest
    first, each with the topic it became, if any. Topic discovery uses the
    last 90 days of these first, ahead of every other source."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = (
        select(ObservedQuestion)
        .where(ObservedQuestion.created_at >= cutoff)
        .order_by(ObservedQuestion.created_at.desc())
        .limit(limit)
    )
    if brand_id:
        query = query.where(ObservedQuestion.brand_id == brand_id)
    rows = (await db.execute(query)).scalars().all()

    # Which questions already became a topic (discovery records the id).
    queue_rows = (
        await db.execute(
            select(ContentQueue.id, ContentQueue.status, ContentQueue.source_detail).where(
                ContentQueue.source == "observed_demand", ContentQueue.created_at >= cutoff
            )
        )
    ).all()
    topic_for: dict[int, dict] = {}
    for queue_id, status, detail in queue_rows:
        qid = (detail or {}).get("observed_question_id")
        if isinstance(qid, int):
            topic_for[qid] = {"queue_id": queue_id, "status": status}

    return {
        "questions": [
            {
                "id": r.id,
                "brand_id": r.brand_id,
                "question": r.question,
                "source": r.source,
                "asked_at": r.asked_at.isoformat() if r.asked_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "intent": (r.detail or {}).get("intent"),
                "call_source": (r.detail or {}).get("call_source"),
                "topic": topic_for.get(r.id),
            }
            for r in rows
        ]
    }


@router.delete("/{question_id}")
async def delete_customer_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Remove a question so topic discovery and the audit stop using it. A
    topic it already became stays in the Content Queue."""
    row = await db.get(ObservedQuestion, question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")
    await db.delete(row)
    await db.flush()
    return {"deleted": question_id}


@router.post("/scan")
async def scan_calls_now(
    background_tasks: BackgroundTasks,
    days: int | None = Query(None, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Run the CallRail call-summary scan now (it also runs daily at 7:15am CT).

    The default lookback (a few days) runs inline and returns its counts. A
    longer backfill (days > 7) can take minutes, longer than a request may
    stay open, so it runs in the background and reports in Notifications."""
    from app.services.call_questions_service import CallQuestionsService

    if days and days > 7:
        background_tasks.add_task(_backfill, days)
        return {"status": "started", "days": days}
    return await CallQuestionsService(db).run(days=days)


async def _backfill(days: int) -> None:
    from app.database import AsyncSessionLocal
    from app.services.call_questions_service import CallQuestionsService
    from app.services.notification_service import NotificationService, record_worker_error

    async with AsyncSessionLocal() as session:
        try:
            result = await CallQuestionsService(session).run(days=days, max_calls=1000)
            await session.commit()
            if result.get("status") == "ok":
                body = (
                    f"Read {result.get('calls_scanned', 0)} call summaries from the last {days} days and "
                    f"stored {result.get('stored', 0)} new customer question(s) "
                    f"({result.get('duplicates', 0)} already known)."
                )
            else:
                body = result.get("message", "The scan could not read CallRail data.")
            await NotificationService(session).create(
                type="call_questions", title="Customer question backfill finished", body=body
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            await record_worker_error(session, "call_questions", f"backfill failed: {e}")
            await session.commit()
