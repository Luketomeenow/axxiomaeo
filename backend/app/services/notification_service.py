import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.approval import Notification, WorkerError

logger = logging.getLogger(__name__)


async def record_worker_error(
    db: AsyncSession,
    worker_name: str,
    error_message: str,
    error_details: dict | None = None,
    notify: bool = True,
) -> None:
    """Persist a WorkerError and surface it (in-app + Slack). Never raises.

    notify=False for call sites that already emit their own notification,
    so a single failure doesn't double-post to Slack.
    """
    try:
        db.add(
            WorkerError(
                worker_name=worker_name,
                error_message=error_message,
                error_details=error_details,
            )
        )
        if notify:
            await NotificationService(db).create(
                type="worker_error",
                title=f"Worker failed: {worker_name}",
                body=(error_message or "")[:500],
            )
    except Exception:
        logger.warning("Failed to record worker error for %s", worker_name, exc_info=True)


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

        # Published posts also go to Discord (with live links) so the team
        # can monitor what went out from the channel.
        if type == "published" and self.settings.discord_webhook_url:
            await self._send_discord(title, body)

        return notification

    async def _send_discord(self, title: str, body: str) -> None:
        # approve_and_publish joins URLs with "; " — one per line keeps
        # Discord's auto-linking clean (a trailing ";" breaks the link).
        content = f"**{title}**\n{body.replace('; ', chr(10))}"[:1900]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self.settings.discord_webhook_url, json={"content": content})
        except Exception as e:
            logger.warning("Discord notification failed: %s", e)

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
