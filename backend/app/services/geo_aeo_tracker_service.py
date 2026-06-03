"""GEO/AEO Tracker integration — https://github.com/danishashko/geo-aeo-tracker

Calls the self-hosted tracker's POST /api/scrape endpoint (Bright Data AI scrapers
configured in the tracker app, not in this backend).
"""

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.models.brand import Brand
from app.schemas.citation import CitationResult
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)

VALID_PROVIDERS = frozenset(
    {"chatgpt", "perplexity", "copilot", "gemini", "google_ai", "grok"}
)

ELEVATOR_COMPETITORS = [
    "Otis",
    "KONE",
    "Schindler",
    "Thyssenkrupp",
    "TK Elevator",
    "Mitsubishi Electric",
]


@dataclass
class ScrapeResponse:
    provider: str
    prompt: str
    answer: str
    sources: list[str]


def brand_search_terms(brand: Brand) -> list[str]:
    terms = [brand.name]
    if brand.wp_url:
        host = urlparse(brand.wp_url).netloc.lower().replace("www.", "")
        if host:
            terms.append(host)
            base = host.split(".")[0]
            if len(base) > 3:
                terms.append(base.replace("-", " "))
    return list(dict.fromkeys(t for t in terms if t))


def website_domain(wp_url: str) -> str:
    return urlparse(wp_url).netloc.lower().replace("www.", "") if wp_url else ""


def find_mentions(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    found = []
    for term in terms:
        if term.lower() in lower:
            found.append(term)
    return found


def find_competitor(text: str) -> str | None:
    for name in ELEVATOR_COMPETITORS:
        if name.lower() in text.lower():
            return name
    return None


def analyze_scrape(
    scrape: ScrapeResponse,
    brand: Brand,
    terms: list[str],
) -> CitationResult:
    domain = website_domain(brand.wp_url)
    answer = scrape.answer or ""
    sources = scrape.sources or []

    mentioned = bool(find_mentions(answer, terms))
    domain_cited = bool(
        domain and any(domain in s.lower() for s in sources)
    )
    is_cited = mentioned or domain_cited

    citation_url = None
    if domain:
        for source in sources:
            if domain in source.lower():
                citation_url = source
                break
    if not citation_url and sources and is_cited:
        citation_url = sources[0]

    competitor = None if is_cited else find_competitor(answer)

    return CitationResult(
        query=scrape.prompt,
        is_cited=is_cited,
        competitor_cited=competitor,
        citation_url=citation_url,
        platform=scrape.provider,
    )


class GeoAeoTrackerService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.geo_aeo_tracker_url.rstrip("/")
        self.providers = [
            p.strip()
            for p in settings.geo_aeo_providers.split(",")
            if p.strip() in VALID_PROVIDERS
        ] or ["perplexity", "google_ai"]
        self.concurrency = max(1, settings.geo_aeo_concurrency)

    def _configured(self) -> bool:
        return bool(self.base_url)

    async def _scrape_one(self, provider: str, prompt: str) -> ScrapeResponse | None:
        timeout = httpx.Timeout(120.0, connect=5.0)

        async def do_request():
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/scrape",
                    json={
                        "provider": provider,
                        "prompt": prompt,
                        "requireSources": True,
                    },
                )
                if response.status_code >= 400:
                    detail = response.text[:500]
                    raise RuntimeError(f"GEO/AEO Tracker scrape failed ({response.status_code}): {detail}")
                data = response.json()
                if data.get("error"):
                    raise RuntimeError(data["error"])
                return ScrapeResponse(
                    provider=data.get("provider", provider),
                    prompt=data.get("prompt", prompt),
                    answer=data.get("answer", ""),
                    sources=data.get("sources") or [],
                )

        try:
            return await retry_with_backoff(do_request, max_retries=2)
        except Exception as exc:
            logger.warning("Scrape failed for provider=%s query=%r: %s", provider, prompt[:80], exc)
            return None

    async def get_citation_share(self, brand: Brand, queries: list[str]) -> list[CitationResult]:
        if not self._configured():
            raise RuntimeError("GEO_AEO_TRACKER_URL not configured")

        if not await self.health_check():
            raise RuntimeError(
                "GEO/AEO Tracker is not reachable at "
                f"{self.base_url} — start it with npm run dev and configure Bright Data keys"
            )

        terms = brand_search_terms(brand)
        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = []

        async def run_pair(provider: str, query: str):
            async with semaphore:
                scrape = await self._scrape_one(provider, query)
                if not scrape:
                    return None
                return analyze_scrape(scrape, brand, terms)

        for query in queries:
            for provider in self.providers:
                tasks.append(run_pair(provider, query))

        outcomes = await asyncio.gather(*tasks)
        results = [r for r in outcomes if r is not None]
        if not results:
            raise RuntimeError("GEO/AEO Tracker returned no results (is it running with Bright Data keys?)")
        return results

    async def health_check(self) -> bool:
        if not self._configured():
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code < 500
        except Exception:
            return False
