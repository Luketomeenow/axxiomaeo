from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.brand import Brand
from app.schemas.brand import BrandUpdate, brand_to_dict

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("")
async def list_brands(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Brand).order_by(Brand.name))
    brands = result.scalars().all()
    return [brand_to_dict(b) for b in brands]


@router.get("/{brand_id}")
async def get_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand_to_dict(brand)


@router.put("/{brand_id}")
async def update_brand(
    brand_id: str,
    payload: BrandUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(brand, field, value)

    await db.flush()
    return brand_to_dict(brand)
