"""Research current card terms and stage evidence-backed differences for review.

Research never overwrites the live catalog or stamps an agent answer as verified.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from agent_hub.models.content import MessageInput, TextContent

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

CARD_RESEARCH_AGENT_SLUG = "credit-card-researcher"
RESEARCH_MARKER_KEY = "card_catalog_research_last_run"
# Monthly cadence (user-locked): a research run is due this many days after the last.
RESEARCH_INTERVAL_DAYS = 30

_HOUSEHOLD_CONTEXT = (
    "Maintain the existing household card catalog. Research factual issuer terms, not spending assumptions or application recommendations. "
    "Do not add speculative new products; new offers enter through household intake."
)


class CardResearchService:
    def __init__(self) -> None:
        self._client_cls = AgentHubAPIClient

    def research_due(self) -> bool:
        """True when the monthly cadence says a catalog refresh is due."""
        with get_storage().connection() as conn:
            row = conn.execute(
                "SELECT fact_value FROM household_confirmed_facts WHERE fact_key = %s",
                [RESEARCH_MARKER_KEY],
            ).fetchone()
        if row is None or not row[0]:
            return True
        try:
            last = datetime.fromisoformat(str(row[0]))
        except ValueError:
            return True
        return (datetime.now(UTC) - last).days >= RESEARCH_INTERVAL_DAYS

    def refresh_catalog(self, *, trigger: str) -> dict[str, Any]:
        """Run the research agent and stage its proposed catalog changes."""
        # Lazy: card_management_service pulls the transaction-service stack.
        from app.services.card_management_service import CardManagementService  # noqa: PLC0415

        catalog = CardManagementService().get_catalog()
        catalog_json = json.dumps(
            [
                {
                    "slug": p.slug,
                    "issuer": p.issuer,
                    "product_name": p.product_name,
                    "annual_fee": p.annual_fee,
                    "reward_multipliers": p.reward_multipliers,
                    "point_program": p.point_program,
                    "est_point_value_cents": p.est_point_value_cents,
                    "welcome_bonus_points": p.welcome_bonus_points,
                    "welcome_bonus_cash": p.welcome_bonus_cash,
                    "welcome_min_spend": p.welcome_min_spend,
                    "welcome_window_days": p.welcome_window_days,
                    "credits": [c.model_dump() for c in p.credits],
                    "last_verified_at": p.last_verified_at,
                }
                for p in catalog
            ],
            default=str,
        )
        client = self._client_cls(agent_slug=CARD_RESEARCH_AGENT_SLUG, use_memory=False)
        response = client.complete_messages(
            messages=[
                MessageInput(
                    role="user",
                    content=[
                        TextContent(
                            text=(
                                f"{_HOUSEHOLD_CONTEXT}\n\nCurrent catalog:\n{catalog_json}\n\n"
                                "Verify the catalog against current public sources and respond "
                                "with the JSON schema from your instructions. For each proposed field, include "
                                "evidence[field] = {source_url: official issuer HTTPS page, excerpt: supporting terms, "
                                "effective_from: effective date if stated}. Never estimate terms or invent a fee. "
                                "Updates are proposals pending review, not verified catalog values."
                            )
                        )
                    ],
                )
            ],
            execute_tools=True,
            purpose=f"credit_card_catalog_research:{trigger}",
        )
        payload = _parse_json_response(response.content)
        applied = self._apply(payload)
        self._stamp_marker()
        result = {
            "trigger": trigger,
            "updates_applied": applied["updates"],
            "pending_review": applied["pending"],
            "candidates_added": applied["candidates"],
            "material_changes": [],  # Unapproved research must not send factual fee-change alerts.
            "proposed_changes": payload.get("material_changes") or [],
            "research_notes": payload.get("research_notes") or "",
        }
        logger.info(
            "card_catalog_research_complete",
            trigger=trigger,
            updates=applied["updates"],
            candidates=applied["candidates"],
            material_changes=len(result["material_changes"]),
        )
        return result

    # -- internals ---------------------------------------------------------

    def _apply(self, payload: dict[str, Any]) -> dict[str, int]:
        from app.services.card_terms_review_service import CardTermsReviewService  # noqa: PLC0415

        pending = CardTermsReviewService().stage(payload)
        return {"updates": 0, "candidates": 0, "pending": pending}

    def _stamp_marker(self) -> None:
        with get_storage().connection() as conn:
            conn.execute(
                """
                INSERT INTO household_confirmed_facts (fact_key, fact_value, confirmed_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (fact_key) DO UPDATE
                SET fact_value = EXCLUDED.fact_value, confirmed_at = EXCLUDED.confirmed_at
                """,
                [RESEARCH_MARKER_KEY, datetime.now(UTC).isoformat()],
            )
            conn.commit()


def _slugify(issuer: str, product_name: str) -> str:
    raw = f"{issuer} {product_name}".lower()
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:120] or f"card-{uuid.uuid4().hex[:8]}"


def _parse_json_response(content: str) -> dict[str, Any]:
    """Parse the agent's JSON answer, tolerating code fences / leading prose."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match is None:
            raise ValueError("Research agent returned no JSON object.") from None
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Research agent returned non-object JSON.")
    return parsed


@lru_cache(maxsize=1)
def get_card_research_service() -> CardResearchService:
    return CardResearchService()
