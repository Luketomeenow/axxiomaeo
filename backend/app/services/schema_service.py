import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.models.brand import Brand
from app.models.content import ContentPiece


def _wrap_json_ld(data: dict) -> str:
    return json.dumps(data, indent=2)


def _brand_phone(brand: Brand) -> str | None:
    """Brand phone usable in published output — never the [BRAND_PHONE] token."""
    phone = (brand.phone or "").strip()
    if not phone or phone == "[BRAND_PHONE]":
        return None
    return phone


def build_organization_schema(brand: Brand) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand.name,
        "alternateName": brand.name,
        "url": brand.wp_url,
        "logo": brand.logo_url or f"{brand.wp_url}/wp-content/uploads/logo.png",
        "description": f"{brand.name} provides certified elevator maintenance, repair, modernization, and installation services.",
        "areaServed": brand.markets or [],
        "numberOfEmployees": {"@type": "QuantitativeValue", "minValue": 50, "maxValue": 500},
        "foundingDate": "2023",
    }
    phone = _brand_phone(brand)
    if phone:
        schema["contactPoint"] = {
            "@type": "ContactPoint",
            "telephone": phone,
            "contactType": "customer service",
            "availableLanguage": "English",
            "hoursAvailable": "24/7",
        }
    if not brand.is_corporate:
        schema["parentOrganization"] = {
            "@type": "Organization",
            "name": "Axxiom Elevator",
            "url": "https://axxiomelevator.com",
        }
    return _wrap_json_ld(schema)


def build_local_business_schema(brand: Brand, city: str = "") -> str:
    primary_city = city or (brand.markets[0] if brand.markets else "National")
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": brand.name,
        "url": brand.wp_url,
        "priceRange": "$$",
        "openingHours": "Mo-Su 00:00-23:59",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": primary_city.split()[0] if primary_city else "",
            "addressRegion": primary_city.split()[-1] if " " in primary_city else "",
            "addressCountry": "US",
        },
        "serviceArea": [
            {"@type": "GeoCircle", "geoMidpoint": {"@type": "GeoCoordinates"}, "geoRadius": "50000"}
            for _ in (brand.markets or ["National"])
        ],
    }
    phone = _brand_phone(brand)
    if phone:
        schema["telephone"] = phone
    return _wrap_json_ld(schema)


def _normalize_faq_items(items: list) -> list[dict]:
    faqs: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        question = item.get("question") or item.get("q") or item.get("name")
        answer = item.get("answer") or item.get("a") or item.get("text")
        if question and answer:
            faqs.append({"question": str(question).strip(), "answer": str(answer).strip()})
    return faqs


def _faqs_from_faqpage_object(data: dict) -> list[dict]:
    if data.get("@type") != "FAQPage":
        return []
    entities = data.get("mainEntity") or []
    if not isinstance(entities, list):
        entities = [entities]
    faqs: list[dict] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        question = entity.get("name")
        accepted = entity.get("acceptedAnswer") or {}
        answer = accepted.get("text") if isinstance(accepted, dict) else None
        if question and answer:
            faqs.append({"question": str(question).strip(), "answer": str(answer).strip()})
    return faqs


