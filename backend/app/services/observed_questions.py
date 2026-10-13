"""Saving observed customer questions — one path for every source.

The Agent API (questions pushed by the GHL agent) and the daily scan of
CallRail call summaries both store through store_observed_questions, so
dedupe and idempotency behave the same everywhere: a question near-identical
(Jaccard >= 0.75) to one the brand already has from the last 180 days, or one
whose external_ref was already stored for that brand, is skipped and counted
as a duplicate.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observed_question import ObservedQuestion


async def store_observed_questions(db: AsyncSession, items: list[dict]) -> dict:
    """Insert the new questions. Each item: brand_id, question, source
    (call | chat | form), and optional asked_at, external_ref, detail."""
    from app.services.topic_discovery_service import queries_similar

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
        question = (item.get("question") or "").strip()
        external_ref = item.get("external_ref") or None
        corpus = questions_by_brand.setdefault(item["brand_id"], [])
        refs = refs_by_brand.setdefault(item["brand_id"], set())
        if (external_ref and external_ref in refs) or any(
            queries_similar(question, q) for q in corpus
        ):
            duplicates += 1
            continue
        row = ObservedQuestion(
            brand_id=item["brand_id"],
            question=question,
            source=item["source"],
            asked_at=item.get("asked_at"),
            external_ref=external_ref,
            detail=item.get("detail"),
        )
        db.add(row)
        await db.flush()
        accepted_ids.append(row.id)
        corpus.append(question)
        if external_ref:
            refs.add(external_ref)

    return {"accepted": len(accepted_ids), "duplicates": duplicates, "ids": accepted_ids}
