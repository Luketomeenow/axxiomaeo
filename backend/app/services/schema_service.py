import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.models.brand import Brand
from app.models.content import ContentPiece


def _wrap_json_ld(data: dict) -> str:
    return json.dumps(data, indent=2)


def build_organization_schema(brand: Brand) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": brand.name,
        "alternateName": brand.name,
        "url": brand.wp_url,
        "logo": brand.logo_url or f"{brand.wp_url}/wp-content/uploads/logo.png",
        "description": f"{brand.name} provides certified elevator maintenance, repair, modernization, and installation services.",
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": brand.phone or "[BRAND_PHONE]",
            "contactType": "customer service",
            "availableLanguage": "English",
            "hoursAvailable": "24/7",
        },
        "areaServed": brand.markets or [],
        "numberOfEmployees": {"@type": "QuantitativeValue", "minValue": 50, "maxValue": 500},
        "foundingDate": "2023",
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
        "telephone": brand.phone or "[BRAND_PHONE]",
        "priceRange": "$$",
        "openingHours": "Mo-Su 00:00-23:59",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": primary_city.split()[0] if primary_city else "",
            "addressRegion": primary_city.split()[-1] if " " in primary_city else "",
            "addressCountry": "US",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.8",
            "reviewCount": "50",
        },
        "serviceArea": [
            {"@type": "GeoCircle", "geoMidpoint": {"@type": "GeoCoordinates"}, "geoRadius": "50000"}
            for _ in (brand.markets or ["National"])
        ],
    }
    return _wrap_json_ld(schema)


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
        answer = " ".join(answer_parts)[:500]
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


def build_service_schema(brand: Brand, service_type: str) -> str:
    schema = {
        "@context": "https://schema.org",
        "@type": "Service",
        "serviceType": service_type,
        "provider": {"@type": "Organization", "name": brand.name, "url": brand.wp_url},
        "areaServed": brand.markets or [],
        "availableChannel": {
            "@type": "ServiceChannel",
            "servicePhone": {"@type": "ContactPoint", "telephone": brand.phone or "[BRAND_PHONE]"},
            "availableLanguage": "English",
        },
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": f"{brand.name} Services",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": service_type}}
            ],
        },
    }
    return _wrap_json_ld(schema)


def build_article_schema(post: ContentPiece, brand: Brand, author: dict | None = None) -> str:
    author = author or {"name": "Axxiom Technical Team", "url": brand.wp_url}
    now = datetime.now(timezone.utc).isoformat()
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.title,
        "author": {
            "@type": "Person",
            "name": author.get("name", "Axxiom Technical Team"),
            "url": author.get("url", brand.wp_url),
        },
        "datePublished": (post.published_at or datetime.utcnow()).isoformat() if post.published_at else now,
        "dateModified": now,
        "publisher": {"@type": "Organization", "name": brand.name, "url": brand.wp_url},
        "wordCount": post.word_count or 0,
        "articleSection": post.content_type or "Elevator Services",
        "keywords": post.target_query or "",
    }
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
        )
    )
    schemas.append(article_data)
    types.append("Article")

    steps = extract_steps_from_html(html)
    if steps:
        howto_data = json.loads(build_howto_schema(title, steps))
        schemas.append(howto_data)
        types.append("HowTo")

    if len(schemas) == 1:
        return json.dumps(schemas[0], indent=2), types
    return json.dumps(schemas, indent=2), types


def wrap_schema_script(json_ld: str) -> str:
    return f'<script type="application/ld+json">{json_ld}</script>'
