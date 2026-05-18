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

import asyncio
import json
import os
import time
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger

from .schemas import (
    AnalystOutput,
    DebateRound,
    Evidence,
    FeedbackAgentResponse,
    IpsResult,
    PastDecisionEntry,
    PmDecision,
    ResearcherOutput,
    RiskObjection,
    RiskVoteOutput,
    Side,
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
RISK_SLUGS = (SLUG_RISK_AGGRESSIVE, SLUG_RISK_CONSERVATIVE, SLUG_RISK_NEUTRAL)
_AGENT_COMPLETION_TIMEOUT_SECONDS = 20 * 60

# Per-process cap on simultaneous LLM calls. The 25-symbol fan-out otherwise
# stampedes the same upstream model and trips provider rate limits before the
# orchestrator's per-provider cooldown can engage. Sized to ~the agent-hub DB
# pool floor so we never starve the DB pool either.
_DEFAULT_LLM_CONCURRENCY = 6
_llm_semaphore_cell: dict[str, asyncio.Semaphore | None] = {"sem": None}


def _get_llm_semaphore() -> asyncio.Semaphore:
    """Return the process-wide LLM concurrency semaphore (lazy-init)."""
    sem = _llm_semaphore_cell["sem"]
    if sem is None:
        raw = os.environ.get("COMMITTEE_LLM_CONCURRENCY")
        try:
            size = max(1, int(raw)) if raw else _DEFAULT_LLM_CONCURRENCY
        except ValueError:
            size = _DEFAULT_LLM_CONCURRENCY
        sem = asyncio.Semaphore(size)
        _llm_semaphore_cell["sem"] = sem
    return sem


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
    risk_history: list[RiskVoteOutput] | None = None,
    feedback_round: dict[str, Any] | None = None,
) -> RiskVoteOutput:
    """Call one risk voter."""
    payload: dict[str, Any] = {
        "proposal": proposal.model_dump(mode="json"),
        "analyst_outputs": [_summarize_analyst(a) for a in analyst_outputs],
        "debate_history": [_summarize_round(r) for r in debate_history],
        "ips_result": ips_result.model_dump(mode="json"),
        "risk_history": [_summarize_risk_vote(v) for v in risk_history or []],
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


async def run_analyst_feedback(
    slug: str,
    *,
    symbol: str,
    context: dict[str, Any],
    prior_output: AnalystOutput,
    debate_summary: list[dict[str, Any]],
    new_claim: str,
) -> FeedbackAgentResponse:
    """Re-invoke an analyst with a user claim and parse the feedback-shape response.

    The system prompt for each analyst slug includes the feedback-round
    clause (DB-resident, see plan §Anti-sycophancy). When ``feedback_round``
    is set in the payload the model returns ``{score, revised_stance,
    rebuttal_or_concession}`` instead of the regular thesis shape.
    """
    payload: dict[str, Any] = {
        "symbol": symbol,
        "context_slice": _context_slice_for(slug, context),
        "feedback_round": True,
        "feedback_input": {
            "prior_output": _summarize_analyst(prior_output),
            "debate_summary": debate_summary,
            "new_claim": new_claim,
        },
    }
    raw = await _complete(slug, payload, purpose=f"committee.analyst.{slug}.feedback")
    parsed = _parse_json_content(raw)
    return _parse_feedback_response(parsed, slug=slug, prior_score=prior_output.score)


async def run_risk_feedback(
    slug: str,
    *,
    proposal: TradeProposal,
    ips_result: IpsResult,
    prior_vote: RiskVoteOutput,
    debate_summary: list[dict[str, Any]],
    new_claim: str,
) -> RiskVoteOutput:
    """Re-invoke a risk voter with the feedback claim, return the new full vote.

    The runner needs the new ``score`` to compute the consensus-shift
    risk-median delta, so we keep the full ``RiskVoteOutput`` shape.
    """
    payload: dict[str, Any] = {
        "proposal": proposal.model_dump(mode="json"),
        "ips_result": ips_result.model_dump(mode="json"),
        "feedback_round": True,
        "feedback_input": {
            "prior_vote": prior_vote.model_dump(mode="json"),
            "debate_summary": debate_summary,
            "new_claim": new_claim,
        },
    }
    start = time.monotonic()
    raw = await _complete(slug, payload, purpose=f"committee.risk.{slug}.feedback")
    latency_ms = int((time.monotonic() - start) * 1000)
    parsed = _parse_json_content(raw)
    return RiskVoteOutput(
        agent_slug=slug,
        vote=str(parsed.get("vote") or prior_vote.vote),
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
        try:
            async with asyncio.timeout(_AGENT_COMPLETION_TIMEOUT_SECONDS):
                async with _get_llm_semaphore():
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
        except TimeoutError as exc:
            raise TimeoutError(
                f"{purpose} timed out after {_AGENT_COMPLETION_TIMEOUT_SECONDS}s"
            ) from exc
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


def _stance_from_score(score: float) -> Side:
    """Map a numeric analyst score to bull/bear/neutral. Threshold: ±0.2."""
    if score >= 0.2:
        return "bull"
    if score <= -0.2:
        return "bear"
    return "neutral"


def _parse_feedback_response(
    parsed: dict[str, Any],
    *,
    slug: str,
    prior_score: float,
) -> FeedbackAgentResponse:
    """Coerce a feedback-round LLM response into FeedbackAgentResponse.

    Falls back to ``weak`` + unchanged stance on missing/invalid fields
    so a single misbehaving agent can't crash the consensus rule.
    """
    raw_score = str(parsed.get("score") or "weak").strip().lower()
    if raw_score not in {"weak", "mistaken", "partial", "decisive"}:
        raw_score = "weak"
    raw_stance = str(parsed.get("revised_stance") or "").strip().lower()
    prior_stance = _stance_from_score(prior_score)
    if raw_stance not in {"bull", "bear", "neutral"}:
        raw_stance = prior_stance
    return FeedbackAgentResponse(
        agent_slug=slug,
        score=raw_score,
        revised_stance=raw_stance,
        rebuttal_or_concession=str(parsed.get("rebuttal_or_concession") or "").strip(),
        prior_stance=prior_stance,
    )


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


def _summarize_risk_vote(v: RiskVoteOutput) -> dict[str, Any]:
    return {
        "agent_slug": v.agent_slug,
        "vote": v.vote,
        "score": v.score,
        "narrative_md": v.narrative_md,
        "objections": [o.model_dump(mode="json") for o in v.objections],
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
