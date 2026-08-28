"""CallRail → AEO attribution: phone calls that started on platform content.

The marketing warehouse (same Postgres, ``public`` schema) ingests CallRail
call logs with each call's landing page. Joining those landing pages against
the posts this platform published answers the money question directly: which
articles make the phone ring. Phone calls are most of an elevator company's
real leads — web-form conversions undercount badly.

Read-only over ``public.fact_callrail_call``; the AEO app never writes to the
warehouse.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# One row per call (snapshots duplicate call_id), URL-normalized landing page,
# joined to published AEO posts by exact path match.
_ATTRIBUTION_SQL = text(r"""
WITH calls AS (
    SELECT DISTINCT ON (call_id)
           call_id, source, start_time,
           lower(answered::text) = 'true' AS answered,
           lower(first_time_caller::text) = 'true' AS first_time_caller,
           rtrim(lower(regexp_replace(
               split_part(split_part(landing_page_url, '?', 1), '#', 1),
               '^https?://(www\.)?', '')), '/') AS lp
    FROM public.fact_callrail_call
    WHERE start_time > now() - make_interval(days => :days)
      AND landing_page_url IS NOT NULL AND landing_page_url <> ''
    ORDER BY call_id, snapshot_date DESC
)
SELECT p.brand_id, p.title, p.wp_post_url,
       c.source, c.answered, c.first_time_caller, c.start_time
FROM calls c
JOIN aeo.content_pieces p
  ON p.status = 'published' AND p.wp_post_url IS NOT NULL
 AND c.lp = rtrim(lower(regexp_replace(
         split_part(p.wp_post_url, '?', 1), '^https?://(www\.)?', '')), '/')
 -- An article match requires a PATH. Draft posts carry '?p=<id>' URLs whose
 -- query-stripped form is the bare homepage — without this guard, every
 -- homepage call got credited to those "articles" (386 phantom calls found).
 AND position('/' in c.lp) > 0
""")


async def aeo_call_attribution(db: AsyncSession, days: int = 30) -> dict:
    """Calls whose landing page is an AEO-published article, aggregated for
    the Reports page. Returns zeros (with ``available: False``) when the
    warehouse table is missing/unreadable rather than failing the report."""
    try:
        rows = (await db.execute(_ATTRIBUTION_SQL, {"days": days})).all()
    except Exception:
        logger.exception("CallRail attribution query failed (warehouse unavailable?)")
        return {"available": False, "days": days, "total_calls": 0}

    by_brand: dict[str, dict] = {}
    by_post: dict[str, dict] = {}
    by_source: dict[str, int] = {}
    answered = first_time = 0

    for r in rows:
        b = by_brand.setdefault(r.brand_id, {"calls": 0, "answered": 0, "first_time": 0})
        b["calls"] += 1
        p = by_post.setdefault(
            r.wp_post_url,
            {"title": r.title, "url": r.wp_post_url, "brand_id": r.brand_id, "calls": 0},
        )
        p["calls"] += 1
        by_source[r.source or "unknown"] = by_source.get(r.source or "unknown", 0) + 1
        if r.answered:
            answered += 1
            b["answered"] += 1
        if r.first_time_caller:
            first_time += 1
            b["first_time"] += 1

    return {
        "available": True,
        "days": days,
        "total_calls": len(rows),
        "answered": answered,
        "first_time_callers": first_time,
        "by_brand": [
            {"brand_id": k, **v}
            for k, v in sorted(by_brand.items(), key=lambda x: -x[1]["calls"])
        ],
        "top_posts": sorted(by_post.values(), key=lambda x: -x["calls"])[:12],
        "by_source": sorted(
            ({"source": k, "calls": v} for k, v in by_source.items()),
            key=lambda x: -x["calls"],
        ),
    }
