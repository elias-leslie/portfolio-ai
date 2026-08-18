"""Use the dedicated household document review agent from Agent Hub."""

from __future__ import annotations

from agent_hub import AgentHubClient as SDKClient

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

HOUSEHOLD_REVIEW_AGENT_SLUG = "financial-document-reviewer"

# Receipt photos are routed to their own agent so they can run on a local
# vision model: the images stay on the box, and the receipt path keeps working
# when hosted providers are out of quota. Only the receipt-image retry uses it —
# statement review stays on the general reviewer, which is a stronger model.
HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG = "household-receipt-vision"


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
        self._ready_slugs: set[str] = set()

    def ensure_agent(self, slug: str = HOUSEHOLD_REVIEW_AGENT_SLUG) -> None:
        """Verify the named review agent exists and is active."""
        if not AGENT_HUB_ENABLED or slug in self._ready_slugs:
            return

        client = self._sdk._get_client()
        headers = self._sdk._inject_tracking_headers("sdk.ensure_household_review_agent")
        response = client.get(f"/api/agents/{slug}", headers=headers)

        if response.status_code == 404:
            raise RuntimeError(f"Required Agent Hub agent '{slug}' is missing.")

        response.raise_for_status()
        current = response.json()
        if not bool(current.get("is_active", True)):
            raise RuntimeError(f"Required Agent Hub agent '{slug}' is inactive.")

        self._ready_slugs.add(slug)

    def resolve_review_agent_slug(self, *, include_image: bool) -> str:
        """Pick the review agent, degrading to the general reviewer.

        A missing or deactivated receipt agent must not take the receipt path
        down with it, so this falls back rather than raising: losing the local
        vision model costs privacy and quota, but still reviews the receipt.
        """
        self.ensure_agent()
        if not include_image:
            return HOUSEHOLD_REVIEW_AGENT_SLUG
        try:
            self.ensure_agent(HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG)
        except Exception:
            logger.warning(
                "receipt_vision_agent_unavailable_falling_back",
                extra={"fallback_slug": HOUSEHOLD_REVIEW_AGENT_SLUG},
                exc_info=True,
            )
            return HOUSEHOLD_REVIEW_AGENT_SLUG
        return HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG
