from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.approval import ApprovalEvent
from app.models.brand import Brand
from app.models.content import ContentPiece
from app.models.schema_job import SchemaDeployment, SchemaJob
from app.services.notification_service import NotificationService
from app.services.schema_service import (
    build_brand_schema_set,
    build_faqpage_from_text,
    wrap_schema_script,
)
from app.services.wordpress_service import WordPressService, schema_carrier_meta
from slugify import slugify

router = APIRouter(prefix="/api/schema", tags=["schema"])


def _deployment_slug(dep: SchemaDeployment, brand_id: str) -> str:
    if dep.schema_type == "Organization":
        return f"schema-organization-{brand_id}"
    if dep.schema_type == "LocalBusiness":
        return f"schema-localbusiness-{brand_id}"
    if dep.schema_type == "Service":
        service_name = (dep.title or "").split(" - ", 1)[-1].strip()
        return slugify(f"schema-service-{service_name}-{brand_id}", max_length=80)
    return slugify(f"schema-{dep.schema_type.lower()}-{brand_id}", max_length=80)


class RejectRequest(BaseModel):
    notes: str = ""


class UpdateDeploymentRequest(BaseModel):
    schema_json: str


class ApproveDeploymentRequest(BaseModel):
    schema_json: str | None = None


class FaqSchemaRequest(BaseModel):
    text: str
    include_script_tag: bool = False


@router.post("/faq/generate")
async def generate_faq_schema(
    req: FaqSchemaRequest,
    _user: dict = Depends(get_current_user),
):
    """
    Convert FAQ text into FAQPage JSON-LD for search engines and AI crawlers.

    Accepts Q:/A: blocks, question? + answer paragraphs, JSON FAQ arrays, HTML, or FAQPage JSON.
    """
    try:
        schema_json, faqs = build_faqpage_from_text(req.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "schema_type": "FAQPage",
        "faq_count": len(faqs),
        "faqs": faqs,
        "schema_json": schema_json,
        "script_snippet": wrap_schema_script(schema_json) if req.include_script_tag else None,
    }


