"""Card-catalog freshness via the Agent Hub research agent (plan §0a item 3).

Card terms drift fast (CSR fee $550→$795 and the Hyatt 4:3 cut both landed
within months), so the ``credit-card-researcher`` Agent Hub agent re-verifies
the catalog against issuer pages and reputable points sites — monthly via the
daily household maintenance task (gated by a run marker), or on demand via
``POST /api/household/cards/research/refresh``.

The agent runs an agentic web-research tool loop server-side and returns
structured updates; only whitelisted fields are applied, ``last_verified_at``
is stamped, new candidate cards land with ``source='research'``, and material
changes (fee hikes, devaluations, elevated bonuses) are returned for the alert
path to deliver ([G:2d62382d]: only act-worthy findings interrupt).
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

# Fields the agent may change on an existing row. Anything else is ignored.
_UPDATABLE_FIELDS = frozenset(
    {
        "product_name", "network", "annual_fee", "reward_multipliers", "point_program",
        "est_point_value_cents", "welcome_bonus_points", "welcome_bonus_cash",
        "welcome_min_spend", "welcome_window_days", "transfer_partners", "credits",
        "issuer_rules",
    }
)
_JSONB_FIELDS = frozenset({"reward_multipliers", "transfer_partners", "credits", "issuer_rules"})

_HOUSEHOLD_CONTEXT = (
    "Household context: ~$6,000-7,000/month total card spend, travel-leaning, hands-off "
    "(easy-credit valuation), two-player rotation (~2 opens/player/year), keeps Amazon "
    "Prime Visa permanently."
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
        """Run the research agent and apply its verified catalog changes."""
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
                                "with the JSON schema from your instructions."
                            )
                        )
                    ],
                )
            ],
            execute_tools=True,
            max_turns=24,
            purpose=f"credit_card_catalog_research:{trigger}",
        )
        payload = _parse_json_response(response.content)
        applied = self._apply(payload)
        self._stamp_marker()
        result = {
            "trigger": trigger,
            "updates_applied": applied["updates"],
            "candidates_added": applied["candidates"],
            "material_changes": payload.get("material_changes") or [],
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
        updates = payload.get("updates") or []
        candidates = payload.get("new_candidates") or []
        applied_updates = 0
        added_candidates = 0
        with get_storage().connection() as conn:
            for update in updates:
                slug = update.get("slug")
                fields = update.get("fields") or {}
                clean = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
                if not slug or not clean:
                    continue
                sets = ", ".join(
                    f"{col} = %s::jsonb" if col in _JSONB_FIELDS else f"{col} = %s" for col in clean
                )
                params = [
                    json.dumps(v) if k in _JSONB_FIELDS else v for k, v in clean.items()
                ]
                conn.execute(
                    f"UPDATE credit_card_products SET {sets}, "
                    "last_verified_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP "
                    "WHERE slug = %s",
                    [*params, slug],
                )
                applied_updates += 1
            for candidate in candidates:
                if not candidate.get("product_name") or not candidate.get("issuer"):
                    continue
                slug = candidate.get("slug") or _slugify(
                    str(candidate["issuer"]), str(candidate["product_name"])
                )
                welcome = candidate.get("welcome") if isinstance(candidate.get("welcome"), dict) else {}
                conn.execute(
                    """
                    INSERT INTO credit_card_products (
                        id, slug, issuer, network, product_name, card_kind, annual_fee,
                        reward_multipliers, point_program, est_point_value_cents,
                        welcome_bonus_points, welcome_bonus_cash, welcome_min_spend,
                        welcome_window_days, transfer_partners, credits, issuer_rules,
                        source, last_verified_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'personal', %s, %s::jsonb, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, 'research', CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (slug) DO NOTHING
                    """,
                    [
                        str(uuid.uuid4()),
                        slug,
                        str(candidate["issuer"]),
                        candidate.get("network"),
                        str(candidate["product_name"]),
                        float(candidate.get("annual_fee") or 0.0),
                        json.dumps(candidate.get("reward_multipliers") or {"other": 1.0}),
                        candidate.get("point_program"),
                        float(candidate.get("est_point_value_cents") or 1.0),
                        int(welcome.get("bonus_points") or candidate.get("welcome_bonus_points") or 0),
                        float(welcome.get("bonus_cash") or candidate.get("welcome_bonus_cash") or 0.0),
                        float(welcome.get("min_spend") or candidate.get("welcome_min_spend") or 0.0),
                        int(welcome.get("window_days") or candidate.get("welcome_window_days") or 0),
                        json.dumps(candidate.get("transfer_partners") or []),
                        json.dumps(candidate.get("credits") or []),
                        json.dumps(candidate.get("issuer_rules") or {}),
                    ],
                )
                added_candidates += 1
            conn.commit()
        return {"updates": applied_updates, "candidates": added_candidates}

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
