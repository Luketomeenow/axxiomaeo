"""Daily posting-cadence monitor.

Checks each brand's LIVE WordPress site (public REST API) — not our own DB —
so it verifies what readers and AI crawlers actually see. A brand whose
publish pipeline silently fails (expired app password, Cloudflare block,
broken endpoint) shows up here as "no posts today" even if the backend
believes it published.

Alerts go through NotificationService with type="posting_alert", which routes
to the general Discord channel (same one that announces published posts),
plus Slack and the in-app notification list. Silent when everything is
healthy.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.brand import Brand
from app.services.notification_service import NotificationService, record_worker_error
from app.services.schema_crawl import BROWSER_HEADERS

logger = logging.getLogger(__name__)

# Content generation runs at 09:00 America/Chicago and auto-publishes as
# drafts validate; the monitor runs mid-afternoon (see scheduler), so "no
# posts today" means the day's pipeline genuinely produced nothing live.
_TZ = ZoneInfo("America/Chicago")
_WINDOW_DAYS = 7


async def _fetch_post_days(client: httpx.AsyncClient, wp_url: str) -> Counter | None:
    """Days → post counts from the site's public API, or None if unreachable.

    WP returns site-local dates; all brand sites are US timezones within 2h of
    America/Chicago, so comparing date strings against a Chicago "today" is
    safe everywhere except the midnight edge, where the monitor never runs.
    """
    after = (datetime.now(_TZ) - timedelta(days=_WINDOW_DAYS)).strftime("%Y-%m-%dT00:00:00")
    url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    try:
        resp = await client.get(
            url,
            params={"per_page": 100, "after": after, "_fields": "date", "orderby": "date"},
        )
        if resp.status_code >= 400:
            logger.warning("Posting monitor: %s returned HTTP %s", url, resp.status_code)
            return None
        posts = resp.json()
        if not isinstance(posts, list):
            logger.warning("Posting monitor: %s returned non-list payload", url)
            return None
        return Counter(p["date"][:10] for p in posts if isinstance(p, dict) and p.get("date"))
    except Exception as e:
        logger.warning("Posting monitor: failed to reach %s: %s", url, e)
        return None


def _brand_status(name: str, days: Counter | None, today: str) -> tuple[bool, str]:
    """(is_failing, human line) for one brand."""
    if days is None:
        return True, f"⚠️ {name}: could not check — site/API unreachable from the monitor"
    posts_today = days.get(today, 0)
    if posts_today > 0:
        return False, f"✅ {name}: {posts_today} post(s) today"
    if not days:
        return True, f"❌ {name}: no posts in the last {_WINDOW_DAYS} days"
    last_day = max(days)
    silent = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(last_day, "%Y-%m-%d")).days
    return True, f"❌ {name}: no posts today — last post {last_day} ({silent} day(s) ago)"


async def check_posting() -> tuple[list[str], list[str]]:
    """Check every brand's live site; returns (failing, healthy) status lines."""
    async with AsyncSessionLocal() as session:
        brands = list((await session.execute(select(Brand))).scalars().all())

    today = datetime.now(_TZ).strftime("%Y-%m-%d")
    failing: list[str] = []
    healthy: list[str] = []

    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True
    ) as client:
        for brand in brands:
            if not brand.wp_url:
                continue
            days = await _fetch_post_days(client, brand.wp_url)
            is_failing, line = _brand_status(brand.name, days, today)
            (failing if is_failing else healthy).append(line)

    return failing, healthy


async def alert_failures(failing: list[str], healthy: list[str]) -> None:
    body_lines = failing + (["", "Posting normally: " + "; ".join(healthy)] if healthy else [])
    body = "\n".join(body_lines)
    title = f"Posting alert: {len(failing)} brand(s) not publishing"
    logger.warning("Posting monitor: %s\n%s", title, body)

    async with AsyncSessionLocal() as session:
        await NotificationService(session).create(
            type="posting_alert",
            title=title,
            body=body,
        )
        # Persist for the worker-error dashboard too; the notification above
        # already alerts, so notify=False avoids a double post.
        await record_worker_error(
            session,
            "posting_monitor",
            f"{len(failing)} brand(s) with no posts today",
            error_details={"failing": failing},
            notify=False,
        )
        await session.commit()


async def run_posting_monitor():
    settings = get_settings()
    if not settings.posting_monitor_enabled:
        logger.info("Posting monitor disabled (POSTING_MONITOR_ENABLED=false)")
        return

    logger.info("Starting posting-cadence monitor")
    failing, healthy = await check_posting()

    if not failing:
        logger.info("Posting monitor: all %d brands posted today", len(healthy))
        return

    await alert_failures(failing, healthy)
