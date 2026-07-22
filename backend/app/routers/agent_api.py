"""Machine-facing API for external AI agents (the Foundry AEO strategist).

Auth is a shared key in the ``X-API-Key`` header (``AGENT_API_KEY`` env var;
unset = this whole surface is disabled). The read endpoints give an agent a
compact, LLM-friendly view of live AEO performance; the one write endpoint
queues content generation through the exact same dedup + human-review pipeline
the UI uses — an agent can DRAFT content, but publishing stays behind the
human gate in Content Review.

``/api/agent/openapi.json`` serves a scoped OpenAPI spec (just these
endpoints) for import as a Foundry OpenAPI tool.
"""

import logging
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.brand import Brand
from app.models.content import ContentPiece, ContentQueue
from app.routers.content import _generate_task, _parse_local_market

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent-api"])

VALID_CONTENT_TYPES = {"faq_hub", "local_page", "vertical_page", "comparison", "data_stats"}


async def require_agent_key(x_api_key: str = Header(default="")) -> None:
    configured = get_settings().agent_api_key
    if not configured:
        raise HTTPException(status_code=503, detail="Agent API disabled — AGENT_API_KEY is not set")
    if not secrets.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="Invalid API key")


class AgentGenerateRequest(BaseModel):
    brand_id: str = Field(description="Brand id, e.g. 'quality' — see /overview for the roster")
    target_query: str = Field(min_length=8, description="The search/AI query the article should win")
    content_type: str = Field(default="faq_hub", description="faq_hub | local_page | vertical_page | comparison | data_stats")
    title: str = Field(default="", description="Optional title; defaults to the target query")
    reason: str = Field(default="", description="Why the agent recommends this (stored for the human reviewer)")


@router.get("/overview", dependencies=[Depends(require_agent_key)])
async def agent_overview(db: AsyncSession = Depends(get_db)):
    """Compact snapshot of AEO performance: brands, latest-audit citation
    share, queue depth, published counts, and the current top recommendations."""
    from app.services.recommendation_service import RecommendationService
    from app.services.report_service import ReportService

    brands = list((await db.execute(select(Brand).order_by(Brand.id))).scalars().all())
    reports = ReportService(db)
    by_brand = {row["brand_id"]: row for row in await reports.get_citation_by_brand()}
    by_platform = await reports.get_visibility_by_platform()

    published_counts = dict(
        (await db.execute(
            select(ContentPiece.brand_id, func.count(ContentPiece.id))
            .where(ContentPiece.status == "published")
            .group_by(ContentPiece.brand_id)
        )).all()
    )
    queue_counts = dict(
        (await db.execute(
            select(ContentQueue.status, func.count(ContentQueue.id)).group_by(ContentQueue.status)
        )).all()
    )

    try:
        recommendations = await RecommendationService(db).list_recommendations(limit=8)
    except Exception:  # recommendations are derived data — never sink the overview
        logger.exception("Agent overview: recommendations unavailable")
        recommendations = []

    return {
        "brands": [
            {
                "brand_id": b.id,
                "name": b.name,
                "markets": b.markets or [],
                "citation": by_brand.get(b.id),
                "published_posts": published_counts.get(b.id, 0),
            }
            for b in brands
        ],
        "citation_by_platform": by_platform,
        "queue_by_status": queue_counts,
        "top_recommendations": recommendations,
        "notes": (
            "Citation figures reflect the latest audit run (audits run the 1st & 15th). "
            "Use POST /api/agent/generate to queue an article; drafts always wait for "
            "human approval in Content Review before publishing."
        ),
    }


