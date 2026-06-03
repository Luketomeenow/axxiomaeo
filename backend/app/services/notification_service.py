import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.approval import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create(
        self,
        type: str,
        title: str,
        body: str = "",
        entity_type: str | None = None,
        entity_id: int | None = None,
        send_slack: bool = True,
    ) -> Notification:
        notification = Notification(
            type=type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        self.db.add(notification)
        await self.db.flush()

        if send_slack and self.settings.slack_webhook_url:
            await self._send_slack(title, body, entity_type, entity_id)

        return notification

    async def _send_slack(
        self,
        title: str,
        body: str,
        entity_type: str | None,
        entity_id: int | None,
    ) -> None:
        link = self.settings.frontend_url
        if entity_type == "content_draft" and entity_id:
            link = f"{self.settings.frontend_url}/content/review/{entity_id}"
        elif entity_type == "schema_deployment" and entity_id:
            link = f"{self.settings.frontend_url}/schema/review"

        payload = {
            "text": f"*{title}*\n{body}\n<{link}|Review in Dashboard>",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self.settings.slack_webhook_url, json=payload)
        except Exception as e:
            logger.warning("Slack notification failed: %s", e)
