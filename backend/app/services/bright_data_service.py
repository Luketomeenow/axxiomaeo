"""Bright Data AI-search-API integration (native, no self-hosted tracker).

Bright Data's AI scrapers are ASYNCHRONOUS: a trigger returns a snapshot_id,
you poll progress, then download the finished records. Flow:
    POST https://api.brightdata.com/datasets/v3/scrape?dataset_id=<id>  -> {snapshot_id}
    GET  https://api.brightdata.com/datasets/v3/progress/{snapshot_id}  -> {status}
    GET  https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json -> [records]

Scrapes are slow (minutes each), so all of a brand's queries for one engine are
sent as ONE batch -> one snapshot -> one download, instead of one call per query.

Reuses the mention/competitor/aggregation logic from geo_aeo_tracker_service so
detection and scoring stay identical across providers.
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

logger = logging.getLogger(__name__)

TRIGGER_URL = "https://api.brightdata.com/datasets/v3/scrape"
PROGRESS_URL = "https://api.brightdata.com/datasets/v3/progress/{sid}"
SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{sid}"

# The chat URL each scraper drives.
PROVIDER_URLS = {
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/",
    "perplexity": "https://www.perplexity.ai",
}

# Per-provider optional input fields. Confirmed against live 400 validation
# errors: only ChatGPT's scraper accepts `web_search` (Gemini/Perplexity reject
# its presence and search natively anyway); NO scraper accepts `country`
# ("not available for this scraper"), so it's omitted entirely.
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
    Perplexity share the family but field names may vary, so sweep all known
    list-of-objects/strings and pull any url (or bare URL string).
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
        self.poll_interval = max(3, settings.bright_data_poll_seconds)
        self.max_wait = max(30, settings.bright_data_max_wait_seconds)

    def _configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _trigger(self, dataset_id: str, inputs: list[dict]) -> tuple[str | None, list | None]:
        """Start a batch scrape. Returns (snapshot_id, None) for the normal
        async path, or (None, records) if a dataset ever returns inline."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            r = await client.post(
                TRIGGER_URL,
                params={"dataset_id": dataset_id, "notify": "false", "include_errors": "true"},
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"input": inputs},
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Bright Data trigger failed ({r.status_code}): {r.text[:300]}")
            data = r.json()
            if isinstance(data, dict) and data.get("snapshot_id"):
                return data["snapshot_id"], None
            if isinstance(data, list):
                return None, data
            if isinstance(data, dict):
                recs = data.get("data") or data.get("results")
                if isinstance(recs, list):
                    return None, recs
            raise RuntimeError(f"Bright Data trigger: unexpected response {str(data)[:200]}")

    async def _await_ready(self, snapshot_id: str) -> bool:
        waited = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            while waited < self.max_wait:
                r = await client.get(PROGRESS_URL.format(sid=snapshot_id), headers=self._headers())
                status = r.json().get("status") if r.status_code == 200 else None
                if status == "ready":
                    return True
                if status == "failed":
                    logger.warning("Bright Data snapshot %s failed", snapshot_id)
                    return False
                await asyncio.sleep(self.poll_interval)
                waited += self.poll_interval
        logger.warning(
            "Bright Data snapshot %s not ready after %ss (low balance queues scrapes "
            "without running them — check account credit)", snapshot_id, self.max_wait,
        )
        return False

    async def _download(self, snapshot_id: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.get(
                SNAPSHOT_URL.format(sid=snapshot_id),
                params={"format": "json"},
                headers=self._headers(),
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Bright Data download failed ({r.status_code}): {r.text[:200]}")
            data = r.json()
            return data if isinstance(data, list) else [data]

    def _match_query(self, rec: dict, queries: list[str], prompt_to_query: dict[str, str]) -> str | None:
        idx = rec.get("index")
        if isinstance(idx, int) and 0 <= idx < len(queries):
            return queries[idx]
        return prompt_to_query.get((rec.get("prompt") or "")[:4096])

    async def _run_provider(
        self, brand: Brand, provider: str, queries: list[str], terms: list[str], meta: dict
    ) -> list[CitationResult]:
        dataset_id = self.dataset_ids.get(provider)
        if not dataset_id:
            logger.warning("No dataset id for provider=%s", provider)
            return []
        extra = PROVIDER_EXTRA_INPUT.get(provider, {})
        # One batch: each query repeated sample_runs times, tagged with its index.
        inputs = [
            {"url": PROVIDER_URLS[provider], "prompt": q[:4096], "index": i, **extra}
            for i, q in enumerate(queries)
            for _ in range(self.sample_runs)
        ]
        try:
            snapshot_id, inline = await self._trigger(dataset_id, inputs)
            if inline is not None:
                records = inline
            elif snapshot_id and await self._await_ready(snapshot_id):
                records = await self._download(snapshot_id)
            else:
                records = []
        except Exception as exc:
            logger.warning("Bright Data provider=%s failed: %s", provider, exc)
            return []

        prompt_to_query = {q[:4096]: q for q in queries}
        samples_by_query: dict[str, list[CitationResult]] = {q: [] for q in queries}
        for rec in records:
            if not isinstance(rec, dict) or rec.get("error"):
                continue
            query = self._match_query(rec, queries, prompt_to_query)
            if query is None:
                continue
            scrape = ScrapeResponse(
                provider=provider,
                prompt=query,
                answer=_extract_answer(rec),
                sources=_extract_sources(rec),
            )
            samples_by_query[query].append(analyze_scrape(scrape, brand, terms))

        results: list[CitationResult] = []
        for query, samples in samples_by_query.items():
            if not samples:
                continue
            qmeta = meta.get(query, QueryAuditMeta())
            results.append(
                aggregate_sample_results(
                    samples, parent_query=qmeta.parent_query, funnel_stage=qmeta.funnel_stage
                )
            )
        return results

    async def get_citation_share(
        self,
        brand: Brand,
        queries: list[str],
        query_meta: dict[str, QueryAuditMeta] | None = None,
    ) -> list[CitationResult]:
        if not self._configured():
            raise RuntimeError("BRIGHT_DATA_API_KEY not configured")

        terms = brand_search_terms(brand)
        meta = query_meta or {}
        semaphore = asyncio.Semaphore(self.concurrency)

        async def guarded(provider: str) -> list[CitationResult]:
            async with semaphore:
                return await self._run_provider(brand, provider, queries, terms, meta)

        outcomes = await asyncio.gather(*[guarded(p) for p in self.providers])
        results = [r for group in outcomes for r in group]
        if not results:
            raise RuntimeError(
                "Bright Data returned no results — scrapes may be queued but not "
                "running (check account balance), or check the API key and dataset ids"
            )
        return results
