from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.approval import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class MarkReadRequest(BaseModel):
    pass


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = select(Notification).order_by(Notification.created_at.desc()).limit(50)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in items
    ]


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from sqlalchemy import func

    count = await db.scalar(
        select(func.count(Notification.id)).where(Notification.read_at.is_(None))
    )
    return {"count": count or 0}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    notification = await db.get(Notification, notification_id)
    if not notification:
        return {"status": "not_found"}
    notification.read_at = datetime.utcnow()
    await db.flush()
    return {"status": "read"}
