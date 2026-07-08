"""Bright Data AI-search-API integration (native, no self-hosted tracker).

Calls Bright Data's Scrapers Library directly:
    POST https://api.brightdata.com/datasets/v3/scrape?dataset_id=<id>
    Authorization: Bearer <BRIGHT_DATA_API_KEY>
    body: {"input": [{"url": ..., "prompt": ..., "web_search": true, ...}]}

Reuses the mention/competitor/aggregation logic from geo_aeo_tracker_service so
detection and scoring stay identical across providers — this module only owns
the request shape and response parsing for Bright Data's native API.
"""

import asyncio
import logging

import httpx

from app.config import get_settings
from app.models.brand import Brand
from app.schemas.citation import CitationResult
from app.services.geo_aeo_tracker_service import (
    QueryAuditMeta,
    ScrapeResponse,
    aggregate_sample_results,
    analyze_scrape,
    brand_search_terms,
)
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)

# Each AI-search dataset: the chat URL Bright Data drives + its dataset id.
# Dataset ids are overridable via env (BRIGHT_DATA_DATASET_<PROVIDER>) in case
# Bright Data reassigns them — defaults are the current library ids.
PROVIDER_URLS = {
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/",
    "perplexity": "https://www.perplexity.ai",
}

# Per-provider extra input fields. web_search triggers ChatGPT's browsing so it
# cites live sources; Gemini and Perplexity REJECT the field (400 "should not
# contain a web_search field") because they browse by default. `country` is
# rejected by all three ("Selected country is not available"), so it is never
# sent — every input is just {url, prompt} plus whatever is listed here.
PROVIDER_EXTRA_INPUT = {
    "chatgpt": {"web_search": True},
}


def _extract_answer(rec: dict) -> str:
    for key in ("answer_text", "answer_text_markdown", "answer", "text", "response"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _extract_sources(rec: dict) -> list[str]:
    """Collect every cited/source URL from a Bright Data AI-search record.

    ChatGPT documents citations[], search_sources[], links_attached[]. Gemini/
    Perplexity use the same family but field names may vary, so we sweep all
    known list-of-objects/strings and pull any 'url' (or bare URL string).
    """
    urls: list[str] = []
    for key in ("citations", "search_sources", "links_attached", "sources", "links", "references"):
        items = rec.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                u = item.get("url") or item.get("link") or item.get("href")
                if isinstance(u, str) and u.strip():
                    urls.append(u)
            elif isinstance(item, str) and item.startswith("http"):
                urls.append(item)
    return list(dict.fromkeys(urls))  # dedupe, preserve order


class BrightDataService:
    BASE_URL = "https://api.brightdata.com/datasets/v3/scrape"

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.bright_data_api_key
        self.providers = [
            p.strip()
            for p in settings.bright_data_providers.split(",")
            if p.strip() in PROVIDER_URLS
        ] or ["chatgpt", "gemini", "perplexity"]
        self.dataset_ids = {
            "chatgpt": settings.bright_data_dataset_chatgpt,
            "gemini": settings.bright_data_dataset_gemini,
            "perplexity": settings.bright_data_dataset_perplexity,
        }
        self.concurrency = max(1, settings.bright_data_concurrency)
        self.sample_runs = max(1, settings.citation_sample_runs)

    def _configured(self) -> bool:
        return bool(self.api_key)

    async def _scrape_one(self, provider: str, prompt: str) -> ScrapeResponse | None:
        dataset_id = self.dataset_ids.get(provider)
        if not dataset_id:
            logger.warning("No dataset id configured for provider=%s", provider)
            return None
        timeout = httpx.Timeout(180.0, connect=10.0)
        payload = {
            "input": [
                {
                    "url": PROVIDER_URLS[provider],
                    "prompt": prompt[:4096],  # documented max
                    **PROVIDER_EXTRA_INPUT.get(provider, {}),
                }
            ]
        }

        async def do_request():
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.BASE_URL,
                    params={"dataset_id": dataset_id, "notify": "false", "include_errors": "true"},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"Bright Data scrape failed ({response.status_code}): {response.text[:400]}")
                data = response.json()
                # Sync scrape returns the result record(s): a list, or a dict
                # wrapping them under a common key.
                if isinstance(data, dict):
                    data = data.get("data") or data.get("results") or data.get("input") or [data]
                if not isinstance(data, list) or not data:
                    raise RuntimeError("Bright Data returned no result record")
                rec = data[0]
                if isinstance(rec, dict) and rec.get("error"):
                    raise RuntimeError(f"Bright Data record error: {rec.get('error')}")
                return ScrapeResponse(
                    provider=provider,
                    prompt=prompt,
                    answer=_extract_answer(rec),
                    sources=_extract_sources(rec),
                )

        try:
            return await retry_with_backoff(do_request, max_retries=2)
        except Exception as exc:
            logger.warning("Bright Data scrape failed provider=%s query=%r: %s", provider, prompt[:80], exc)
            return None

    async def get_citation_share(
        self,
        brand: Brand,
        queries: list[str],
        query_meta: dict[str, QueryAuditMeta] | None = None,
    ) -> list[CitationResult]:
        if not self._configured():
            raise RuntimeError("BRIGHT_DATA_API_KEY not configured")

        terms = brand_search_terms(brand)
        semaphore = asyncio.Semaphore(self.concurrency)
        meta = query_meta or {}

        async def run_samples(provider: str, query: str) -> CitationResult | None:
            async with semaphore:
                samples: list[CitationResult] = []
                for _ in range(self.sample_runs):
                    scrape = await self._scrape_one(provider, query)
                    if scrape:
                        samples.append(analyze_scrape(scrape, brand, terms))
                if not samples:
                    return None
                qmeta = meta.get(query, QueryAuditMeta())
                return aggregate_sample_results(
                    samples,
                    parent_query=qmeta.parent_query,
                    funnel_stage=qmeta.funnel_stage,
                )

        tasks = [run_samples(provider, query) for query in queries for provider in self.providers]
        outcomes = await asyncio.gather(*tasks)
        results = [r for r in outcomes if r is not None]
        if not results:
            raise RuntimeError("Bright Data returned no results (check API key, balance, and dataset ids)")
        return results
