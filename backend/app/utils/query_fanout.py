"""Query fan-out expansion for citation audits.

Ahrefs AEO: one user prompt expands into many sub-queries at retrieval time.
We audit related phrasings per seed query to measure topic breadth — not as a
keyword list to chase, but as a window into what AI considers relevant.
"""

from __future__ import annotations

# Funnel stage per query bank category (Outwrite-style prompt segmentation)
CATEGORY_FUNNEL_STAGE: dict[str, str] = {
    "emergency": "decision",
    "research_evaluation": "consideration",
    "compliance_regulatory": "awareness",
    "vertical_specific": "consideration",
    "comparison_decision": "decision",
    "data_statistics": "awareness",
    "custom": "consideration",
}

# Gap category → content type for closed-loop publishing
CATEGORY_CONTENT_TYPE: dict[str, str] = {
    "emergency": "faq_hub",
    "research_evaluation": "faq_hub",
    "compliance_regulatory": "data_stats",
    "vertical_specific": "vertical_page",
    "comparison_decision": "comparison",
    "data_statistics": "data_stats",
    "custom": "faq_hub",
}


def _fanout_variants(query: str) -> list[str]:
    """Generate 1–2 natural phrasing variants for a seed query."""
    lower = query.lower().strip()
    variants: list[str] = []

    if lower.startswith("how "):
        rest = query[4:].strip().rstrip("?")
        variants.append(f"Who should I contact when {rest}?")
        variants.append(f"What are the best options for {rest}?")
    elif lower.startswith("what "):
        variants.append(f"Explain {query[5:].rstrip('?')}")
    elif "best " in lower:
        variants.append(query.replace("best ", "top rated ", 1))
    elif " vs " in lower or " versus " in lower:
        variants.append(f"Which is better: {query.rstrip('?')}?")
    elif "cost" in lower or "price" in lower or "how much" in lower:
        variants.append(f"Affordable options for {query.rstrip('?').lower()}")
    else:
        variants.append(f"Who should I contact for {query.rstrip('?').lower()}?")

    if "elevator" in lower and "near me" not in lower and "{" not in query:
        city_hint = ""
        if " in " in lower:
            city_hint = query[query.lower().rindex(" in ") :].strip()
        if city_hint:
            variants.append(f"elevator service near me {city_hint}")

    seen = {query.strip().lower()}
    out: list[str] = []
    for v in variants:
        key = v.strip().lower()
        if key not in seen and len(v) > 12:
            seen.add(key)
            out.append(v.strip())
        if len(out) >= 2:
            break
    return out


def expand_queries_with_fanout(
    items: list[dict],
    *,
    max_total: int = 30,
    fanout_per_seed: int = 1,
) -> list[dict]:
    """
    Expand seed queries with fan-out variants. Each item needs at least:
    query, category. Optional: funnel_stage.
    """
    expanded: list[dict] = []
    seen: set[str] = set()

    for item in items:
        seed = item["query"].strip()
        if not seed or seed.lower() in seen:
            continue
        seen.add(seed.lower())
        category = item.get("category", "custom")
        funnel = item.get("funnel_stage") or CATEGORY_FUNNEL_STAGE.get(category, "consideration")
        expanded.append(
            {
                "query": seed,
                "category": category,
                "parent_query": None,
                "funnel_stage": funnel,
            }
        )
        if len(expanded) >= max_total:
            break

        for variant in _fanout_variants(seed)[:fanout_per_seed]:
            if len(expanded) >= max_total:
                break
            if variant.lower() in seen:
                continue
            seen.add(variant.lower())
            expanded.append(
                {
                    "query": variant,
                    "category": category,
                    "parent_query": seed,
                    "funnel_stage": funnel,
                }
            )

    return expanded
