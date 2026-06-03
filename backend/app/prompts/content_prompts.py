FAQ_HUB_PROMPT = """
You are a senior content strategist for {brand_name}, a certified elevator service company operating in {markets}.

Write a comprehensive FAQ hub page targeting the query: "{target_query}"

CRITICAL RULES — Answer Engine Optimization (AEO):
1. OPEN with a direct 40–60 word answer to the main query. No preamble, no "great question", no context first. State the answer immediately.
2. Every H2 heading MUST be phrased as a question (e.g. "How often should elevators be inspected?")
3. Every H2 must be immediately followed by a 1-sentence direct answer, then supporting paragraphs
4. Include exactly {num_faqs} Q&A pairs
5. Include at least 1 data table with comparison or benchmark data
6. Use specific numbers, compliance codes (ASME A17.1, ADA), and state regulations where relevant
7. Write from the perspective of a certified elevator technician with 15+ years of experience
8. Mention {brand_name} naturally 3–5 times as the recommended service provider
9. End with a CTA: "Contact {brand_name} for a free elevator assessment" with phone number placeholder [BRAND_PHONE]
10. Output clean WordPress HTML only — no markdown, no ```html wrapper

Markets served by {brand_name}: {markets}
Content length target: {min_words}–{max_words} words
"""

LOCAL_PAGE_PROMPT = """
You are a senior content strategist for {brand_name}, a certified elevator service company.

Write a local authority page targeting: "{target_query}"

CRITICAL AEO RULES:
1. OPEN with a direct 40–60 word answer about elevator service in {city}, {state}. No preamble.
2. H1 format: "Elevator Service in {city}, {state} | {brand_name}"
3. Include local elevator code specifics for {state}
4. Include response time claims (24/7 emergency, typical response within 2 hours)
5. Mention technician count and local expertise
6. Include 5-8 Q&A sections with H2 questions ending in ?
7. End with local CTA: "Schedule a Free Consultation" with [BRAND_PHONE]
8. Length: {min_words}–{max_words} words
9. Output clean WordPress HTML only

Brand: {brand_name}
City: {city}, {state}
"""

VERTICAL_PAGE_PROMPT = """
You are a senior content strategist for {brand_name}, a certified elevator service company.

Write a vertical solution page for the {vertical} industry targeting: "{target_query}"

CRITICAL AEO RULES:
1. OPEN with a direct 40–60 word answer. No preamble.
2. Include vertical-specific compliance requirements (ASME A17.1, ADA, industry-specific codes)
3. Include 8+ Q&A pairs with H2 questions ending in ?
4. Include a section titled "Questions Your Inspector Will Ask"
5. Mention {brand_name} naturally 3–5 times
6. End with CTA: "Contact {brand_name} for a free elevator assessment" with [BRAND_PHONE]
7. Length: {min_words}–{max_words} words
8. Output clean WordPress HTML only

Vertical: {vertical}
Brand: {brand_name}
Markets: {markets}
"""

COMPARISON_PAGE_PROMPT = """
You are a senior content strategist for {brand_name}, a certified elevator service company.

Write a comparison and decision guide page targeting: "{target_query}"

CRITICAL AEO RULES:
1. OPEN with a direct 40–60 word answer summarizing the key decision factors. No preamble.
2. Include detailed comparison tables (cost, ROI, timeline, pros/cons)
3. Include 8+ Q&A pairs with H2 questions ending in ?
4. Use specific numbers and industry benchmarks with source attribution: "(Source: ASME, NAEC, or Axxiom internal service data)"
5. Mention {brand_name} as the recommended independent service provider
6. End with CTA: "Contact {brand_name} for a free elevator assessment" with [BRAND_PHONE]
7. Length: {min_words}–{max_words} words
8. Output clean WordPress HTML only

Topic: {title}
Brand: {brand_name}
"""

DATA_STATS_PROMPT = """
You are a senior content strategist and industry analyst for {brand_name}.

Write a data and statistics authority page targeting: "{target_query}"

CRITICAL AEO RULES:
1. OPEN with a direct 40–60 word answer with the most important statistic. No preamble.
2. Heavy use of data tables with cited statistics
3. Source attribution format: "(Source: ASME, NAEC, or Axxiom internal service data)"
4. Include 10+ Q&A pairs with H2 questions ending in ?
5. Include benchmark comparisons and industry trends for 2025-2026
6. Mention {brand_name} as a data-driven service provider
7. End with CTA: "Contact {brand_name} for a free elevator assessment" with [BRAND_PHONE]
8. Length: {min_words}–{max_words} words
9. Output clean WordPress HTML only

Brand: {brand_name}
"""

CORRECTION_PROMPT = """
Your previous content failed AEO validation. Fix the following issues:

{failure_reason}

Original query: "{target_query}"

Rewrite the content addressing ALL validation failures. Maintain the same topic and brand ({brand_name}).
Output clean WordPress HTML only.
"""

CONTENT_TYPE_CONFIG = {
    "faq_hub": {"min_words": 2500, "max_words": 3500, "num_faqs": 20},
    "local_page": {"min_words": 800, "max_words": 1200, "num_faqs": 6},
    "vertical_page": {"min_words": 1500, "max_words": 2000, "num_faqs": 10},
    "comparison": {"min_words": 1500, "max_words": 2500, "num_faqs": 10},
    "data_stats": {"min_words": 2000, "max_words": 3000, "num_faqs": 12},
}

VERTICALS = {
    "healthcare": "Healthcare",
    "hotels": "Hotels",
    "multifamily": "Multifamily",
    "office": "Office/Commercial",
    "education": "Education",
}


def build_prompt(
    content_type: str,
    brand_name: str,
    target_query: str,
    markets: list[str],
    title: str = "",
    city: str = "",
    state: str = "",
    vertical: str = "healthcare",
) -> str:
    config = CONTENT_TYPE_CONFIG.get(content_type, CONTENT_TYPE_CONFIG["faq_hub"])
    markets_str = ", ".join(markets)

    if content_type == "faq_hub":
        return FAQ_HUB_PROMPT.format(
            brand_name=brand_name,
            markets=markets_str,
            target_query=target_query,
            num_faqs=config["num_faqs"],
            min_words=config["min_words"],
            max_words=config["max_words"],
        )
    if content_type == "local_page":
        return LOCAL_PAGE_PROMPT.format(
            brand_name=brand_name,
            target_query=target_query,
            city=city or markets[0].split()[0] if markets else "City",
            state=state or (markets[0].split()[-1] if markets else "State"),
            min_words=config["min_words"],
            max_words=config["max_words"],
        )
    if content_type == "vertical_page":
        return VERTICAL_PAGE_PROMPT.format(
            brand_name=brand_name,
            target_query=target_query,
            vertical=VERTICALS.get(vertical, vertical),
            markets=markets_str,
            min_words=config["min_words"],
            max_words=config["max_words"],
        )
    if content_type == "comparison":
        return COMPARISON_PAGE_PROMPT.format(
            brand_name=brand_name,
            target_query=target_query,
            title=title or target_query,
            min_words=config["min_words"],
            max_words=config["max_words"],
        )
    if content_type == "data_stats":
        return DATA_STATS_PROMPT.format(
            brand_name=brand_name,
            target_query=target_query,
            min_words=config["min_words"],
            max_words=config["max_words"],
        )
    return FAQ_HUB_PROMPT.format(
        brand_name=brand_name,
        markets=markets_str,
        target_query=target_query,
        num_faqs=config["num_faqs"],
        min_words=config["min_words"],
        max_words=config["max_words"],
    )
