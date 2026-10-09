"""Runtime prompt lookup from Agent Hub DB."""

from __future__ import annotations

from functools import lru_cache

from agent_hub import AgentHubClient as SDKClient
from agent_hub.exceptions import AgentHubError

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED
from app.config import settings

_sdk = SDKClient(
    base_url=settings.agent_hub_url,
    client_name="portfolio-ai",
    client_id=settings.portfolio_client_id or None,
    request_source=settings.portfolio_request_source,
)


@lru_cache(maxsize=64)
def require_agent_hub_prompt(slug: str) -> str:
    """Return prompt content from Agent Hub or raise when missing."""
    if not AGENT_HUB_ENABLED:
        raise RuntimeError("Agent Hub is disabled; prompt lookup unavailable.")

    try:
        payload = _sdk.get_prompt(slug)
    except AgentHubError as exc:
        if exc.status_code == 404:
            raise RuntimeError(f"Required Agent Hub prompt '{slug}' is missing.") from exc
        raise
    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"Required Agent Hub prompt '{slug}' has no content.")
    return content


def render_agent_hub_prompt(slug: str, /, **values: object) -> str:
    """Fetch prompt content from Agent Hub and format with runtime values."""
    try:
        return require_agent_hub_prompt(slug).format(**values)
    except KeyError as exc:
        missing = str(exc).strip("'")
        raise RuntimeError(
            f"Required Agent Hub prompt '{slug}' is missing format value '{missing}'."
        ) from exc
