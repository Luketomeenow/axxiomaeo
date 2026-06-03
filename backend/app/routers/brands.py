from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.brand import Brand

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("")
async def list_brands(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Brand).order_by(Brand.name))
    brands = result.scalars().all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "wp_url": b.wp_url,
            "markets": b.markets,
            "is_corporate": b.is_corporate,
            "ga4_property_id": b.ga4_property_id,
            "gsc_site_url": b.gsc_site_url,
        }
        for b in brands
    ]
