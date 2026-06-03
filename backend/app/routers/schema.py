from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.approval import ApprovalEvent
from app.models.brand import Brand
from app.models.schema_job import SchemaDeployment, SchemaJob
from app.services.notification_service import NotificationService
from app.services.schema_service import build_local_business_schema, build_organization_schema, build_service_schema
from app.services.wordpress_service import WordPressService

router = APIRouter(prefix="/api/schema", tags=["schema"])

SERVICE_TYPES = [
    "Elevator Maintenance",
    "Elevator Repair",
    "Elevator Modernization",
    "New Elevator Installation",
    "Elevator Inspection",
]


class RejectRequest(BaseModel):
    notes: str = ""


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


@router.post("/deploy/{brand_id}")
async def deploy_schema_for_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    deployments = []
    org_schema = build_organization_schema(brand)
    deployments.append(
        SchemaDeployment(
            brand_id=brand_id,
            schema_type="Organization",
            schema_json=org_schema,
            title=f"{brand.name} - Organization Schema",
            status="pending_review",
        )
    )
    local_schema = build_local_business_schema(brand)
    deployments.append(
        SchemaDeployment(
            brand_id=brand_id,
            schema_type="LocalBusiness",
            schema_json=local_schema,
            title=f"{brand.name} - LocalBusiness Schema",
            status="pending_review",
        )
    )
    for svc in SERVICE_TYPES:
        deployments.append(
            SchemaDeployment(
                brand_id=brand_id,
                schema_type="Service",
                schema_json=build_service_schema(brand, svc),
                title=f"{brand.name} - {svc}",
                status="pending_review",
            )
        )

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


@router.post("/deployments/{deployment_id}/approve")
async def approve_deployment(
    deployment_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    dep = await db.get(SchemaDeployment, deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")

    brand = await db.get(Brand, dep.brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    wp = WordPressService()
    if dep.wp_post_id:
        result = await wp.update_post_meta(brand, dep.wp_post_id, dep.schema_json or "", post_type="pages")
    else:
        slug = f"schema-{dep.schema_type.lower()}-{brand.id}"
        result = await wp.create_post(
            brand=brand,
            title=dep.title or f"{brand.name} Schema",
            content="",
            slug=slug,
            schema_json=dep.schema_json or "",
            post_type="pages",
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
    from app.models.content import ContentPiece

    async with AsyncSessionLocal() as session:
        brand = await session.get(Brand, brand_id)
        if not brand:
            return
        result = await session.execute(
            select(ContentPiece).where(ContentPiece.brand_id == brand_id, ContentPiece.status == "published")
        )
        pieces = result.scalars().all()
        for piece in pieces:
            if not piece.wp_post_url:
                continue
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(piece.wp_post_url)
                    has_schema = 'type="application/ld+json"' in resp.text
                    job = SchemaJob(
                        brand_id=brand_id,
                        wp_post_id=piece.wp_post_id,
                        wp_post_url=piece.wp_post_url,
                        validation_status="valid" if has_schema else "error",
                        error_details=None if has_schema else "Missing JSON-LD schema",
                        validated_at=datetime.utcnow(),
                    )
                    session.add(job)
            except Exception as e:
                session.add(
                    SchemaJob(
                        brand_id=brand_id,
                        wp_post_id=piece.wp_post_id,
                        wp_post_url=piece.wp_post_url,
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
        jobs = await db.execute(select(SchemaJob).where(SchemaJob.brand_id == brand.id))
        job_list = jobs.scalars().all()
        valid = sum(1 for j in job_list if j.validation_status == "valid")
        errors = sum(1 for j in job_list if j.validation_status == "error")
        last_validated = max((j.validated_at for j in job_list if j.validated_at), default=None)
        result.append(
            {
                "brand_id": brand.id,
                "brand_name": brand.name,
                "total_pages": len(job_list),
                "valid_schema": valid,
                "errors": errors,
                "last_validation": last_validated.isoformat() if last_validated else None,
            }
        )
    return result
