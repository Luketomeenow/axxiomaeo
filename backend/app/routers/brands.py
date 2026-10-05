from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
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


@router.post("/{brand_id}/test-connection")
async def test_wp_connection(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Live WordPress auth probe for one brand — the honest version of
    wp_publish_configured (which only checks a password string exists)."""
    from app.services.pipeline_health_service import store_wp_auth_result
    from app.services.wordpress_service import WordPressService

    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    if not get_settings().wp_publish_configured(brand_id):
        result = {
            "ok": False,
            "status_code": None,
            "error": f"No application password configured (WP_APP_PASSWORD_{brand_id.upper()})",
        }
    else:
        result = await WordPressService().check_connection(brand)

    # Feed the health page's cache so /api/health/flow reflects this instantly.
    store_wp_auth_result(brand_id, result)
    return {**result, "checked_at": datetime.utcnow().isoformat()}


class CtaRefreshRequest(BaseModel):
    apply: bool = False
    limit: int = Field(20, ge=1, le=50)
    # Earlier numbers to replace besides the ones found in the posts' CTA
    # buttons, e.g. a number that only appears in body text.
    old_numbers: list[str] = []


@router.get("/{brand_id}/phone-check")
async def check_brand_phone(
    brand_id: str,
    phone: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Is the phone (default: the saved one) one of CallRail's rotating
    website numbers? Those never get swapped per visitor, so calls from posts
    that show one are credited to the wrong page."""
    from app.services.cta_refresh_service import phone_check

    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return await phone_check(db, phone if phone is not None else brand.phone)


@router.post("/{brand_id}/cta-refresh")
async def refresh_post_ctas(
    brand_id: str,
    body: CtaRefreshRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Bring the call-to-action and phone number on the brand's published
    posts up to date with Brand Settings. apply=false (default) only reports
    what would change; apply=true updates up to ``limit`` posts on WordPress
    per call (the dashboard asks for confirmation, then repeats until
    ``remaining`` is 0)."""
    from app.services.cta_refresh_service import refresh_brand_posts

    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    if body.apply and not get_settings().wp_publish_configured(brand_id):
        raise HTTPException(status_code=400, detail="WordPress credentials not configured for this brand")
    return await refresh_brand_posts(
        db, brand, apply=body.apply, limit=body.limit, old_numbers=body.old_numbers
    )