def parse_faqs_from_text(text: str) -> list[dict]:
    """
    Parse FAQ question/answer pairs from plain text, JSON, or HTML.

    Supported plain-text formats:
    - Q: ... / A: ... blocks
    - Question line ending with ? followed by answer paragraph(s)
    - JSON array: [{"question": "...", "answer": "..."}]
    - Existing FAQPage JSON-LD object
    - HTML with <h2>Question?</h2> + following content (same as content publish)
    """
    raw = text.strip()
    if not raw:
        return []

    if re.search(r"<h[1-6][^>]*>", raw, re.IGNORECASE):
        return extract_faqs_from_html(raw)

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return _normalize_faq_items(parsed)
        if isinstance(parsed, dict):
            if parsed.get("@type") == "FAQPage":
                return _faqs_from_faqpage_object(parsed)
            if "mainEntity" in parsed:
                return _faqs_from_faqpage_object(parsed)
            if "question" in parsed and "answer" in parsed:
                return _normalize_faq_items([parsed])
    except json.JSONDecodeError:
        pass

    qa_blocks = re.findall(
        r"(?:^|\n)\s*Q(?:uestion)?\s*:\s*(.+?)\s*\n\s*A(?:nswer)?\s*:\s*(.+?)(?=\n\s*Q(?:uestion)?\s*:|\Z)",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if qa_blocks:
        return [
            {"question": q.strip(), "answer": a.strip()}
            for q, a in qa_blocks
            if q.strip() and a.strip()
        ]

    faqs: list[dict] = []
    blocks = re.split(r"\n\s*\n", raw)
    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if not block:
            i += 1
            continue
        lines = block.split("\n", 1)
        headline = lines[0].strip().lstrip("#").strip()
        if headline.endswith("?"):
            answer = lines[1].strip() if len(lines) > 1 else ""
            if not answer and i + 1 < len(blocks):
                nxt = blocks[i + 1].strip()
                if nxt and not nxt.split("\n", 1)[0].strip().endswith("?"):
                    answer = nxt
                    i += 1
            if answer:
                faqs.append({"question": headline, "answer": answer})
        i += 1

    return faqs


def build_faqpage_from_text(text: str) -> tuple[str, list[dict]]:
    """Turn FAQ text into FAQPage JSON-LD. Returns (json_string, parsed_faqs)."""
    faqs = parse_faqs_from_text(text)
    if not faqs:
        raise ValueError(
            "No FAQ pairs found. Use Q:/A: blocks, JSON [{question, answer}], "
            "or HTML with <h2>Question?</h2> followed by answer content."
        )
    return build_faqpage_schema(faqs), faqs


def extract_faqs_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    faqs = []
    h2_tags = soup.find_all("h2")
    for h2 in h2_tags:
        question = h2.get_text(strip=True)
        if not question.endswith("?"):
            continue
        answer_parts = []
        for sibling in h2.find_next_siblings():
            if sibling.name == "h2":
                break
            if sibling.name in ("p", "ul", "ol", "div"):
                answer_parts.append(sibling.get_text(strip=True))
        answer = " ".join(answer_parts)[:2000]
        if answer:
            faqs.append({"question": question, "answer": answer})
    return faqs


def build_faqpage_schema(faqs: list[dict]) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {"@type": "Answer", "text": faq["answer"]},
            }
            for faq in faqs
        ],
    }
    return _wrap_json_ld(schema)


def _service_page_url(brand: Brand, service_type: str) -> str | None:
    urls = brand.service_page_urls or {}
    if not urls:
        return None
    key = service_type.lower()
    for k, v in urls.items():
        if k.lower() in key or key in k.lower():
            return v
    return urls.get(service_type)


def build_service_schema(brand: Brand, service_type: str) -> str:
    service_url = _service_page_url(brand, service_type)
    phone = _brand_phone(brand)
    available_channel: dict = {
        "@type": "ServiceChannel",
        "availableLanguage": "English",
    }
    if phone:
        available_channel["servicePhone"] = {"@type": "ContactPoint", "telephone": phone}
    schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": service_type,
        "serviceType": service_type,
        "provider": {"@type": "Organization", "name": brand.name, "url": brand.wp_url},
        "areaServed": brand.markets or [],
        "availableChannel": available_channel,
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": f"{brand.name} Services",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": service_type}}
            ],
        },
    }
    if service_url:
        schema["url"] = service_url
    return _wrap_json_ld(schema)


def extract_author_from_html(html: str, brand: Brand) -> dict:
    """Author entity for Article schema. Always the brand's team as an
    Organization — never a named Person with a credential (the old
    Person + "IUEC-Certified" jobTitle asserted a certification we can't
    attest, in machine-readable form)."""
    return {"name": f"{brand.name} Team", "url": brand.wp_url}


def extract_images_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    images: list[dict] = []
    for figure in soup.find_all("figure", class_=re.compile(r"aeo-figure")):
        img = figure.find("img")
        if not img or not img.get("src"):
            continue
        figcaption = figure.find("figcaption")
        caption = figcaption.get_text(strip=True) if figcaption else img.get("alt", "")
        images.append(
            {
                "@type": "ImageObject",
                "url": img["src"],
                "contentUrl": img["src"],
                "description": caption or img.get("alt", ""),
                "caption": caption,
                "name": img.get("title") or img.get("alt", ""),
            }
        )
    if not images:
        for img in soup.find_all("img", class_=re.compile(r"aeo-content-image")):
            if not img.get("src"):
                continue
            images.append(
                {
                    "@type": "ImageObject",
                    "url": img["src"],
                    "contentUrl": img["src"],
                    "description": img.get("alt", ""),
                    "caption": img.get("alt", ""),
                    "name": img.get("title") or img.get("alt", ""),
                }
            )
    return images


