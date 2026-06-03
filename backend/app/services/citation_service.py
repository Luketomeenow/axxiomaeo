import logging

import httpx

from app.config import get_settings
from app.models.brand import Brand
from app.schemas.citation import CitationResult
from app.services.geo_aeo_tracker_service import GeoAeoTrackerService
from app.utils.helpers import retry_with_backoff

logger = logging.getLogger(__name__)


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


class CitationService:
    def __init__(self):
        settings = get_settings()
        self.provider = settings.citation_provider.lower()
        self.peec = PeecService()
        self.geo_aeo = GeoAeoTrackerService()

    async def provider_available(self) -> bool:
        provider = self.provider
        if provider == "auto":
            if self.geo_aeo._configured():
                return await self.geo_aeo.health_check()
            return bool(get_settings().peec_api_key)
        if provider == "geo_aeo":
            return self.geo_aeo._configured() and await self.geo_aeo.health_check()
        if provider == "peec":
            return bool(get_settings().peec_api_key)
        return provider == "none"

    async def run_audit(self, brand: Brand, queries: list[str]) -> tuple[list[CitationResult], str]:
        provider = self.provider
        if provider == "auto":
            if self.geo_aeo._configured():
                provider = "geo_aeo"
            elif get_settings().peec_api_key:
                provider = "peec"
            else:
                provider = "none"

        try:
            if provider == "geo_aeo":
                results = await self.geo_aeo.get_citation_share(brand, queries)
                return results, "completed"
            if provider == "peec":
                results = await self.peec.get_citation_share(brand.name, queries)
                return results, "completed"
            if provider == "none":
                return [], "manual_required"
            logger.error("Unknown CITATION_PROVIDER: %s", provider)
            return [], "manual_required"
        except Exception as e:
            logger.error("Citation audit failed (%s): %s", provider, e)
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
