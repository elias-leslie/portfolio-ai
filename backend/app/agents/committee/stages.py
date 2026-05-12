"""Per-stage helpers that call Agent Hub agents.

Each helper wraps a single Agent Hub completion and returns a typed
output dataclass. The committee runner composes these into the full
graph; this module owns the Agent Hub I/O details only.

The system prompts (and the anti-sycophancy + feedback-round clauses)
live in the Agent Hub DB on the respective slug records. The Python
runner never injects prompt text — it sends ``agent_slug`` plus a
structured user-message payload.
"""

from __future__ import annotations

import json
import time
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger

from .schemas import (
    AnalystOutput,
    DebateRound,
    Evidence,
    IpsResult,
    PastDecisionEntry,
    PmDecision,
    ResearcherOutput,
    RiskObjection,
    RiskVoteOutput,
    TradeProposal,
)

logger = get_logger(__name__)

# Slug constants — single source of truth in this module.
SLUG_FUNDAMENTALS = "fundamentals-v1"
SLUG_NEWS = "news-grounded-v1"
SLUG_SENTIMENT = "sentiment-grounded-v1"
SLUG_TECHNICAL = "technical-v1"
SLUG_BULL = "bull-researcher-v1"
SLUG_BEAR = "bear-researcher-v1"
SLUG_TRADER = "trader-v1"
SLUG_RISK_AGGRESSIVE = "risk-aggressive-v1"
SLUG_RISK_NEUTRAL = "risk-neutral-v1"
SLUG_RISK_CONSERVATIVE = "risk-conservative-v1"
SLUG_PM = "portfolio-mgr-v1"

ANALYST_SLUGS = (SLUG_FUNDAMENTALS, SLUG_NEWS, SLUG_SENTIMENT, SLUG_TECHNICAL)
RISK_SLUGS = (SLUG_RISK_AGGRESSIVE, SLUG_RISK_NEUTRAL, SLUG_RISK_CONSERVATIVE)


async def run_analyst(
    slug: str,
    *,
    symbol: str,
    context: dict[str, Any],
    feedback_round: dict[str, Any] | None = None,
) -> AnalystOutput:
    """Call one analyst agent. Returns a parsed AnalystOutput."""
    payload: dict[str, Any] = {
        "symbol": symbol,
        "context_slice": _context_slice_for(slug, context),
        "feedback_round": bool(feedback_round),
    }
    if feedback_round is not None:
        payload["feedback_input"] = feedback_round
    start = time.monotonic()
    raw = await _complete(slug, payload, purpose=f"committee.analyst.{slug}")
    latency_ms = int((time.monotonic() - start) * 1000)
    parsed = _parse_json_content(raw)
    evidence = _coerce_evidence(parsed.get("evidence"), default_side="neutral")
    score = _coerce_score(parsed.get("score"), low=-1.0, high=1.0)
    return AnalystOutput(
        agent_slug=slug,
        content_md=str(parsed.get("thesis_md") or parsed.get("catalysts_md") or parsed.get("mood_md") or parsed.get("regime_md") or "").strip(),
        score=score,
        evidence=evidence,
        tokens=_tokens(raw),
        latency_ms=latency_ms,
    )


async def run_researcher(
    side: str,
    *,
    symbol: str,
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    feedback_round: dict[str, Any] | None = None,
) -> ResearcherOutput:
    """Call one researcher (bull or bear) for one debate round."""
    if side == "bull":
        slug = SLUG_BULL
    elif side == "bear":
        slug = SLUG_BEAR
    else:
        raise ValueError(f"Unknown researcher side: {side}")
    payload: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "analyst_outputs": [_summarize_analyst(a) for a in analyst_outputs],
        "debate_history": [_summarize_round(r) for r in debate_history],
        "round_idx": len(debate_history),
        "feedback_round": bool(feedback_round),
    }
    if feedback_round is not None:
        payload["feedback_input"] = feedback_round
    start = time.monotonic()
    raw = await _complete(slug, payload, purpose=f"committee.researcher.{side}")
    latency_ms = int((time.monotonic() - start) * 1000)
    parsed = _parse_json_content(raw)
    return ResearcherOutput(
        agent_slug=slug,
        role=side,
        argument_md=str(parsed.get("argument_md") or "").strip(),
        rebuttals_md=str(parsed.get("rebuttals_md") or "").strip(),
        score=_coerce_score(parsed.get("score"), low=0.0, high=1.0),
        evidence=_coerce_evidence(parsed.get("evidence"), default_side=side),
        tokens=_tokens(raw),
        latency_ms=latency_ms,
    )


