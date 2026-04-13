"""Use the dedicated household document review agent from Agent Hub."""

from __future__ import annotations

from agent_hub import AgentHubClient as SDKClient

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

HOUSEHOLD_REVIEW_AGENT_SLUG = "financial-document-reviewer"


class HouseholdReviewAgentService:
    """Verify the dedicated Agent Hub reviewer exists and is active.

    Agent configuration lives in Agent Hub. Portfolio-AI should route by slug,
    not own local model/prompt/fallback config for the reviewer.
    """

    def __init__(self) -> None:
        self._sdk = SDKClient(
            base_url=settings.agent_hub_url,
            client_name="portfolio-ai",
            client_id=settings.portfolio_client_id or None,
            request_source=settings.portfolio_request_source,
        )
        self._agent_ready = False

    def ensure_agent(self) -> None:
        """Verify the financial document reviewer agent exists and is active."""
        if not AGENT_HUB_ENABLED or self._agent_ready:
            return

        client = self._sdk._get_client()
        headers = self._sdk._inject_tracking_headers("sdk.ensure_household_review_agent")
        response = client.get(f"/api/agents/{HOUSEHOLD_REVIEW_AGENT_SLUG}", headers=headers)

        if response.status_code == 404:
            raise RuntimeError(
                f"Required Agent Hub agent '{HOUSEHOLD_REVIEW_AGENT_SLUG}' is missing."
            )

        response.raise_for_status()
        current = response.json()
        if not bool(current.get("is_active", True)):
            raise RuntimeError(
                f"Required Agent Hub agent '{HOUSEHOLD_REVIEW_AGENT_SLUG}' is inactive."
            )

        self._agent_ready = True
