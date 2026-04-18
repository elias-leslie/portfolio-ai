from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient

from .models import StrategyLabDetailResponse, StrategyLabReviewCapability, StrategyLabReviewSuccess

REVIEW_UNAVAILABLE_MESSAGE = "Review is unavailable right now."
STALE_QUOTE_MESSAGE = "Quote is stale"
REVIEW_PURPOSE = "strategy_lab_review"
REVIEW_TIMEOUT_SECONDS = 30
REVIEW_CHECK_TIMEOUT_SECONDS = 2


def get_review_capability(detail: StrategyLabDetailResponse) -> StrategyLabReviewCapability:
    if detail.helper_text == "Quote is stale. Refresh market data before acting.":
        return StrategyLabReviewCapability(available=False, message=STALE_QUOTE_MESSAGE)

    try:
        AgentHubAPIClient(agent_slug="equity-analyst", timeout=REVIEW_CHECK_TIMEOUT_SECONDS)
    except Exception:
        return StrategyLabReviewCapability(available=False, message=REVIEW_UNAVAILABLE_MESSAGE)
    return StrategyLabReviewCapability(available=True, message=None)


def _review_prompt(detail: StrategyLabDetailResponse) -> str:
    payload = {
        "symbol": detail.symbol,
        "action": detail.action,
        "strategy_template": detail.strategy_template,
        "primary_account_target": detail.primary_account_target.model_dump() if detail.primary_account_target else None,
        "why_bullets": detail.why_bullets,
        "watch_item": detail.watch_item,
        "backtest_snapshot": detail.backtest_snapshot.model_dump(),
    }
    return (
        "Review this Strategy Lab call in plain English. Return JSON only with keys: "
        "verdict, summary, tailwinds, headwinds, invalidation_triggers, act_now_or_wait.\n\n"
        f"Summary:\nSymbol {detail.symbol} · action {detail.action} · template {detail.strategy_template}\n\n"
        f"JSON:\n{json.dumps(payload, default=str)}"
    )


def run_review(detail: StrategyLabDetailResponse) -> StrategyLabReviewSuccess:
    client = AgentHubAPIClient(agent_slug="equity-analyst", timeout=REVIEW_TIMEOUT_SECONDS)
    response = client.generate(prompt=_review_prompt(detail), purpose=REVIEW_PURPOSE)
    parsed: dict[str, Any] | None = None
    content = response.content.strip()
    try:
        parsed = json.loads(content)
    except Exception:
        if "{" in content and "}" in content:
            try:
                parsed = json.loads(content[content.index("{"): content.rindex("}") + 1])
            except Exception:
                parsed = None
    if not isinstance(parsed, dict):
        parsed = {
            "verdict": "Needs review",
            "summary": content[:400],
            "tailwinds": [],
            "headwinds": [],
            "invalidation_triggers": [],
            "act_now_or_wait": "Read the summary before acting.",
        }
    return StrategyLabReviewSuccess(
        verdict=str(parsed.get("verdict") or "Needs review"),
        summary=str(parsed.get("summary") or "No review summary returned."),
        tailwinds=[str(v) for v in (parsed.get("tailwinds") or [])],
        headwinds=[str(v) for v in (parsed.get("headwinds") or [])],
        invalidation_triggers=[str(v) for v in (parsed.get("invalidation_triggers") or [])],
        act_now_or_wait=str(parsed.get("act_now_or_wait") or "Wait for more clarity."),
        generated_at=datetime.now(UTC),
    )
