"""Machine-facing API for external AI agents (the Foundry AEO strategist).

Auth is a shared key in the ``X-API-Key`` header (``AGENT_API_KEY`` env var;
unset = this whole surface is disabled). The read endpoints give an agent a
compact, LLM-friendly view of live AEO performance; the write endpoints queue
content generation through the exact same dedup + human-review pipeline the UI
uses (an agent can DRAFT content, but publishing stays behind the human gate
in Content Review) and accept observed customer questions from the ghl-agent
as demand signals.

``/api/agent/openapi.json`` serves a scoped OpenAPI spec (just these
endpoints) for import as a Foundry OpenAPI tool.
"""

import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.brand import Brand
from app.models.content import ContentPiece, ContentQueue
from app.models.observed_question import ObservedQuestion
from app.routers.content import _generate_task, _parse_local_market

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent-api"])

VALID_CONTENT_TYPES = {"faq_hub", "local_page", "vertical_page", "comparison", "data_stats"}
VALID_QUESTION_SOURCES = {"call", "chat", "form"}


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
            "Citation figures reflect the latest audit run (audits run weekly, Mondays). "
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


class ObservedQuestionIn(BaseModel):
    brand_id: str = Field(description="Brand id, e.g. 'quality' — see /overview for the roster")
    question: str = Field(min_length=8, max_length=500, description="The customer's question, as close to verbatim as possible")
    source: str = Field(description="call | chat | form")
    asked_at: datetime | None = Field(default=None, description="When the customer asked (ISO 8601)")
    external_ref: str = Field(default="", max_length=200, description="Idempotency key, e.g. the GHL conversation id")


@router.post("/observed-questions", dependencies=[Depends(require_agent_key)])
async def agent_observed_questions(
    items: list[ObservedQuestionIn],
    db: AsyncSession = Depends(get_db),
):
    """Push real customer questions (from GHL calls/chats/forms) into the
    platform. They become the highest-trust demand signal: audited on AI
    engines weekly (query_source="ghl") and fed to topic discovery as the
    first-priority pool (source="observed_demand").

    Near-duplicate questions (Jaccard >= 0.75 vs the brand's last-180-days
    corpus, or a matching external_ref) are silently skipped and counted in
    ``duplicates``. Contract for the ghl-agent: POST a JSON array of
    {brand_id, question, source: call|chat|form, asked_at?, external_ref?}
    with the X-API-Key header."""
    from app.services.topic_discovery_service import queries_similar

    if not items:
        raise HTTPException(status_code=422, detail="Provide at least one question")

    known_brands = {b.id for b in (await db.execute(select(Brand))).scalars().all()}
    bad_brand = next((i.brand_id for i in items if i.brand_id not in known_brands), None)
    if bad_brand:
        raise HTTPException(status_code=404, detail=f"Unknown brand_id {bad_brand!r}; known: {sorted(known_brands)}")
    bad_source = next((i.source for i in items if i.source not in VALID_QUESTION_SOURCES), None)
    if bad_source:
        raise HTTPException(status_code=422, detail=f"source must be one of {sorted(VALID_QUESTION_SOURCES)}")

    cutoff = datetime.utcnow() - timedelta(days=180)
    existing_rows = (
        await db.execute(
            select(ObservedQuestion.brand_id, ObservedQuestion.question, ObservedQuestion.external_ref)
            .where(ObservedQuestion.created_at >= cutoff)
        )
    ).all()
    questions_by_brand: dict[str, list[str]] = {}
    refs_by_brand: dict[str, set[str]] = {}
    for brand_id, question, ref in existing_rows:
        questions_by_brand.setdefault(brand_id, []).append(question)
        if ref:
            refs_by_brand.setdefault(brand_id, set()).add(ref)

    accepted_ids: list[int] = []
    duplicates = 0
    for item in items:
        corpus = questions_by_brand.setdefault(item.brand_id, [])
        refs = refs_by_brand.setdefault(item.brand_id, set())
        if (item.external_ref and item.external_ref in refs) or any(
            queries_similar(item.question, q) for q in corpus
        ):
            duplicates += 1
            continue
        row = ObservedQuestion(
            brand_id=item.brand_id,
            question=item.question.strip(),
            source=item.source,
            asked_at=item.asked_at,
            external_ref=item.external_ref or None,
        )
        db.add(row)
        await db.flush()
        accepted_ids.append(row.id)
        corpus.append(item.question)
        if item.external_ref:
            refs.add(item.external_ref)

    return {"accepted": len(accepted_ids), "duplicates": duplicates, "ids": accepted_ids}


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
            "/api/agent/observed-questions": {
                "post": {
                    "operationId": "pushObservedQuestions",
                    "summary": (
                        "Push real customer questions (from GHL calls/chats/forms). They feed the "
                        "weekly citation audit (provenance 'ghl') and topic discovery as the "
                        "highest-trust demand pool. Near-duplicates are deduped server-side."
                    ),
                    "security": secured,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["brand_id", "question", "source"],
                                        "properties": {
                                            "brand_id": {"type": "string", "description": "Brand id from /overview"},
                                            "question": {"type": "string", "description": "The customer's question, near-verbatim (8-500 chars)"},
                                            "source": {"type": "string", "enum": ["call", "chat", "form"]},
                                            "asked_at": {"type": "string", "format": "date-time"},
                                            "external_ref": {"type": "string", "description": "Idempotency key, e.g. GHL conversation id"},
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "{accepted, duplicates, ids}"},
                        "404": {"description": "Unknown brand_id"},
                        "422": {"description": "Invalid source or empty batch"},
                    },
                }
            },
        },
    }