def build_article_schema(post: ContentPiece, brand: Brand, author: dict | None = None, html: str = "") -> str:
    if author is None and html:
        author = extract_author_from_html(html, brand)
    author = author or {"name": f"{brand.name} Team", "url": brand.wp_url}
    now = datetime.now(timezone.utc).isoformat()
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.title,
        "author": {
            "@type": "Organization",
            "name": author.get("name", f"{brand.name} Team"),
            "url": author.get("url", brand.wp_url),
        },
        "datePublished": (post.published_at or datetime.utcnow()).isoformat() if post.published_at else now,
        "dateModified": now,
        "publisher": {"@type": "Organization", "name": brand.name, "url": brand.wp_url},
        "wordCount": post.word_count or 0,
        "articleSection": post.content_type or "Elevator Services",
        "keywords": post.target_query or "",
    }
    if html:
        image_objects = extract_images_from_html(html)
        if image_objects:
            schema["image"] = image_objects
            schema["thumbnailUrl"] = image_objects[0].get("url")
    return _wrap_json_ld(schema)


def build_howto_schema(title: str, steps: list[str]) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": title,
        "step": [
            {"@type": "HowToStep", "position": i + 1, "text": step}
            for i, step in enumerate(steps)
        ],
    }
    return _wrap_json_ld(schema)


def extract_steps_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    ol = soup.find("ol")
    if ol:
        return [li.get_text(strip=True) for li in ol.find_all("li")]
    return []


_HOWTO_HEADING_HINTS = (
    "step", "protocol", "procedure", "process", "checklist", "how to",
    "what to do", "what should", "immediately", "do if", "respond", "guide to",
)


def extract_howto(html: str) -> tuple[str, list[str]]:
    """Find a step-by-step ordered list and the heading it sits under.

    Returns (name, steps). Only matches an ordered list that sits under an
    action/procedure heading (so a generic "top 5 reasons" <ol> isn't
    mislabeled as HowTo), with at least two steps. Empty steps => no HowTo.
    The heading becomes the HowTo name (more accurate than the article title).
    """
    soup = BeautifulSoup(html, "lxml")
    for ol in soup.find_all("ol"):
        items = [li.get_text(strip=True) for li in ol.find_all("li") if li.get_text(strip=True)]
        if len(items) < 2:
            continue
        prev = ol.find_previous(["h2", "h3", "h1"])
        heading = prev.get_text(strip=True) if prev else ""
        if any(hint in heading.lower() for hint in _HOWTO_HEADING_HINTS):
            return heading, items
    return "", []


def build_combined_schema(html: str, brand: Brand, title: str, content_type: str) -> tuple[str, list[str]]:
    """Build combined JSON-LD for content. Returns (json_string, schema_types)."""
    schemas = []
    types = []

    faqs = extract_faqs_from_html(html)
    if faqs:
        faq_data = json.loads(build_faqpage_schema(faqs))
        schemas.append(faq_data)
        types.append("FAQPage")

    article_data = json.loads(
        build_article_schema(
            ContentPiece(title=title, content_type=content_type, word_count=len(html.split())),
            brand,
            html=html,
        )
    )
    schemas.append(article_data)
    types.append("Article")

    howto_name, steps = extract_howto(html)
    if steps:
        howto_data = json.loads(build_howto_schema(howto_name or title, steps))
        schemas.append(howto_data)
        types.append("HowTo")

    if len(schemas) == 1:
        return json.dumps(schemas[0], indent=2), types
    return json.dumps(schemas, indent=2), types


def wrap_schema_script(json_ld: str) -> str:
    return f'<script type="application/ld+json">{json_ld}</script>'


# The five elevator service lines each brand gets a Service schema for.
SERVICE_TYPES = [
    "Elevator Maintenance",
    "Elevator Repair",
    "Elevator Modernization",
    "New Elevator Installation",
    "Elevator Inspection",
]


def build_brand_schema_set(brand: Brand) -> list[dict]:
    """The canonical brand-level JSON-LD set for a brand: Organization,
    LocalBusiness, and one Service per line (7 total).

    Titles are deterministic so a deployment can be matched back to its slot on
    redeploy — the daily publish worker uses the title to tell "already live"
    from "changed" from "missing". Shared by the manual deploy endpoint and the
    auto-publish worker so both produce identical schema.
    """
    items = [
        {
            "schema_type": "Organization",
            "title": f"{brand.name} - Organization Schema",
            "schema_json": build_organization_schema(brand),
        },
        {
            "schema_type": "LocalBusiness",
            "title": f"{brand.name} - LocalBusiness Schema",
            "schema_json": build_local_business_schema(brand),
        },
    ]
    for svc in SERVICE_TYPES:
        items.append(
            {
                "schema_type": "Service",
                "title": f"{brand.name} - {svc}",
                "schema_json": build_service_schema(brand, svc),
            }
        )
    return items
