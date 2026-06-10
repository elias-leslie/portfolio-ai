"""Phone push notifications via the agent-hub Telegram endpoint (plan §8).

Bot token/chat config stays in agent-hub ([M:6084f2a8]); portfolio-ai only
POSTs ``{title, body, severity}`` to ``/api/notifications/telegram``. When
agent-hub is unreachable or disabled the NullNotifier keeps every caller safe —
alerts still land in jenny_notifications for the UI, they just don't push.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from app.agents.clients.agent_hub_client import PORTFOLIO_CLIENT_ID, PORTFOLIO_REQUEST_SOURCE
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class Notifier(Protocol):
    def send(self, *, title: str, body: str, severity: str = "info") -> bool: ...


class TelegramNotifier:
    """POSTs to agent-hub's shared Telegram report chat."""

    def __init__(self, base_url: str | None = None, timeout: float = 15.0) -> None:
        self._url = f"{(base_url or settings.agent_hub_url).rstrip('/')}/api/notifications/telegram"
        self._timeout = timeout

    def send(self, *, title: str, body: str, severity: str = "info") -> bool:
        headers = {"X-Request-Source": PORTFOLIO_REQUEST_SOURCE or "portfolio-ai"}
        if PORTFOLIO_CLIENT_ID:
            headers["X-Client-Id"] = PORTFOLIO_CLIENT_ID
        try:
            response = httpx.post(
                self._url,
                json={"title": title, "body": body, "severity": severity, "source": "portfolio-ai"},
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("telegram_notify_failed", error=str(exc), title=title)
            return False
        return True


class NullNotifier:
    def send(self, *, title: str, body: str, severity: str = "info") -> bool:
        logger.info("notifier_noop", title=title, severity=severity)
        return False


def get_notifier() -> Notifier:
    if settings.agent_hub_url:
        return TelegramNotifier()
    return NullNotifier()
