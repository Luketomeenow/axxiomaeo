import asyncio
import base64
import json
import logging
from datetime import date, timedelta

from app.config import get_settings
from app.schemas.brand import normalize_ga4_property_id

logger = logging.getLogger(__name__)

AI_REFERRERS = [
    "chat.openai.com",
    "perplexity.ai",
    "claude.ai",
    "bard.google.com",
    "gemini.google.com",
]


class GA4Service:
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
            self._credentials = service_account.Credentials.from_service_account_info(info)
            return self._credentials
        except Exception as e:
            logger.warning("GA4 credentials error: %s", e)
            return None

    async def get_ai_referred_sessions(
        self,
        property_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        creds = self._get_credentials()
        property_id = normalize_ga4_property_id(property_id)
        if not creds or not property_id:
            return {"sessions": 0, "conversions": 0, "conversion_rate": 0, "top_landing_pages": []}

        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest

            client = BetaAnalyticsDataClient(credentials=creds)
            end = end_date or date.today().isoformat()
            start = start_date or (date.today() - timedelta(days=30)).isoformat()

            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start, end_date=end)],
                dimensions=[Dimension(name="sessionSource"), Dimension(name="landingPage")],
                metrics=[Metric(name="sessions"), Metric(name="conversions")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="sessionSource",
                        in_list_filter=Filter.InListFilter(values=AI_REFERRERS),
                    )
                ),
            )
            response = client.run_report(request)
            total_sessions = 0
            total_conversions = 0
            pages: dict[str, int] = {}
            for row in response.rows:
                sessions = int(row.metric_values[0].value)
                conversions = int(row.metric_values[1].value)
                total_sessions += sessions
                total_conversions += conversions
                page = row.dimension_values[1].value
                pages[page] = pages.get(page, 0) + sessions

            top_pages = sorted(pages.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                "sessions": total_sessions,
                "conversions": total_conversions,
                "conversion_rate": round(total_conversions / total_sessions * 100, 2) if total_sessions else 0,
                "top_landing_pages": [{"page": p, "sessions": s} for p, s in top_pages],
            }
        except Exception as e:
            logger.warning("GA4 query failed: %s", e)
            return {"sessions": 0, "conversions": 0, "conversion_rate": 0, "top_landing_pages": []}

    def _fetch_ai_referred_timeseries_sync(
        self,
        property_id: str,
        days: int = 90,
    ) -> list[dict]:
        creds = self._get_credentials()
        property_id = normalize_ga4_property_id(property_id)
        if not creds or not property_id:
            return []

        try:
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import (
                DateRange,
                Dimension,
                Filter,
                FilterExpression,
                Metric,
                RunReportRequest,
            )

            client = BetaAnalyticsDataClient(credentials=creds)
            end = date.today()
            start = end - timedelta(days=days)

            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[
                    DateRange(start_date=start.isoformat(), end_date=end.isoformat())
                ],
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="sessions")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="sessionSource",
                        in_list_filter=Filter.InListFilter(values=AI_REFERRERS),
                    )
                ),
            )
            response = client.run_report(request)
            rows = []
            for row in response.rows:
                raw_date = row.dimension_values[0].value
                formatted = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                rows.append(
                    {
                        "date": formatted,
                        "sessions": int(row.metric_values[0].value),
                    }
                )
            rows.sort(key=lambda r: r["date"])
            return rows
        except Exception as e:
            logger.warning("GA4 timeseries query failed: %s", e)
            return []

    async def get_ai_referred_sessions_timeseries(
        self,
        property_id: str,
        days: int = 90,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self._fetch_ai_referred_timeseries_sync, property_id, days
        )
