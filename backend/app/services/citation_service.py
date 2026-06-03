import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)


@dataclass
class CitationResult:
    query: str
    is_cited: bool
    competitor_cited: str | None = None
    citation_url: str | None = None
    platform: str = "google_ai"


class PeecService:
    BASE_URL = "https://api.peec.ai/v1"

    def __init__(self):
        self.api_key = get_settings().peec_api_key

    async def get_citation_share(self, brand_name: str, queries: list[str]) -> list[CitationResult]:
        if not self.api_key:
            raise RuntimeError("PEEC_API_KEY not configured")

        async def do_request():
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/citations/check",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"brand_name": brand_name, "queries": queries},
                )
                response.raise_for_status()
                return response.json()

        data = await retry_with_backoff(do_request)
        results = []
        for item in data.get("results", data if isinstance(data, list) else []):
            results.append(
                CitationResult(
                    query=item.get("query", ""),
                    is_cited=item.get("cited", item.get("is_cited", False)),
                    competitor_cited=item.get("competitor_cited"),
                    citation_url=item.get("citation_url"),
                    platform=item.get("platform", "google_ai"),
                )
            )
        return results

    async def get_trend_data(self, brand_name: str, days: int = 30) -> dict:
        if not self.api_key:
            return {"trend": [], "citation_share": 0}

        async def do_request():
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/citations/trends",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    params={"brand_name": brand_name, "days": days},
                )
                response.raise_for_status()
                return response.json()

        return await retry_with_backoff(do_request)


class CitationService:
    def __init__(self):
        self.peec = PeecService()

    async def run_audit(self, brand_name: str, queries: list[str]) -> tuple[list[CitationResult], str]:
        try:
            results = await self.peec.get_citation_share(brand_name, queries)
            return results, "completed"
        except Exception as e:
            logger.error("Peec.ai unavailable: %s", e)
            return [], "manual_required"

    def build_gap_list(self, results: list[CitationResult]) -> list[dict]:
        gaps = []
        for r in results:
            if not r.is_cited:
                gaps.append(
                    {
                        "query": r.query,
                        "competitor_cited": r.competitor_cited,
                        "platform": r.platform,
                    }
                )
        return gaps
