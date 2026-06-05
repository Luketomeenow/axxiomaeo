import asyncio
import base64
import json
import logging
from datetime import date, timedelta

from app.config import get_settings

logger = logging.getLogger(__name__)


class GSCService:
    def __init__(self):
        self._credentials = None

    def _get_credentials(self):
        if self._credentials:
            return self._credentials
        sa_json = get_settings().google_service_account_json
        if not sa_json:
            return None
        try:
            from google.oauth2 import service_account

            info = json.loads(base64.b64decode(sa_json).decode())
            self._credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
            )
            return self._credentials
        except Exception as e:
            logger.warning("GSC credentials error: %s", e)
            return None

    async def get_featured_snippets(self, site_url: str, queries: list[str]) -> list[dict]:
        return await asyncio.to_thread(self._get_featured_snippets_sync, site_url, queries)

    def _get_featured_snippets_sync(self, site_url: str, queries: list[str]) -> list[dict]:
        creds = self._get_credentials()
        if not creds:
            return [{"query": q, "clicks": 0, "impressions": 0, "position": 0, "has_featured_snippet": False} for q in queries]

        try:
            from googleapiclient.discovery import build

            service = build("searchconsole", "v1", credentials=creds)
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            body = {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 100,
            }
            response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
            rows = response.get("rows", [])
            results = []
            query_data = {r["keys"][0]: r for r in rows}
            for q in queries:
                row = query_data.get(q, {})
                results.append(
                    {
                        "query": q,
                        "clicks": row.get("clicks", 0),
                        "impressions": row.get("impressions", 0),
                        "position": row.get("position", 0),
                        "has_featured_snippet": row.get("position", 99) <= 1,
                    }
                )
            return results
        except Exception as e:
            logger.warning("GSC query failed: %s", e)
            return [{"query": q, "clicks": 0, "impressions": 0, "position": 0, "has_featured_snippet": False} for q in queries]