async def run_trader(
    *,
    symbol: str,
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    portfolio_value: float,
    current_price: float,
    past_decisions: list[PastDecisionEntry],
) -> TradeProposal:
    """Call the trader to synthesize the debate into a trade proposal."""
    payload: dict[str, Any] = {
        "symbol": symbol,
        "analyst_outputs": [_summarize_analyst(a) for a in analyst_outputs],
        "debate_history": [_summarize_round(r) for r in debate_history],
        "portfolio_value": portfolio_value,
        "current_price": current_price,
        "past_decisions": [d.model_dump(mode="json") for d in past_decisions],
        "feedback_round": False,
    }
    start = time.monotonic()
    raw = await _complete(SLUG_TRADER, payload, purpose="committee.trader")
    latency_ms = int((time.monotonic() - start) * 1000)
    parsed = _parse_json_content(raw)
    return TradeProposal(
        action=str(parsed.get("action") or "hold"),
        qty_pct=_coerce_score(parsed.get("qty_pct"), low=0.0, high=1.0),
        entry_price=float(parsed.get("entry_price") or current_price),
        stop_price=_optional_float(parsed.get("stop_price")),
        horizon=str(parsed.get("horizon") or "swing"),
        rationale_md=str(parsed.get("rationale_md") or "").strip(),
        signers=[str(s) for s in parsed.get("signers") or []],
        tokens=_tokens(raw),
        latency_ms=latency_ms,
    )


async def run_risk(
    slug: str,
    *,
    proposal: TradeProposal,
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    ips_result: IpsResult,
    feedback_round: dict[str, Any] | None = None,
) -> RiskVoteOutput:
    """Call one risk voter."""
    payload: dict[str, Any] = {
        "proposal": proposal.model_dump(mode="json"),
        "analyst_outputs": [_summarize_analyst(a) for a in analyst_outputs],
        "debate_history": [_summarize_round(r) for r in debate_history],
        "ips_result": ips_result.model_dump(mode="json"),
        "feedback_round": bool(feedback_round),
    }
    if feedback_round is not None:
        payload["feedback_input"] = feedback_round
    start = time.monotonic()
    raw = await _complete(slug, payload, purpose=f"committee.risk.{slug}")
    latency_ms = int((time.monotonic() - start) * 1000)
    parsed = _parse_json_content(raw)
    return RiskVoteOutput(
        agent_slug=slug,
        vote=str(parsed.get("vote") or "downgrade"),
        score=_coerce_score(parsed.get("score"), low=-1.0, high=1.0),
        narrative_md=str(parsed.get("narrative_md") or "").strip(),
        objections=[
            RiskObjection(
                claim=str(item.get("claim", "")),
                severity=str(item.get("severity", "low")),
            )
            for item in parsed.get("objections") or []
            if isinstance(item, dict)
        ],
        tokens=_tokens(raw),
        latency_ms=latency_ms,
    )


async def run_pm(
    *,
    proposal: TradeProposal,
    debate_history: list[DebateRound],
    risk_votes: list[RiskVoteOutput],
    ips_result: IpsResult,
    past_decisions: list[PastDecisionEntry],
    feedback_round: dict[str, Any] | None = None,
) -> PmDecision:
    """Call the portfolio manager for the final decision."""
    payload: dict[str, Any] = {
        "proposal": proposal.model_dump(mode="json"),
        "debate_history": [_summarize_round(r) for r in debate_history],
        "risk_votes": [v.model_dump(mode="json") for v in risk_votes],
        "ips_result": ips_result.model_dump(mode="json"),
        "past_decisions": [d.model_dump(mode="json") for d in past_decisions],
        "feedback_round": bool(feedback_round),
    }
    if feedback_round is not None:
        payload["feedback_input"] = feedback_round
    start = time.monotonic()
    raw = await _complete(SLUG_PM, payload, purpose="committee.pm")
    latency_ms = int((time.monotonic() - start) * 1000)
    parsed = _parse_json_content(raw)
    qty_pct = _coerce_score(parsed.get("qty_pct"), low=0.0, high=1.0)
    return PmDecision(
        action=str(parsed.get("action") or "hold"),
        qty_pct=qty_pct,
        qty=0.0,  # filled in at approve time from portfolio_value + price
        confidence=_coerce_score(parsed.get("confidence"), low=0.0, high=1.0),
        horizon=str(parsed.get("horizon") or proposal.horizon),
        signers=[str(s) for s in parsed.get("signers") or []],
        rationale_md=str(parsed.get("rationale_md") or "").strip(),
        rebuttal_md=str(parsed.get("rebuttal_md") or "").strip() or None,
        tokens=_tokens(raw),
        latency_ms=latency_ms,
    )


