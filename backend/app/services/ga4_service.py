import asyncio
import logging
from datetime import date, timedelta

from app.config import get_settings
from app.schemas.brand import normalize_ga4_property_id
from app.services.google_credentials import load_service_account_info

logger = logging.getLogger(__name__)

# Hosts whose referrals count as AI-assistant traffic. Matched case-insensitively
# with CONTAINS against GA4 sessionSource, so bare domains also cover www./m.
# variants. Override via AI_REFERRER_HOSTS (comma-separated) without a deploy.
AI_REFERRERS = [
    "chatgpt.com",
    "chat.openai.com",  # pre-2024 ChatGPT host — keep for historical ranges
    "perplexity.ai",
    "claude.ai",
    "gemini.google.com",
    "copilot.microsoft.com",
    "chat.deepseek.com",
    "grok.com",
    "meta.ai",
]


def _ai_referrer_hosts() -> list[str]:
    raw = get_settings().ai_referrer_hosts
    hosts = [h.strip() for h in raw.split(",") if h.strip()] if raw else []
    return hosts or AI_REFERRERS


def _ai_referrer_filter():
    """OR-group of case-insensitive CONTAINS filters on sessionSource."""
    from google.analytics.data_v1beta.types import Filter, FilterExpression, FilterExpressionList

    return FilterExpression(
        or_group=FilterExpressionList(
            expressions=[
                FilterExpression(
                    filter=Filter(
                        field_name="sessionSource",
                        string_filter=Filter.StringFilter(
                            match_type=Filter.StringFilter.MatchType.CONTAINS,
                            value=host,
                            case_sensitive=False,
                        ),
                    )
                )
                for host in _ai_referrer_hosts()
            ]
        )
    )


class GA4Service:
    def __init__(self):
        self._credentials = None

    def _get_credentials(self):
        if self._credentials:
            return self._credentials
        info = load_service_account_info(get_settings().google_service_account_json)
        if not info:
            return None
        try:
            from google.oauth2 import service_account

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
            from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

            client = BetaAnalyticsDataClient(credentials=creds)
            end = end_date or date.today().isoformat()
            start = start_date or (date.today() - timedelta(days=30)).isoformat()

            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[DateRange(start_date=start, end_date=end)],
                dimensions=[Dimension(name="sessionSource"), Dimension(name="landingPage")],
                metrics=[Metric(name="sessions"), Metric(name="conversions")],
                dimension_filter=_ai_referrer_filter(),
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
                dimension_filter=_ai_referrer_filter(),
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

    async def get_organic_search_sessions(
        self,
        property_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Sessions from traditional organic search (Google/Bing), excluding AI tools.

        Uses GA4's 'Organic Search' default channel group, which captures classic
        search-engine referrals and is distinct from the AI-referrer host list.
        """
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
                dimensions=[Dimension(name="sessionDefaultChannelGroup"), Dimension(name="landingPage")],
                metrics=[Metric(name="sessions"), Metric(name="conversions")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="sessionDefaultChannelGroup",
                        string_filter=Filter.StringFilter(value="Organic Search"),
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
            logger.warning("GA4 organic-search query failed: %s", e)
            return {"sessions": 0, "conversions": 0, "conversion_rate": 0, "top_landing_pages": []}

    def _fetch_organic_timeseries_sync(self, property_id: str, days: int = 90) -> list[dict]:
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
                date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="sessions")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="sessionDefaultChannelGroup",
                        string_filter=Filter.StringFilter(value="Organic Search"),
                    )
                ),
            )
            response = client.run_report(request)
            rows = []
            for row in response.rows:
                raw_date = row.dimension_values[0].value
                formatted = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                rows.append({"date": formatted, "sessions": int(row.metric_values[0].value)})
            rows.sort(key=lambda r: r["date"])
            return rows
        except Exception as e:
            logger.warning("GA4 organic timeseries query failed: %s", e)
            return []

    async def get_organic_search_sessions_timeseries(
        self,
        property_id: str,
        days: int = 90,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self._fetch_organic_timeseries_sync, property_id, days
        )

    async def get_event_counts_by_page(
        self,
        property_id: str,
        event_names: list[str],
        days: int = 30,
    ) -> list[dict] | None:
        """Counts of the named events (e.g. phone_call_click, form_submit) per
        page path over the last ``days``. None when GA4 can't be read, so the
        caller can tell "no events happened" from "no data"."""
        if not self._get_credentials() or not normalize_ga4_property_id(property_id):
            return None
        return await asyncio.to_thread(
            self._fetch_event_counts_by_page_sync, property_id, event_names, days
        )

    def _fetch_event_counts_by_page_sync(
        self, property_id: str, event_names: list[str], days: int
    ) -> list[dict] | None:
        creds = self._get_credentials()
        property_id = normalize_ga4_property_id(property_id)
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
            request = RunReportRequest(
                property=f"properties/{property_id}",
                date_ranges=[
                    DateRange(
                        start_date=(date.today() - timedelta(days=days)).isoformat(),
                        end_date=date.today().isoformat(),
                    )
                ],
                dimensions=[Dimension(name="eventName"), Dimension(name="pagePath")],
                metrics=[Metric(name="eventCount")],
                dimension_filter=FilterExpression(
                    filter=Filter(
                        field_name="eventName",
                        in_list_filter=Filter.InListFilter(values=list(event_names)),
                    )
                ),
                limit=10000,
            )
            response = client.run_report(request)
            return [
                {
                    "event": row.dimension_values[0].value,
                    "page": row.dimension_values[1].value,
                    "count": int(row.metric_values[0].value),
                }
                for row in response.rows
            ]
        except Exception as e:
            logger.warning("GA4 event-count query failed: %s", e)
            return None
