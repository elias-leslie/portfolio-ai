"""Provision and use the dedicated household document review agent."""

from __future__ import annotations

from typing import Any

from agent_hub import AgentHubClient as SDKClient

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED
from app.config import settings
from app.constants.models import CLAUDE_OPUS, CLAUDE_SONNET, GEMINI_PRO
from app.logging_config import get_logger

logger = get_logger(__name__)

HOUSEHOLD_REVIEW_AGENT_SLUG = "financial-document-reviewer"
HOUSEHOLD_REVIEW_MEMORY_TAGS = [
    "finance-relevant",
    "household-finance",
    "financial-doc-review",
]
HOUSEHOLD_REVIEW_AGENT_SPEC: dict[str, Any] = {
    "slug": HOUSEHOLD_REVIEW_AGENT_SLUG,
    "name": "Financial Document Reviewer",
    "description": (
        "Specialized reviewer for household financial documents including statements, "
        "receipts, invoices, tax files, brokerage reports, and order confirmations."
    ),
    "system_prompt": """You are Jenny's dedicated financial document review agent.

Your job is to review uploaded household finance documents and classify them accurately for a personal investor household.

Document types you should handle well:
- bank and credit-card statements
- brokerage and retirement statements
- receipts and order confirmations
- bills and invoices
- tax documents
- screenshots of transactions, checkout pages, balances, or account activity

Core behaviors:
- Prefer precise classification over generic "other".
- Use extracted text, visual evidence, merchant names, institutions, statement cues, and filename patterns together.
- Identify likely merchant, institution, account, statement period, and document role when evidence is strong.
- Infer planning implications conservatively.
- Ask the fewest questions possible, but ask targeted questions when confidence is low.
- Use plain language suitable for a household CFO assistant, not an accounting textbook.
- If the caller requests JSON, return strict JSON only.

Risk controls:
- Never invent transactions, balances, tax facts, or retirement assumptions.
- Never claim certainty when the document is ambiguous or partially unreadable.
- Treat confirmed household facts as more important than generic priors.
- Prefer project-specific household patterns over broad consumer generalizations when memory provides them.
""",
    "primary_model_id": CLAUDE_SONNET,
    "fallback_models": [
        CLAUDE_OPUS,
        GEMINI_PRO,
        "codex/gpt-5.4",
    ],
    "temperature": 0.1,
    "thinking_level": "low",
    "verbosity_level": "low",
    "is_active": True,
    "is_coding_agent": False,
    "memory_config": {
        "injection_enabled": True,
        "budget_enforcement": True,
        "token_budget": 900,
        "include_mandates": False,
        "include_guardrails": False,
        "reference_index": False,
        "continuity_enabled": False,
        "include_tags": HOUSEHOLD_REVIEW_MEMORY_TAGS,
        "exclude_tags": [],
    },
}


class HouseholdReviewAgentService:
    """Manage the dedicated Agent Hub reviewer and its household memory."""

    def __init__(self) -> None:
        self._sdk = SDKClient(
            base_url=settings.agent_hub_url,
            client_name="portfolio-ai",
            client_id=settings.portfolio_client_id or None,
            request_source=settings.portfolio_request_source,
        )
        self._agent_ready = False

    def ensure_agent(self) -> None:
        """Provision or update the financial document reviewer agent."""
        if not AGENT_HUB_ENABLED or self._agent_ready:
            return

        client = self._sdk._get_client()
        headers = self._sdk._inject_tracking_headers("sdk.ensure_household_review_agent")
        response = client.get(f"/api/agents/{HOUSEHOLD_REVIEW_AGENT_SLUG}", headers=headers)

        if response.status_code == 404:
            create_response = client.post("/api/agents", json=HOUSEHOLD_REVIEW_AGENT_SPEC, headers=headers)
            create_response.raise_for_status()
            self._agent_ready = True
            logger.info("household_review_agent_created", slug=HOUSEHOLD_REVIEW_AGENT_SLUG)
            return

        response.raise_for_status()
        current = response.json()
        if self._agent_needs_update(current):
            update_payload = {
                key: value
                for key, value in HOUSEHOLD_REVIEW_AGENT_SPEC.items()
                if key != "slug"
            }
            update_payload["change_reason"] = "Sync household financial document reviewer config"
            update_response = client.put(
                f"/api/agents/{HOUSEHOLD_REVIEW_AGENT_SLUG}",
                json=update_payload,
                headers=headers,
            )
            update_response.raise_for_status()
            logger.info("household_review_agent_updated", slug=HOUSEHOLD_REVIEW_AGENT_SLUG)

        self._agent_ready = True

    def _agent_needs_update(self, current: dict[str, Any]) -> bool:
        comparable_fields = [
            "name",
            "description",
            "system_prompt",
            "primary_model_id",
            "fallback_models",
            "temperature",
            "thinking_level",
            "verbosity_level",
            "is_active",
            "is_coding_agent",
            "memory_config",
        ]
        return any(current.get(field) != HOUSEHOLD_REVIEW_AGENT_SPEC.get(field) for field in comparable_fields)
