"""Pipeline flow health — diagnoses every stage of the daily content flow.

The August 2026 outage went unnoticed for days because each stage fails
silently in its own way: topic discovery queues 0 and logs INFO, the content
worker finds an empty queue and returns, a failed WP publish strands the
queue row in 'ready', and worker_errors was write-only. This service answers
"is the flow healthy, and if not, which stage broke and why" in one call.

Read-only by design: GET /api/health/flow polls it from the UI, so it must
never send alerts (the 10:30 flow_health worker does that) and never 500 —
every stage try/excepts down to a warn.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.approval import JobRun, Notification, WorkerError
from app.models.brand import Brand
from app.models.content import ContentDraft, ContentPiece, ContentQueue
from app.services.google_credentials import load_service_account_info

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("America/Chicago")

# Per-brand WP auth probe results — module-level TTL cache so a UI polling
# /api/health/flow doesn't hammer five WordPress sites. The manual
# test-connection endpoint writes through it via store_wp_auth_result.
_WP_AUTH_CACHE: dict[str, tuple[float, dict]] = {}
_WP_AUTH_TTL = 600.0


def store_wp_auth_result(brand_id: str, result: dict) -> None:
    _WP_AUTH_CACHE[brand_id] = (time.monotonic(), result)


def chicago_day_start_utc(now_utc: datetime | None = None) -> datetime:
    """Start of 'today' on the America/Chicago clock, as NAIVE UTC.

    Every scheduled job runs on the Chicago clock and every DB timestamp is
    naive datetime.utcnow, so day windows must be Chicago days converted to
    UTC — a plain UTC midnight would call 7-9pm CT posts "tomorrow's".
    """
    now = (now_utc or datetime.utcnow()).replace(tzinfo=ZoneInfo("UTC"))
    local_start = now.astimezone(_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def overall_status(stages: list[dict]) -> str:
    statuses = {s.get("status") for s in stages}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "ok"


def _stage(key: str, label: str, status: str, detail: str, metrics: dict) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail, "metrics": metrics}


class PipelineHealthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def check_flow(self, include_wp_auth: bool = True) -> dict:
        day_start = chicago_day_start_utc()
        now_ct = datetime.now(_TZ)

        stage_calls = (
            ("integrations", "Integrations", self._stage_integrations(include_wp_auth)),
            ("discovery", "Topic discovery (8am)", self._stage_discovery(day_start, now_ct)),
            ("generation", "Content generation (9am)", self._stage_generation(day_start)),
            ("publish", "Publishing", self._stage_publish(day_start, now_ct)),
            ("errors", "Worker errors (24h)", self._stage_errors()),
        )
        stages = []
        for key, label, coro in stage_calls:
            try:
                stages.append(await coro)
            except Exception as e:  # one broken probe must not 500 the endpoint
                logger.warning("Flow health stage %s failed: %s", key, e)
                stages.append(_stage(key, label, "warn", f"Check failed: {e}", {}))

        return {
            "checked_at": datetime.utcnow().isoformat(),
            "overall": overall_status(stages),
            "stages": stages,
        }

    async def _stage_integrations(self, include_wp_auth: bool) -> dict:
        from app.services.citation_service import CitationService
        from app.services.wordpress_service import WordPressService

        gsc_ok = load_service_account_info(self.settings.google_service_account_json) is not None
        try:
            citation_ok = await CitationService().provider_available()
        except Exception:
            citation_ok = False
        discord_ok = bool(self.settings.discord_webhook_url)

        brands = list((await self.db.execute(select(Brand))).scalars().all())
        wp_results: list[dict] = []
        if include_wp_auth:
            wp = WordPressService()
            now = time.monotonic()

            async def probe(brand: Brand) -> dict:
                if not self.settings.wp_publish_configured(brand.id):
                    return {
                        "brand_id": brand.id,
                        "ok": False,
                        "status_code": None,
                        "error": "No application password configured",
                        "cached": False,
                    }
                cached = _WP_AUTH_CACHE.get(brand.id)
                if cached and now - cached[0] < _WP_AUTH_TTL:
                    return {"brand_id": brand.id, **cached[1], "cached": True}
                result = await wp.check_connection(brand)
                store_wp_auth_result(brand.id, result)
                return {"brand_id": brand.id, **result, "cached": False}

            wp_results = list(await asyncio.gather(*(probe(b) for b in brands if b.wp_url)))
        else:
            # Fold in whatever the cache has; mark the rest unchecked.
            now = time.monotonic()
            for b in brands:
                cached = _WP_AUTH_CACHE.get(b.id)
                if cached and now - cached[0] < _WP_AUTH_TTL:
                    wp_results.append({"brand_id": b.id, **cached[1], "cached": True})

        wp_failed = [r["brand_id"] for r in wp_results if not r.get("ok")]
        problems = []
        if not gsc_ok:
            problems.append("Google service-account credential invalid (GSC/GA4 read 0)")
        if not citation_ok:
            problems.append("citation provider unavailable")
        if wp_failed:
            problems.append(f"WordPress auth failed: {', '.join(wp_failed)}")

        if problems:
            status = "fail"
            detail = "; ".join(problems)
        elif not discord_ok:
            status, detail = "warn", "Discord webhook not set — alerts only reach Slack/in-app"
        else:
            checked = "all brands verified" if include_wp_auth else "WP auth from cache"
            detail = f"GSC credential, citation provider, Discord webhook OK; {checked}"
            status = "ok"

        return _stage(
            "integrations", "Integrations", status, detail,
            {
                "gsc_credential": gsc_ok,
                "citation_provider": citation_ok,
                "discord_webhook": discord_ok,
                "wordpress": wp_results,
            },
        )

    async def _stage_discovery(self, day_start: datetime, now_ct: datetime) -> dict:
        rows = (
            await self.db.execute(
                select(ContentQueue.source, func.count(ContentQueue.id))
                .where(ContentQueue.created_at >= day_start)
                .group_by(ContentQueue.source)
            )
        ).all()
        by_source = {(src or "unknown"): n for src, n in rows}
        queued = sum(by_source.values())

        job_ran = bool(
            await self.db.scalar(
                select(func.count(JobRun.id)).where(
                    JobRun.job_id == "topic_discovery", JobRun.finished_at >= day_start
                )
            )
        )
        if not job_ran:
            # Pre-v14 fallback: the worker posts a topics_queued notification.
            job_ran = bool(
                await self.db.scalar(
                    select(func.count(Notification.id)).where(
                        Notification.type == "topics_queued",
                        Notification.created_at >= day_start,
                    )
                )
            )

        metrics = {"queued_today": queued, "by_source": by_source, "job_ran": job_ran}
        if queued > 0:
            return _stage("discovery", "Topic discovery (8am)", "ok",
                          f"{queued} topic(s) queued today", metrics)
        if now_ct.hour < 9:
            return _stage("discovery", "Topic discovery (8am)", "ok",
                          "8am discovery hasn't run yet today", metrics)
        if job_ran:
            return _stage(
                "discovery", "Topic discovery (8am)", "warn",
                "Job ran but queued 0 topics — demand pools may be exhausted or "
                "GSC/citation feeds down (see Integrations)", metrics)
        return _stage(
            "discovery", "Topic discovery (8am)", "fail",
            "No topics queued today and no record the 8am job ran", metrics)

    async def _stage_generation(self, day_start: datetime) -> dict:
        drafts_today = (
            await self.db.scalar(
                select(func.count(ContentDraft.id)).where(ContentDraft.created_at >= day_start)
            )
        ) or 0

        stuck_cutoff = datetime.utcnow() - timedelta(hours=3)
        stuck = (
            await self.db.scalar(
                select(func.count(ContentQueue.id)).where(
                    ContentQueue.status == "in_progress",
                    func.coalesce(ContentQueue.updated_at, ContentQueue.created_at) < stuck_cutoff,
                )
            )
        ) or 0

        # Stranded = generated fine but never published (e.g. WP auth died):
        # queue row 'ready' + draft still 'pending_review' after a day.
        stranded_cutoff = datetime.utcnow() - timedelta(days=1)
        stranded_rows = (
            await self.db.execute(
                select(
                    ContentQueue.id, ContentDraft.id, ContentQueue.brand_id,
                    ContentQueue.title, ContentDraft.created_at,
                )
                .join(ContentDraft, ContentDraft.queue_id == ContentQueue.id)
                .where(
                    ContentQueue.status == "ready",
                    ContentDraft.status == "pending_review",
                    ContentDraft.created_at < stranded_cutoff,
                )
                .order_by(ContentDraft.created_at)
            )
        ).all()
        stranded = [
            {
                "queue_id": q_id,
                "draft_id": d_id,
                "brand_id": brand_id,
                "title": title,
                "age_days": max(0, (datetime.utcnow() - created).days) if created else None,
            }
            for q_id, d_id, brand_id, title, created in stranded_rows
        ]

        metrics = {"drafts_today": drafts_today, "stuck_in_progress": stuck, "stranded": stranded}
        problems = []
        if stuck:
            problems.append(f"{stuck} queue item(s) stuck in_progress >3h")
        if stranded:
            brands = sorted({s['brand_id'] for s in stranded})
            problems.append(
                f"{len(stranded)} draft(s) generated but never published "
                f"({', '.join(brands)}) — waiting in Content Review"
            )
        if problems:
            return _stage("generation", "Content generation (9am)", "fail",
                          "; ".join(problems), metrics)
        return _stage("generation", "Content generation (9am)", "ok",
                      f"{drafts_today} draft(s) generated today", metrics)

    async def _stage_publish(self, day_start: datetime, now_ct: datetime) -> dict:
        rows = (
            await self.db.execute(
                select(ContentPiece.brand_id, func.count(ContentPiece.id))
                .where(
                    ContentPiece.status == "published",
                    ContentPiece.published_at >= day_start,
                )
                .group_by(ContentPiece.brand_id)
            )
        ).all()
        by_brand = dict(rows)
        total = sum(by_brand.values())
        all_brands = [
            b.id for b in (await self.db.execute(select(Brand))).scalars().all() if b.wp_url
        ]
        silent = [b for b in all_brands if not by_brand.get(b)]

        metrics = {"published_today": total, "by_brand": by_brand, "silent_brands": silent}
        note = " (DB view — the 3pm posting monitor verifies the live sites)"
        if now_ct.hour < 10:
            return _stage("publish", "Publishing", "ok",
                          "Publish window not finished yet" + note, metrics)
        if total == 0 and now_ct.hour >= 11:
            return _stage("publish", "Publishing", "fail",
                          "Nothing published today across any brand" + note, metrics)
        if silent:
            return _stage("publish", "Publishing", "warn",
                          f"{total} published, but no posts for: {', '.join(silent)}" + note,
                          metrics)
        return _stage("publish", "Publishing", "ok",
                      f"{total} post(s) published today across all brands" + note, metrics)

    async def _stage_errors(self) -> dict:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        rows = (
            await self.db.execute(
                select(
                    WorkerError.worker_name,
                    func.count(WorkerError.id),
                    func.max(WorkerError.created_at),
                )
                .where(WorkerError.created_at >= cutoff)
                .group_by(WorkerError.worker_name)
                .order_by(func.count(WorkerError.id).desc())
            )
        ).all()
        by_worker = []
        for name, count, latest_at in rows:
            latest_msg = await self.db.scalar(
                select(WorkerError.error_message)
                .where(WorkerError.worker_name == name)
                .order_by(WorkerError.created_at.desc())
                .limit(1)
            )
            by_worker.append(
                {
                    "worker_name": name,
                    "count": count,
                    "latest_message": (latest_msg or "")[:300],
                    "latest_at": latest_at.isoformat() if latest_at else None,
                }
            )
        total = sum(w["count"] for w in by_worker)
        metrics = {"last_24h": total, "by_worker": by_worker}
        if any(w["count"] >= 5 for w in by_worker):
            worst = max(by_worker, key=lambda w: w["count"])
            return _stage("errors", "Worker errors (24h)", "fail",
                          f"{worst['worker_name']} failed {worst['count']}x in 24h", metrics)
        if total:
            return _stage("errors", "Worker errors (24h)", "warn",
                          f"{total} worker error(s) in the last 24h", metrics)
        return _stage("errors", "Worker errors (24h)", "ok", "No worker errors in 24h", metrics)
