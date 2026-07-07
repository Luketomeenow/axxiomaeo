"""Daily topic discovery — feeds demand-driven topics into the content queue.

Runs daily 08:00 (America/Chicago), one hour before the daily content worker,
so freshly discovered topics flow straight into that run's draft generation.
"""

import logging
from collections import Counter

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.notification_service import NotificationService, record_worker_error
from app.services.topic_discovery_service import TopicDiscoveryService

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "citation_gap": "citation gaps",
    "search_demand": "search demand",
    "coverage": "coverage fill",
}


async def run_topic_discovery():
    settings = get_settings()
    if not settings.topic_discovery_enabled:
        logger.info("Topic discovery disabled (TOPIC_DISCOVERY_ENABLED=false)")
        return

    logger.info("Starting topic discovery")
    async with AsyncSessionLocal() as session:
        try:
            result = await TopicDiscoveryService(session).discover()
            queued = result["queued"]
            if queued:
                counts = Counter(item["source"] for item in queued)
                breakdown = ", ".join(
                    f"{n} from {SOURCE_LABELS.get(source, source)}" for source, n in counts.most_common()
                )
                await NotificationService(session).create(
                    type="topics_queued",
                    title=f"{len(queued)} new content topics queued",
                    body=f"{breakdown}. Drafts generate at 9am today, then await your review.",
                    entity_type="content_queue",
                )
            else:
                logger.info("Topic discovery: no new topics (existing coverage is complete)")
            await session.commit()
            logger.info("Topic discovery complete: %s topic(s) queued", len(queued))
        except Exception as e:
            logger.exception("Topic discovery failed: %s", e)
            await record_worker_error(session, "topic_discovery", str(e))
            await session.commit()
