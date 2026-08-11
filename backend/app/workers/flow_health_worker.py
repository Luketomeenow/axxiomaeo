"""Daily flow-health check — the escalation layer above the posting monitor.

Runs mid-morning (10:30 CT), after topic discovery (8am), content generation
(9am), and schema publish (10am) have all had their turn. Diagnoses every
stage via PipelineHealthService and alerts Discord/Slack/in-app when anything
is failing or degraded. Silent when the flow is healthy.
"""

import logging

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.notification_service import NotificationService, record_worker_error
from app.services.pipeline_health_service import PipelineHealthService

logger = logging.getLogger(__name__)


async def run_flow_health():
    settings = get_settings()
    if not settings.flow_health_enabled:
        logger.info("Flow health disabled (FLOW_HEALTH_ENABLED=false)")
        return

    logger.info("Starting flow-health check")
    async with AsyncSessionLocal() as session:
        result = await PipelineHealthService(session).check_flow()

    if result["overall"] == "ok":
        logger.info("Flow health: all stages OK")
        return

    bad = [s for s in result["stages"] if s["status"] != "ok"]
    n_fail = sum(1 for s in bad if s["status"] == "fail")
    n_warn = len(bad) - n_fail
    lines = [
        f"{'❌' if s['status'] == 'fail' else '⚠️'} {s['label']}: {s['detail']}" for s in bad
    ]
    title = f"Pipeline flow {result['overall'].upper()}: {n_fail} failing, {n_warn} warning stage(s)"
    body = "\n".join(lines)
    logger.warning("Flow health: %s\n%s", title, body)

    async with AsyncSessionLocal() as session:
        await NotificationService(session).create(type="flow_alert", title=title, body=body)
        await record_worker_error(
            session,
            "flow_health",
            title,
            error_details={"stages": [{k: s[k] for k in ("key", "status", "detail")} for s in bad]},
            notify=False,  # the flow_alert above already alerts
        )
        await session.commit()
