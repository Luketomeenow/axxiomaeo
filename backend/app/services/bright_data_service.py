"""Bright Data AI-search-API integration (native, no self-hosted tracker).

Calls Bright Data's Scrapers Library directly:
    POST https://api.brightdata.com/datasets/v3/scrape?dataset_id=<id>
    Authorization: Bearer <BRIGHT_DATA_API_KEY>
    body: {"input": [{"url": ..., "prompt": ...}, ...]}

The scrape can return either mode, confirmed live:
  * 200 with the record(s) inline (fast single Gemini/Perplexity calls), or
  * 202 with {"snapshot_id": "sd_..."} — the job runs async and must be polled
    at /datasets/v3/progress/<id> until "ready", then downloaded from
    /datasets/v3/snapshot/<id>?format=json. ChatGPT always does this, and any
    provider does it for a multi-query batch.

To avoid thousands of one-off scrapes, every query for a brand is sent to a
provider in a SINGLE batched request → one snapshot → records mapped back to
their query by the echoed `prompt` (fallback `index`). Reuses the
mention/competitor/aggregation logic from geo_aeo_tracker_service so detection
and scoring stay identical across providers.
"""

import asyncio
import json
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


def _parse_body(text: str):
    """Parse a Bright Data body that may be a single JSON value OR NDJSON.

    Snapshot downloads return newline-delimited JSON (one record per line) for
    multi-record results — .json() only works when there's exactly one line, so
    a batch download raises "Extra data". Try a whole-document parse first (job
    handle / array / single record), then fall back to line-by-line NDJSON.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    records: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


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
    PROGRESS_URL = "https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
    SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"

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
        self.poll_interval = max(2, settings.bright_data_poll_interval_seconds)
        self.max_polls = max(1, settings.bright_data_max_polls)

    def _configured(self) -> bool:
        return bool(self.api_key)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _download_snapshot(self, client: httpx.AsyncClient, snapshot_id: str) -> list[dict]:
        """Poll a snapshot to 'ready', then download its records."""
        headers = self._auth_headers()
        for _ in range(self.max_polls):
            pr = await client.get(self.PROGRESS_URL.format(snapshot_id=snapshot_id), headers=headers)
            status = pr.json().get("status") if pr.status_code == 200 else None
            if status == "ready":
                dl = await client.get(
                    self.SNAPSHOT_URL.format(snapshot_id=snapshot_id),
                    params={"format": "json"},
                    headers=headers,
                )
                if dl.status_code >= 400:
                    raise RuntimeError(f"Bright Data snapshot download failed ({dl.status_code}): {dl.text[:300]}")
                body = _parse_body(dl.text)
                if isinstance(body, list):
                    return [r for r in body if isinstance(r, dict)]
                if isinstance(body, dict):
                    inner = body.get("data")
                    return [r for r in inner if isinstance(r, dict)] if isinstance(inner, list) else [body]
                return []
            if status in ("failed", "error"):
                raise RuntimeError(f"Bright Data snapshot {snapshot_id} reported status={status}")
            await asyncio.sleep(self.poll_interval)
        raise RuntimeError(
            f"Bright Data snapshot {snapshot_id} not ready after {self.max_polls} polls "
            f"({self.max_polls * self.poll_interval}s)"
        )

    async def _resolve_records(self, client: httpx.AsyncClient, data) -> list[dict]:
        """Normalize a scrape response into a list of records, following the
        async snapshot indirection when the response is a 202 job handle."""
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            snapshot_id = data.get("snapshot_id")
            # A 202 job handle carries a snapshot_id and no answer content.
            if snapshot_id and not any(k in data for k in ("answer_text", "answer", "answer_html")):
                return await self._download_snapshot(client, snapshot_id)
            for key in ("data", "results"):
                v = data.get(key)
                if isinstance(v, list):
                    return [r for r in v if isinstance(r, dict)]
            return [data]  # a single inline record (200)
        return []

    async def _scrape_batch(self, provider: str, queries: list[str]) -> dict[str, dict]:
        """Scrape all queries for one provider in a single batched job.

        Returns {query: record}. Records map back to their query by the echoed
        `prompt`, falling back to `index`/position — Bright Data preserves input
        order but we don't rely on it.
        """
        dataset_id = self.dataset_ids.get(provider)
        if not dataset_id:
            logger.warning("No dataset id configured for provider=%s", provider)
            return {}
        extra = PROVIDER_EXTRA_INPUT.get(provider, {})
        inputs = [{"url": PROVIDER_URLS[provider], "prompt": q[:4096], **extra} for q in queries]
        timeout = httpx.Timeout(180.0, connect=10.0)

        async def do_request():
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.BASE_URL,
                    params={"dataset_id": dataset_id, "notify": "false", "include_errors": "true"},
                    headers={**self._auth_headers(), "Content-Type": "application/json"},
                    json={"input": inputs},
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"Bright Data scrape failed ({response.status_code}): {response.text[:400]}")
                return await self._resolve_records(client, _parse_body(response.text))

        try:
            records = await retry_with_backoff(do_request, max_retries=2)
        except Exception as exc:
            logger.warning(
                "Bright Data batch failed provider=%s (%d queries): %s", provider, len(queries), exc
            )
            return {}

        query_set = set(queries)
        by_query: dict[str, dict] = {}
        for i, rec in enumerate(records):
            if rec.get("error"):
                continue
            q = rec.get("prompt")
            if q not in query_set:
                idx = rec.get("index")
                if isinstance(idx, int) and 0 <= idx < len(queries):
                    q = queries[idx]
                elif i < len(queries):
                    q = queries[i]
                else:
                    q = None
            if q and q not in by_query:
                by_query[q] = rec
        if not by_query:
            logger.warning("Bright Data batch provider=%s returned %d records but none mapped to a query", provider, len(records))
        return by_query

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

        async def run_provider(provider: str) -> list[CitationResult]:
            async with semaphore:
                by_query = await self._scrape_batch(provider, queries)
                out: list[CitationResult] = []
                for q in queries:
                    rec = by_query.get(q)
                    if rec is None:
                        continue
                    scrape = ScrapeResponse(
                        provider=provider,
                        prompt=q,
                        answer=_extract_answer(rec),
                        sources=_extract_sources(rec),
                    )
                    cr = analyze_scrape(scrape, brand, terms)
                    qmeta = meta.get(q, QueryAuditMeta())
                    # Reuse the aggregation constructor (n=1) so parent_query /
                    # funnel_stage ride along and the record shape matches the
                    # sampled path exactly.
                    out.append(
                        aggregate_sample_results(
                            [cr],
                            parent_query=qmeta.parent_query,
                            funnel_stage=qmeta.funnel_stage,
                        )
                    )
                return out

        outcomes = await asyncio.gather(*[run_provider(p) for p in self.providers])
        results = [r for lst in outcomes for r in lst]
        if not results:
            raise RuntimeError(
                "Bright Data returned no results (check API key, dataset ids, and snapshot status)"
            )
        return results