@router.get("/gaps", dependencies=[Depends(require_agent_key)])
async def agent_gaps(
    brand_id: str | None = Query(None),
    limit: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Citation gaps from the latest audit — queries where the brand isn't
    cited (often a competitor is). The raw material for content decisions."""
    from app.services.report_service import ReportService

    gaps = await ReportService(db).get_gap_queries(limit=500)
    if brand_id:
        gaps = [g for g in gaps if g["brand_id"] == brand_id]
    return {"gaps": gaps[:limit], "total": len(gaps)}


@router.post("/generate", dependencies=[Depends(require_agent_key)])
async def agent_generate(
    req: AgentGenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Queue one article for generation. Deduped against everything already
    queued, drafted, or published for the brand; the draft lands in Content
    Review for human approval — this endpoint cannot publish anything."""
    from app.services.topic_discovery_service import TopicDiscoveryService, queries_similar

    if req.content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail=f"content_type must be one of {sorted(VALID_CONTENT_TYPES)}")
    brand = await db.get(Brand, req.brand_id)
    if not brand:
        known = [b.id for b in (await db.execute(select(Brand))).scalars().all()]
        raise HTTPException(status_code=404, detail=f"Unknown brand_id {req.brand_id!r}; known: {known}")

    existing = (await TopicDiscoveryService(db)._existing_queries_by_brand()).get(req.brand_id, [])
    covered_by = next((q for q in existing if queries_similar(req.target_query, q)), None)
    if covered_by:
        raise HTTPException(
            status_code=409,
            detail=f'Already covered — "{covered_by}" is queued, drafted, or published for this brand',
        )

    item = ContentQueue(
        brand_id=req.brand_id,
        content_type=req.content_type,
        target_query=req.target_query,
        title=req.title or req.target_query,
        priority=2,
        source="agent",
        source_detail={"reason": req.reason} if req.reason else None,
        status="in_progress",
    )
    db.add(item)
    await db.flush()

    city, state = _parse_local_market(item)
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
    return {
        "status": "generating",
        "queue_id": item.id,
        "message": (
            "Draft generation started. It will appear in Content Review "
            "(pending human approval) in a few minutes — it will NOT publish on its own."
        ),
    }


@router.get("/openapi.json", include_in_schema=False)
async def agent_openapi():
    """Scoped OpenAPI spec for the three agent endpoints — import this URL as
    a Foundry OpenAPI tool. Public: it describes the API but contains no key."""
    base = get_settings().public_api_url.rstrip("/")
    key_scheme = {"type": "apiKey", "name": "X-API-Key", "in": "header"}
    secured = [{"ApiKeyAuth": []}]
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Axxiom AEO Platform — Agent API",
            "version": "1.0.0",
            "description": "Read live AEO performance and queue draft generation (human-gated publishing).",
        },
        "servers": [{"url": base}],
        "components": {"securitySchemes": {"ApiKeyAuth": key_scheme}},
        "security": secured,
        "paths": {
            "/api/agent/overview": {
                "get": {
                    "operationId": "getAeoOverview",
                    "summary": "AEO performance snapshot: brands, latest-audit citation share, queue depth, published counts, top recommendations",
                    "security": secured,
                    "responses": {"200": {"description": "Overview JSON"}},
                }
            },
            "/api/agent/gaps": {
                "get": {
                    "operationId": "getCitationGaps",
                    "summary": "Citation gaps from the latest audit (queries where a brand is not cited; often a competitor is)",
                    "security": secured,
                    "parameters": [
                        {"name": "brand_id", "in": "query", "required": False, "schema": {"type": "string"}},
                        {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "default": 25}},
                    ],
                    "responses": {"200": {"description": "Gap list JSON"}},
                }
            },
            "/api/agent/generate": {
                "post": {
                    "operationId": "generateAeoContent",
                    "summary": "Queue ONE article draft for a brand (deduped; draft waits for human approval in Content Review; cannot publish)",
                    "security": secured,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["brand_id", "target_query"],
                                    "properties": {
                                        "brand_id": {"type": "string", "description": "Brand id from /overview (e.g. quality, axxiom)"},
                                        "target_query": {"type": "string", "description": "Search/AI query the article should win"},
                                        "content_type": {
                                            "type": "string",
                                            "enum": sorted(VALID_CONTENT_TYPES),
                                            "default": "faq_hub",
                                        },
                                        "title": {"type": "string"},
                                        "reason": {"type": "string", "description": "Why this is recommended (shown to the human reviewer)"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Generation started; draft goes to Content Review"},
                        "409": {"description": "Already covered by existing queue/draft/published content"},
                    },
                }
            },
        },
    }
