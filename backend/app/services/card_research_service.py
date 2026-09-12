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
RESEARCH_ATTEMPT_KEY = "card_catalog_research_last_attempt"
# Monthly cadence (user-locked): a research run is due this many days after the last.
RESEARCH_INTERVAL_DAYS = 30

_HOUSEHOLD_CONTEXT = (
    "Maintain the existing household card catalog. Research factual issuer terms, not spending assumptions or application recommendations. "
    "Also look for up to three source-backed personal travel-card offers missing from the catalog. "
    "Use new_candidates[{product: catalog fields including slug, evidence: per-field issuer sources}]. "
    "New products are proposals for review; do not infer an offer from an article or invent eligibility."
)


class CardResearchService:
    def __init__(self) -> None:
        self._client_cls = AgentHubAPIClient

    def research_due(self) -> bool:
        """Opt-in, approaching-decision research with a cooldown on failed runs."""
        with get_storage().connection() as conn:
            facts = dict(conn.execute(
                "SELECT fact_key,fact_value FROM household_confirmed_facts WHERE fact_key = ANY(%s)",
                [["card_strategy_settings", RESEARCH_MARKER_KEY, RESEARCH_ATTEMPT_KEY]],
            ).fetchall())
            try:
                enabled = json.loads(str(facts.get("card_strategy_settings", "{}"))).get("automatic_research") is True
            except (ValueError, AttributeError):
                enabled = False
            if not enabled:
                return False
            approaching = conn.execute("""SELECT 1 FROM card_strategy_plans p
                LEFT JOIN household_credit_cards c ON c.id=p.actual_card_id
                WHERE p.status='approved' AND p.snapshot->'candidate' != 'null'::jsonb AND
                ((p.actual_card_id IS NULL AND (p.snapshot->'candidate'->>'application_on')::date <= CURRENT_DATE+30)
                 OR c.welcome_deadline <= CURRENT_DATE+30) LIMIT 1""").fetchone()
        if not approaching:
            return False
        stamps = [str(facts[k]) for k in (RESEARCH_MARKER_KEY, RESEARCH_ATTEMPT_KEY) if facts.get(k)]
        if not stamps:
            return True
        try:
            last = max(datetime.fromisoformat(stamp).replace(tzinfo=UTC) for stamp in stamps)
        except (ValueError, TypeError):
            return False
        return (datetime.now(UTC) - last).days >= RESEARCH_INTERVAL_DAYS

    def refresh_catalog(self, *, trigger: str) -> dict[str, Any]:
        """Run the research agent and stage its proposed catalog changes."""
        # Lazy: card_management_service pulls the transaction-service stack.
        from app.services.card_management_service import CardManagementService  # noqa: PLC0415

        self._claim_attempt(trigger)

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

    def _claim_attempt(self, trigger: str) -> None:
        # Serialize the check and persisted attempt before any model call. Manual
        # retries also have a short cooldown; refresh clicks cannot fan out calls.
        with get_storage().connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(781947012)")
            if trigger != "on_demand" and not self.research_due():
                raise ValueError("Automatic research is disabled or not due.")
            row = conn.execute("SELECT fact_value FROM household_confirmed_facts WHERE fact_key=%s", [RESEARCH_ATTEMPT_KEY]).fetchone()
            if row:
                try:
                    previous = datetime.fromisoformat(str(row[0])).replace(tzinfo=UTC)
                except ValueError:
                    raise ValueError("The last research attempt needs review before retrying.") from None
                if (datetime.now(UTC)-previous).total_seconds() < 3600:
                    raise ValueError("Research was already attempted recently. Reuse its results or retry after one hour.")
            conn.execute("""INSERT INTO household_confirmed_facts (fact_key,fact_value,confirmed_at)
                VALUES (%s,%s,now()) ON CONFLICT (fact_key) DO UPDATE
                SET fact_value=excluded.fact_value,confirmed_at=now()""", [RESEARCH_ATTEMPT_KEY, datetime.now(UTC).isoformat()])
            conn.commit()

    # -- internals ---------------------------------------------------------

    def _apply(self, payload: dict[str, Any]) -> dict[str, int]:
        from app.services.card_terms_review_service import CardTermsReviewService  # noqa: PLC0415

        pending = CardTermsReviewService().stage(payload)
        return {"updates": 0, "candidates": 0, "pending": pending}

    def _stamp_marker(self, key: str = RESEARCH_MARKER_KEY) -> None:
        with get_storage().connection() as conn:
            conn.execute(
                """
                INSERT INTO household_confirmed_facts (fact_key, fact_value, confirmed_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (fact_key) DO UPDATE
                SET fact_value = EXCLUDED.fact_value, confirmed_at = EXCLUDED.confirmed_at
                """,
                [key, datetime.now(UTC).isoformat()],
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