# ---------- helpers ----------


async def _complete(slug: str, payload: dict[str, Any], *, purpose: str) -> Any:
    """Async Agent Hub completion. Each call gets its own client.

    A short-lived client per call keeps the lifecycle obvious; the
    underlying ``httpx`` pool inside the SDK handles connection reuse.
    """
    client = AgentHubAPIClient(agent_slug=slug, use_memory=False)
    try:
        return await client.complete_messages_async(
            agent_slug=slug,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(payload, default=str),
                }
            ],
            temperature=0.2,
            purpose=purpose,
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()


def _parse_json_content(raw: Any) -> dict[str, Any]:
    """Extract the JSON object from an Agent Hub LLMResponse-shaped result."""
    content = str(getattr(raw, "content", "") or "")
    if not content:
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Attempt to salvage a JSON object substring.
        from app.services._jenny_response_cleanup import extract_json_object_text

        salvaged = extract_json_object_text(content)
        if salvaged is None:
            logger.warning("committee_stage_unparseable_json", preview=content[:200])
            return {}
        try:
            parsed = json.loads(salvaged)
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _coerce_score(value: Any, *, low: float, high: float) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(low, min(high, score))


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_evidence(raw: Any, *, default_side: str) -> list[Evidence]:
    if not isinstance(raw, list):
        return []
    out: list[Evidence] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        side = str(item.get("side") or default_side)
        if side not in {"bull", "bear", "neutral"}:
            side = "neutral"
        out.append(
            Evidence(
                claim=str(item.get("claim", "")),
                source=item.get("source"),
                side=side,
                weight=float(item.get("weight", 1.0)) if item.get("weight") is not None else 1.0,
            )
        )
    return out


def _tokens(raw: Any) -> int:
    usage = getattr(raw, "usage", None)
    if usage is None:
        return 0
    return int(getattr(usage, "total_tokens", 0) or 0)


def _summarize_analyst(a: AnalystOutput) -> dict[str, Any]:
    return {
        "agent_slug": a.agent_slug,
        "score": a.score,
        "content_md": a.content_md,
        "evidence": [e.model_dump(mode="json") for e in a.evidence],
    }


def _summarize_round(r: DebateRound) -> dict[str, Any]:
    return {
        "round_idx": r.round_idx,
        "bull": {
            "score": r.bull.score,
            "argument_md": r.bull.argument_md,
            "rebuttals_md": r.bull.rebuttals_md,
        },
        "bear": {
            "score": r.bear.score,
            "argument_md": r.bear.argument_md,
            "rebuttals_md": r.bear.rebuttals_md,
        },
    }


def _context_slice_for(slug: str, context: dict[str, Any]) -> dict[str, Any]:
    """Hand each analyst only the slice of context they need.

    Keeps payloads tight (token-aware) and signals which fields drive
    the analyst's read.
    """
    if slug == SLUG_FUNDAMENTALS:
        return {k: context.get(k) for k in ("fundamentals", "valuation")}
    if slug == SLUG_NEWS:
        return {"news": context.get("news")}
    if slug == SLUG_SENTIMENT:
        return {"sentiment": context.get("sentiment"), "options": context.get("options")}
    if slug == SLUG_TECHNICAL:
        return {"ohlcv": context.get("ohlcv"), "indicators": context.get("indicators")}
    return context