@router.get("/deployments")
async def list_deployments(
    status: str | None = Query("pending_review"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    query = select(SchemaDeployment).order_by(SchemaDeployment.created_at.desc())
    if status:
        query = query.where(SchemaDeployment.status == status)
    result = await db.execute(query)
    items = result.scalars().all()
    return [
        {
            "id": d.id,
            "brand_id": d.brand_id,
            "schema_type": d.schema_type,
            "title": d.title,
            "wp_post_url": d.wp_post_url,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in items
    ]


@router.get("/deployments/{deployment_id}")
async def get_deployment(
    deployment_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dep = await db.get(SchemaDeployment, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return {
        "id": dep.id,
        "brand_id": dep.brand_id,
        "schema_type": dep.schema_type,
        "title": dep.title,
        "schema_json": dep.schema_json,
        "wp_post_id": dep.wp_post_id,
        "wp_post_url": dep.wp_post_url,
        "status": dep.status,
        "review_notes": dep.review_notes,
    }


@router.get("/published")
async def list_published_schema(
    brand_id: str | None = Query(None),
    source: str | None = Query(None, description="brand_schema or content"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """All live schema: approved brand deployments + published content with schema types."""
    items: list[dict] = []

    if source in (None, "brand_schema"):
        dep_query = (
            select(SchemaDeployment)
            .where(SchemaDeployment.status == "approved")
            .order_by(SchemaDeployment.updated_at.desc())
        )
        if brand_id:
            dep_query = dep_query.where(SchemaDeployment.brand_id == brand_id)
        deps = (await db.execute(dep_query)).scalars().all()
        for d in deps:
            items.append(
                {
                    "id": d.id,
                    "source": "brand_schema",
                    "brand_id": d.brand_id,
                    "title": d.title,
                    "schema_type": d.schema_type,
                    "schema_types": [d.schema_type] if d.schema_type else [],
                    "wp_post_url": d.wp_post_url,
                    "published_at": d.updated_at.isoformat() if d.updated_at else None,
                    "has_schema_json": bool(d.schema_json),
                }
            )

    if source in (None, "content"):
        content_query = (
            select(ContentPiece)
            .where(ContentPiece.status == "published")
            .order_by(ContentPiece.published_at.desc().nullslast(), ContentPiece.created_at.desc())
        )
        if brand_id:
            content_query = content_query.where(ContentPiece.brand_id == brand_id)
        pieces = (await db.execute(content_query)).scalars().all()
        for p in pieces:
            types = p.schema_types or []
            if not types:
                continue
            items.append(
                {
                    "id": p.id,
                    "source": "content",
                    "brand_id": p.brand_id,
                    "title": p.title,
                    "schema_type": ", ".join(types),
                    "schema_types": types,
                    "wp_post_url": p.wp_post_url,
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "has_schema_json": False,
                }
            )

    items.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    return items


@router.get("/published/{source}/{item_id}")
async def get_published_schema(
    source: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if source == "brand_schema":
        dep = await db.get(SchemaDeployment, item_id)
        if not dep or dep.status != "approved":
            raise HTTPException(status_code=404, detail="Published schema not found")
        return {
            "id": dep.id,
            "source": "brand_schema",
            "brand_id": dep.brand_id,
            "title": dep.title,
            "schema_type": dep.schema_type,
            "schema_types": [dep.schema_type] if dep.schema_type else [],
            "schema_json": dep.schema_json,
            "wp_post_id": dep.wp_post_id,
            "wp_post_url": dep.wp_post_url,
            "published_at": dep.updated_at.isoformat() if dep.updated_at else None,
        }

    if source == "content":
        piece = await db.get(ContentPiece, item_id)
        if not piece or piece.status != "published":
            raise HTTPException(status_code=404, detail="Published schema not found")
        types = piece.schema_types or []
        if not types:
            raise HTTPException(status_code=404, detail="This post has no schema types recorded")
        schema_json = None
        if piece.wp_post_id:
            brand = await db.get(Brand, piece.brand_id)
            if brand:
                wp = WordPressService()
                schema_json = await wp.get_post_meta_schema(brand, piece.wp_post_id, post_type="posts")
        return {
            "id": piece.id,
            "source": "content",
            "brand_id": piece.brand_id,
            "title": piece.title,
            "schema_type": ", ".join(types),
            "schema_types": types,
            "schema_json": schema_json,
            "wp_post_id": piece.wp_post_id,
            "wp_post_url": piece.wp_post_url,
            "published_at": piece.published_at.isoformat() if piece.published_at else None,
        }

    raise HTTPException(status_code=400, detail="Source must be brand_schema or content")


@router.post("/deploy/{brand_id}")
async def deploy_schema_for_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    deployments = [
        SchemaDeployment(
            brand_id=brand_id,
            schema_type=item["schema_type"],
            schema_json=item["schema_json"],
            title=item["title"],
            status="pending_review",
        )
        for item in build_brand_schema_set(brand)
    ]

    for d in deployments:
        db.add(d)
    await db.flush()

    notifications = NotificationService(db)
    await notifications.create(
        type="schema_ready",
        title=f"{len(deployments)} schema deployments ready for review",
        body=f"Brand: {brand.name}",
        entity_type="schema_deployment",
        entity_id=deployments[0].id if deployments else None,
    )

    return {"status": "pending_review", "count": len(deployments)}


def _validate_schema_json(schema_json: str) -> None:
    import json

    trimmed = schema_json.strip()
    if not trimmed:
        raise HTTPException(status_code=400, detail="Schema JSON cannot be empty")
    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
    if not isinstance(parsed, (dict, list)):
        raise HTTPException(status_code=400, detail="Schema must be a JSON object or array")


@router.patch("/deployments/{deployment_id}")
async def update_deployment(
    deployment_id: int,
    req: UpdateDeploymentRequest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    dep = await db.get(SchemaDeployment, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if dep.status != "pending_review":
        raise HTTPException(status_code=400, detail="Only pending deployments can be edited")

    _validate_schema_json(req.schema_json)
    dep.schema_json = req.schema_json.strip()
    await db.flush()
    return {"status": "updated", "schema_json": dep.schema_json}


@router.post("/deployments/{deployment_id}/approve")
async def approve_deployment(
    deployment_id: int,
    req: ApproveDeploymentRequest = ApproveDeploymentRequest(),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    dep = await db.get(SchemaDeployment, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if req.schema_json is not None:
        _validate_schema_json(req.schema_json)
        dep.schema_json = req.schema_json.strip()

    brand = await db.get(Brand, dep.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    wp = WordPressService()
    if dep.wp_post_id:
        result = await wp.update_post(
            brand,
            dep.wp_post_id,
            schema_json=dep.schema_json or "",
            post_type="pages",
        )
        # Ensure noindex on existing carrier pages
        await wp._request(
            brand,
            "POST",
            f"pages/{dep.wp_post_id}",
            json={"meta": schema_carrier_meta()},
        )
    else:
        slug = _deployment_slug(dep, brand.id)
        result = await wp.create_post(
            brand=brand,
            title=dep.title or f"{brand.name} Schema",
            content="",
            slug=slug,
            schema_json=dep.schema_json or "",
            post_type="pages",
            noindex=True,
        )
        dep.wp_post_id = result.get("post_id")
        dep.wp_post_url = result.get("post_url")

    dep.status = "approved"
    dep.reviewer_id = user.get("sub", "unknown")

    job = SchemaJob(
        brand_id=dep.brand_id,
        wp_post_id=dep.wp_post_id,
        wp_post_url=dep.wp_post_url,
        schema_types=[dep.schema_type or "Unknown"],
        validation_status="valid",
        deployed_at=datetime.utcnow(),
    )
    db.add(job)
    db.add(
        ApprovalEvent(
            entity_type="schema_deployment",
            entity_id=deployment_id,
            action="approved",
            user_id=user.get("sub", "unknown"),
        )
    )
    await db.flush()
    return {"status": "deployed", "post_url": dep.wp_post_url}


@router.post("/deployments/{deployment_id}/reject")
async def reject_deployment(
    deployment_id: int,
    req: RejectRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    dep = await db.get(SchemaDeployment, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    dep.status = "rejected"
    dep.reviewer_id = user.get("sub", "unknown")
    dep.review_notes = req.notes
    db.add(
        ApprovalEvent(
            entity_type="schema_deployment",
            entity_id=deployment_id,
            action="rejected",
            user_id=user.get("sub", "unknown"),
            notes=req.notes,
        )
    )
    return {"status": "rejected"}


async def _validate_brand(brand_id: str):
    import httpx
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        brand = await session.get(Brand, brand_id)
        if not brand:
            return

        urls_to_check: list[tuple[int | None, str, list[str]]] = []

        result = await session.execute(
            select(ContentPiece).where(ContentPiece.brand_id == brand_id, ContentPiece.status == "published")
        )
        for piece in result.scalars().all():
            if piece.wp_post_url:
                urls_to_check.append(
                    (piece.wp_post_id, piece.wp_post_url, piece.schema_types or ["Content"])
                )

        dep_result = await session.execute(
            select(SchemaDeployment).where(
                SchemaDeployment.brand_id == brand_id,
                SchemaDeployment.status == "approved",
                SchemaDeployment.wp_post_url.isnot(None),
            )
        )
        for dep in dep_result.scalars().all():
            urls_to_check.append(
                (dep.wp_post_id, dep.wp_post_url or "", [dep.schema_type or "BrandSchema"])
            )

        for wp_post_id, url, schema_types in urls_to_check:
            if not url:
                continue
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url)
                    has_schema = 'type="application/ld+json"' in resp.text
                    job = SchemaJob(
                        brand_id=brand_id,
                        wp_post_id=wp_post_id,
                        wp_post_url=url,
                        schema_types=schema_types,
                        validation_status="valid" if has_schema else "error",
                        error_details=None if has_schema else "Missing JSON-LD schema",
                        validated_at=datetime.utcnow(),
                    )
                    session.add(job)
            except Exception as e:
                session.add(
                    SchemaJob(
                        brand_id=brand_id,
                        wp_post_id=wp_post_id,
                        wp_post_url=url,
                        schema_types=schema_types,
                        validation_status="error",
                        error_details=str(e),
                        validated_at=datetime.utcnow(),
                    )
                )
        await session.commit()


@router.post("/validate/{brand_id}")
async def validate_schema(
    brand_id: str,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(get_current_user),
):
    background_tasks.add_task(_validate_brand, brand_id)
    return {"status": "validation_started"}


@router.get("/health")
async def schema_health(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    brands = await db.execute(select(Brand))
    result = []
    for brand in brands.scalars().all():
        jobs = await db.execute(
            select(SchemaJob)
            .where(SchemaJob.brand_id == brand.id)
            .order_by(SchemaJob.created_at.desc())
        )
        job_list = jobs.scalars().all()

        # Collapse to the most-recent job per distinct page. Both approve and
        # every validation run INSERT a fresh SchemaJob, so counting raw rows
        # multiplies each page by how many times it's been checked — which made
        # Pages Tracked / Valid / Errors climb on every validation. Rows are
        # newest-first, so the first one seen per page key is the current state.
        latest_by_page: dict[str, SchemaJob] = {}
        for j in job_list:
            key = j.wp_post_url or (f"post:{j.wp_post_id}" if j.wp_post_id else f"job:{j.id}")
            if key not in latest_by_page:
                latest_by_page[key] = j
        pages = list(latest_by_page.values())

        valid = sum(1 for j in pages if j.validation_status == "valid")
        errors = sum(1 for j in pages if j.validation_status == "error")
        last_validated = max((j.validated_at for j in job_list if j.validated_at), default=None)
        result.append(
            {
                "brand_id": brand.id,
                "brand_name": brand.name,
                "total_pages": len(pages),
                "valid_schema": valid,
                "errors": errors,
                "last_validation": last_validated.isoformat() if last_validated else None,
            }
        )
    return result
