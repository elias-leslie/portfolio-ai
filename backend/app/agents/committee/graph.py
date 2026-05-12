"""Investment Committee orchestrator.

Composes the five-stage pipeline (analysts → researchers → trader →
IPS → risk → PM) into a single ``run_committee`` coroutine. Honors
pause/resume/abort between stages, emits SSE events into the
per-run queue, and persists every event to the database.

Lifetime model:
- Entry: API endpoint validates auth + creates a row via
  ``store.create_run``, registers the stream entry, and schedules
  ``run_committee`` as a background task.
- Cancellation: ``stream.abort(run_id)`` flips the control state. The
  runner picks this up at the next ``check_control`` call and emits
  ``run.aborted``.
- Errors: any exception inside the runner is logged, persisted via
  ``store.mark_failed``, emitted as ``run.failed``.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from importlib import import_module
from typing import Any

from app.logging_config import get_logger

from . import GRAPH_VERSION, stages, store, stream
from . import feedback as feedback_mod
from . import ips as ips_mod
from .schemas import (
    AnalystOutput,
    DebateRound,
    FeedbackAgentResponse,
    IpsCheck,
    IpsResult,
    PastDecisionEntry,
    PmDecision,
    ResearcherOutput,
    RiskVoteOutput,
    TradeProposal,
)

logger = get_logger(__name__)


_DEBATE_ROUNDS = 3
# After pm.decision the runner stays alive briefly so user feedback
# submitted within this window is processed by the consensus-shift
# round. Reset every time a claim lands so the user can submit a
# follow-up. Capped to keep idle runs from holding background slots.
_FEEDBACK_WAIT_SECONDS = 30.0
_FEEDBACK_POLL_INTERVAL = 0.5
_KPI_TICK_INTERVAL = 1.0


async def _kpi_ticker(
    *,
    run_id: str,
    counters: dict[str, float],
    started_at: float,
    emit,
) -> None:
    """Emit ``kpi.tick`` events ~every ``_KPI_TICK_INTERVAL`` seconds.

    Reads the runner's mutable ``counters`` dict so token/cost numbers
    reflect the latest stage completion. Cancelled by the runner's
    ``try/finally`` once a terminal event is emitted.
    """
    try:
        while True:
            await asyncio.sleep(_KPI_TICK_INTERVAL)
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            await emit(
                "kpi.tick",
                stage_name="system",
                content={
                    "tokens_total": int(counters["tokens"]),
                    "cost_usd": float(counters["cost_usd"]),
                    "elapsed_ms": elapsed_ms,
                },
            )
    except asyncio.CancelledError:
        # Expected — the runner cancels the ticker right before the terminal event.
        raise


async def run_committee(
    *,
    run_id: str,
    symbol: str,
    household_id: str | None,
    parent_run_id: str | None = None,
) -> None:
    """Drive a single committee run from start to terminal event."""
    started_at = time.monotonic()
    counters: dict[str, float] = {"tokens": 0.0, "cost_usd": 0.0}
    ticker_task: asyncio.Task[None] | None = None

    async def emit(
        type: str,
        *,
        stage_name: str | None = None,
        agent_slug: str | None = None,
        role: str | None = None,
        content: dict[str, Any] | None = None,
        score: float | None = None,
        tokens: int | None = None,
        latency_ms: int | None = None,
    ) -> int:
        event_id, seq = store.persist_event(
            run_id,
            type=type,
            stage=stage_name,
            agent_slug=agent_slug,
            role=role,
            content=content or {},
            score=score,
            tokens=tokens,
            latency_ms=latency_ms,
        )
        await stream.emit(
            run_id,
            {
                "seq": seq,
                "ts": datetime.now(tz=UTC).isoformat(),
                "run_id": run_id,
                "type": type,
                "stage": stage_name,
                "agent_slug": agent_slug,
                "role": role,
                "content": content or {},
                "score": score,
                "tokens": tokens,
                "latency_ms": latency_ms,
            },
        )
        return event_id

    try:
        store.mark_running(run_id)
        await emit(
            "run.start",
            stage_name="system",
            content={"symbol": symbol, "parent_run_id": parent_run_id, "graph_version": GRAPH_VERSION},
        )
        ticker_task = asyncio.create_task(
            _kpi_ticker(run_id=run_id, counters=counters, started_at=started_at, emit=emit)
        )

        await _ensure_ohlcv(symbol)

        await stream.check_control(run_id)
        context = await _build_context(symbol)
        past_decisions = store.load_past_decisions(symbol, household_id, limit=5)

        # Stage 1: Analysts (concurrent — independent data slices).
        await emit("stage.enter", stage_name="analysts", content={"stage": "analysts"})
        await stream.check_control(run_id)
        analyst_outputs = await _run_analyst_stage(symbol, context, emit)
        counters["tokens"] += sum(a.tokens for a in analyst_outputs)

        # Stage 2: 3-round bull/bear debate.
        await emit("stage.enter", stage_name="researchers", content={"stage": "researchers"})
        debate_history: list[DebateRound] = []
        for round_idx in range(_DEBATE_ROUNDS):
            await stream.check_control(run_id)
            await emit(
                "debate.round.start",
                stage_name="researchers",
                content={"round": round_idx},
            )
            bull, bear = await _run_debate_round(symbol, analyst_outputs, debate_history, emit)
            counters["tokens"] += bull.tokens + bear.tokens
            debate_history.append(DebateRound(round_idx=round_idx, bull=bull, bear=bear))
            await emit(
                "debate.round.end",
                stage_name="researchers",
                content={
                    "round": round_idx,
                    "bull_score": bull.score,
                    "bear_score": bear.score,
                },
            )

        # Stage 3: Trader proposal.
        await emit("stage.enter", stage_name="trader", content={"stage": "trader"})
        await stream.check_control(run_id)
        portfolio_value = _portfolio_value_estimate(household_id)
        current_price = float(context.get("current_price") or 0.0)
        proposal = await stages.run_trader(
            symbol=symbol,
            analyst_outputs=analyst_outputs,
            debate_history=debate_history,
            portfolio_value=portfolio_value,
            current_price=current_price,
            past_decisions=past_decisions,
        )
        counters["tokens"] += proposal.tokens
        await emit(
            "trader.proposal",
            stage_name="trader",
            agent_slug=stages.SLUG_TRADER,
            role="trader",
            content=proposal.model_dump(mode="json"),
            tokens=proposal.tokens,
            latency_ms=proposal.latency_ms,
        )

        # Stage 4: IPS checks (deterministic, no LLM).
        await emit("stage.enter", stage_name="ips", content={"stage": "ips"})
        await stream.check_control(run_id)
        ips_result = await asyncio.to_thread(
            ips_mod.ips_evaluate, proposal, symbol=symbol, household_id=household_id
        )
        for check in ips_result.checks:
            await emit(
                "ips.check",
                stage_name="ips",
                content=check.model_dump(mode="json"),
            )

        # Stage 5: Risk vote (3 voters concurrent).
        await emit("stage.enter", stage_name="risk", content={"stage": "risk"})
        await stream.check_control(run_id)
        risk_votes = await _run_risk_stage(proposal, analyst_outputs, debate_history, ips_result, emit)
        counters["tokens"] += sum(v.tokens for v in risk_votes)

        # Stage 6: PM final decision.
        await emit("stage.enter", stage_name="pm", content={"stage": "pm"})
        await stream.check_control(run_id)
        decision = await stages.run_pm(
            proposal=proposal,
            debate_history=debate_history,
            risk_votes=risk_votes,
            ips_result=ips_result,
            past_decisions=past_decisions,
        )
        counters["tokens"] += decision.tokens
        decision = _enforce_ips_compliance(decision, ips_result)
        await emit(
            "pm.decision",
            stage_name="pm",
            agent_slug=stages.SLUG_PM,
            role="pm",
            content=decision.model_dump(mode="json"),
            score=decision.confidence,
            tokens=decision.tokens,
            latency_ms=decision.latency_ms,
        )

        store.mark_complete(
            run_id,
            decision=decision,
            tokens_total=int(counters["tokens"]),
            cost_usd=counters["cost_usd"],
        )

        # Post-decision feedback loop: drain queued claims, run the
        # consensus-shift round, persist any revised decision. Re-arm the
        # wait window every time a claim lands so a follow-up gets a
        # chance.
        decision = await _drain_feedback_loop(
            run_id=run_id,
            symbol=symbol,
            household_id=household_id,
            context=context,
            analyst_outputs=analyst_outputs,
            debate_history=debate_history,
            ips_result=ips_result,
            proposal=proposal,
            risk_votes=risk_votes,
            past_decisions=past_decisions,
            decision=decision,
            counters=counters,
            emit=emit,
        )

        await _cancel_ticker(ticker_task)
        ticker_task = None
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        await emit(
            "run.complete",
            stage_name="system",
            content={
                "decision": decision.model_dump(mode="json"),
                "tokens_total": int(counters["tokens"]),
                "cost_usd": counters["cost_usd"],
                "elapsed_ms": elapsed_ms,
            },
        )

    except asyncio.CancelledError:
        await _cancel_ticker(ticker_task)
        ticker_task = None
        store.mark_aborted(run_id, reason="user_abort")
        await emit("run.aborted", stage_name="system", content={"reason": "user"})
    except Exception as exc:
        await _cancel_ticker(ticker_task)
        ticker_task = None
        logger.exception("committee_run_failed", run_id=run_id)
        store.mark_failed(run_id, error=str(exc))
        await emit("run.failed", stage_name="system", content={"error": str(exc)})
    finally:
        await _cancel_ticker(ticker_task)


async def _run_analyst_stage(
    symbol: str,
    context: dict[str, Any],
    emit,
) -> list[AnalystOutput]:
    """Fan-out the four analysts concurrently and emit their outputs."""
    tasks = [
        stages.run_analyst(slug, symbol=symbol, context=context)
        for slug in stages.ANALYST_SLUGS
    ]
    outputs = await asyncio.gather(*tasks, return_exceptions=True)
    parsed: list[AnalystOutput] = []
    for slug, result in zip(stages.ANALYST_SLUGS, outputs, strict=True):
        if isinstance(result, BaseException):
            await emit(
                "agent.error",
                stage_name="analysts",
                agent_slug=slug,
                content={"error": str(result)},
            )
            continue
        parsed.append(result)
        await emit(
            "agent.output",
            stage_name="analysts",
            agent_slug=slug,
            role="analyst",
            content={
                "content_md": result.content_md,
                "evidence": [e.model_dump(mode="json") for e in result.evidence],
            },
            score=result.score,
            tokens=result.tokens,
            latency_ms=result.latency_ms,
        )
    return parsed


async def _run_debate_round(
    symbol: str,
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    emit,
) -> tuple[ResearcherOutput, ResearcherOutput]:
    """Run one bull/bear pair concurrently."""
    bull_task = stages.run_researcher(
        "bull",
        symbol=symbol,
        analyst_outputs=analyst_outputs,
        debate_history=debate_history,
    )
    bear_task = stages.run_researcher(
        "bear",
        symbol=symbol,
        analyst_outputs=analyst_outputs,
        debate_history=debate_history,
    )
    bull, bear = await asyncio.gather(bull_task, bear_task)
    for side, output in (("bull", bull), ("bear", bear)):
        await emit(
            "agent.output",
            stage_name="researchers",
            agent_slug=output.agent_slug,
            role=side,
            content={
                "argument_md": output.argument_md,
                "rebuttals_md": output.rebuttals_md,
                "evidence": [e.model_dump(mode="json") for e in output.evidence],
            },
            score=output.score,
            tokens=output.tokens,
            latency_ms=output.latency_ms,
        )
    return bull, bear


async def _run_risk_stage(
    proposal: TradeProposal,
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    ips_result: IpsResult,
    emit,
) -> list[RiskVoteOutput]:
    tasks = [
        stages.run_risk(
            slug,
            proposal=proposal,
            analyst_outputs=analyst_outputs,
            debate_history=debate_history,
            ips_result=ips_result,
        )
        for slug in stages.RISK_SLUGS
    ]
    votes = await asyncio.gather(*tasks)
    for vote in votes:
        await emit(
            "risk.vote",
            stage_name="risk",
            agent_slug=vote.agent_slug,
            role="risk",
            content={
                "vote": vote.vote,
                "narrative_md": vote.narrative_md,
                "objections": [o.model_dump(mode="json") for o in vote.objections],
            },
            score=vote.score,
            tokens=vote.tokens,
            latency_ms=vote.latency_ms,
        )
    return votes


async def _ensure_ohlcv(symbol: str) -> None:
    """Pre-flight backfill via ``refresh_daily_ohlcv`` if the symbol is missing data."""
    try:
        mod = import_module("app.tasks.ingestion.price_ingestion")
        # refresh_daily_ohlcv is sync; offload to a thread.
        await asyncio.to_thread(mod.refresh_daily_ohlcv, [symbol.upper()])
    except Exception as exc:
        # Backfill failure is not fatal — analysts will see whatever data exists.
        logger.warning("committee_ohlcv_backfill_failed", symbol=symbol, error=str(exc))


async def _build_context(symbol: str) -> dict[str, Any]:
    """Build the per-stage context dict from ``build_symbol_intelligence``."""
    try:
        svc = import_module("app.api.symbols.service")
        intelligence = await asyncio.to_thread(svc.build_symbol_intelligence, symbol)
        payload = intelligence.model_dump(mode="json") if hasattr(intelligence, "model_dump") else dict(intelligence)
    except Exception as exc:
        logger.warning("committee_context_build_failed", symbol=symbol, error=str(exc))
        return {"current_price": None}
    return {
        "current_price": _extract_price(payload),
        "fundamentals": payload.get("fundamentals"),
        "valuation": payload.get("valuation"),
        "news": payload.get("news"),
        "sentiment": payload.get("sentiment"),
        "options": payload.get("options"),
        "ohlcv": payload.get("ohlcv") or payload.get("technicals"),
        "indicators": payload.get("indicators") or payload.get("technicals"),
    }


def _extract_price(payload: dict[str, Any]) -> float | None:
    """Best-effort current-price extraction from the intelligence payload."""
    for path in (("price",), ("market", "price"), ("quote", "price"), ("technicals", "last_close")):
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict) and "value" in value:
            try:
                return float(value["value"])
            except (TypeError, ValueError):
                continue
    return None


def _portfolio_value_estimate(household_id: str | None) -> float:
    """Sum of (shares * cost_basis) across the household's positions as a rough portfolio value.

    Used by the trader for qty_pct→qty conversion at approve time. We
    intentionally use cost_basis (not current price) so the trader's
    sizing is stable across intraday quote moves. Approve-time
    conversion uses the *current* close.
    """
    _ = household_id  # single-household scoping handled by storage today
    from app.storage.connection import get_connection_manager

    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(shares * COALESCE(cost_basis, 0)), 0)
            FROM portfolio_positions
            """,
        ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _enforce_ips_compliance(decision: PmDecision, ips_result: IpsResult) -> PmDecision:
    """If any IPS check is severity=block and not passed, force hold or downsize.

    The PM prompt instructs the model to do this itself; this is the
    Python belt-and-suspenders check. It also re-renders the rationale
    when we modify the decision so the audit trail is honest.
    """
    if ips_result.all_passed:
        return decision
    blocking = [c for c in ips_result.checks if c.severity == "block" and not c.passed]
    if not blocking:
        return decision
    if decision.action == "hold":
        return decision
    # Downgrade: keep the action but enforce qty_pct ≤ the smallest threshold.
    smallest_threshold = min(
        (c.threshold for c in blocking if c.threshold is not None),
        default=None,
    )
    if smallest_threshold is not None and decision.qty_pct > smallest_threshold:
        downgraded_pct = smallest_threshold
        forced_hold = downgraded_pct <= 0
        return decision.model_copy(
            update={
                "action": "hold" if forced_hold else decision.action,
                "qty_pct": 0.0 if forced_hold else downgraded_pct,
                "rationale_md": (
                    decision.rationale_md
                    + "\n\n_IPS-enforced compliance: size reduced to honor blocking check(s): "
                    + ", ".join(c.name for c in blocking)
                    + "._"
                ),
            }
        )
    return decision.model_copy(
        update={
            "action": "hold",
            "qty_pct": 0.0,
            "rationale_md": (
                decision.rationale_md
                + "\n\n_IPS-enforced compliance: forced to hold by blocking check(s): "
                + ", ".join(c.name for c in blocking)
                + "._"
            ),
        }
    )


async def _drain_feedback_loop(
    *,
    run_id: str,
    symbol: str,
    household_id: str | None,
    context: dict[str, Any],
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    ips_result: IpsResult,
    proposal: TradeProposal,
    risk_votes: list[RiskVoteOutput],
    past_decisions: list[PastDecisionEntry],
    decision: PmDecision,
    counters: dict[str, float],
    emit,
) -> PmDecision:
    """Wait for + process user feedback claims for ~``_FEEDBACK_WAIT_SECONDS``.

    Each claim triggers a consensus-shift round: re-invoke analysts +
    risk voters with the new claim, run ``should_revise_decision``,
    either re-invoke PM (decision shifted) or emit a rebuttal-only
    ``run.feedback.resolved``. Re-arms the wait window on every claim
    so the user can follow up.

    Returns the (possibly updated) decision; mutates ``counters`` for
    token accounting so the kpi.tick ticker stays accurate.
    """
    deadline = time.monotonic() + _FEEDBACK_WAIT_SECONDS
    debate_summary = [stages._summarize_round(r) for r in debate_history]
    while time.monotonic() < deadline:
        try:
            await stream.check_control(run_id)
        except asyncio.CancelledError:
            raise
        claims = stream.drain_feedback(run_id)
        if not claims:
            await asyncio.sleep(_FEEDBACK_POLL_INTERVAL)
            continue
        for claim in claims:
            decision = await _process_feedback_claim(
                run_id=run_id,
                symbol=symbol,
                household_id=household_id,
                context=context,
                analyst_outputs=analyst_outputs,
                debate_summary=debate_summary,
                ips_result=ips_result,
                proposal=proposal,
                risk_votes_prior=risk_votes,
                past_decisions=past_decisions,
                decision=decision,
                counters=counters,
                claim=claim,
                emit=emit,
            )
        deadline = time.monotonic() + _FEEDBACK_WAIT_SECONDS
    return decision


async def _process_feedback_claim(
    *,
    run_id: str,
    symbol: str,
    household_id: str | None,
    context: dict[str, Any],
    analyst_outputs: list[AnalystOutput],
    debate_summary: list[dict[str, Any]],
    ips_result: IpsResult,
    proposal: TradeProposal,
    risk_votes_prior: list[RiskVoteOutput],
    past_decisions: list[PastDecisionEntry],
    decision: PmDecision,
    counters: dict[str, float],
    claim: dict[str, Any],
    emit,
) -> PmDecision:
    """Run one feedback round: analysts + risk voters + (maybe) PM."""
    new_claim = str(claim.get("user_input") or "").strip()
    round_num = int(claim.get("round") or 0)
    input_id = claim.get("input_id")
    if not new_claim:
        return decision

    analyst_responses = await _run_analyst_feedback_stage(
        symbol=symbol,
        context=context,
        analyst_outputs=analyst_outputs,
        debate_summary=debate_summary,
        new_claim=new_claim,
    )
    new_risk_votes = await _run_risk_feedback_stage(
        proposal=proposal,
        ips_result=ips_result,
        prior_votes=risk_votes_prior,
        debate_summary=debate_summary,
        new_claim=new_claim,
    )
    counters["tokens"] += sum(v.tokens for v in new_risk_votes)

    should_revise, telemetry = feedback_mod.should_revise_decision(
        analyst_responses=analyst_responses,
        prior_risk_votes=risk_votes_prior,
        new_risk_votes=new_risk_votes,
    )

    if should_revise:
        revised = await stages.run_pm(
            proposal=proposal,
            debate_history=[],  # debate is summarized inside the feedback payload
            risk_votes=new_risk_votes,
            ips_result=ips_result,
            past_decisions=past_decisions,
            feedback_round={"new_claim": new_claim, "prior_decision": decision.model_dump(mode="json")},
        )
        counters["tokens"] += revised.tokens
        revised = _enforce_ips_compliance(revised, ips_result)
        store.mark_complete(
            run_id,
            decision=revised,
            tokens_total=int(counters["tokens"]),
            cost_usd=counters["cost_usd"],
        )
        await emit(
            "pm.decision",
            stage_name="pm",
            agent_slug=stages.SLUG_PM,
            role="pm",
            content=revised.model_dump(mode="json"),
            score=revised.confidence,
            tokens=revised.tokens,
            latency_ms=revised.latency_ms,
        )
        decision = revised
        rebuttal_md: str | None = None
    else:
        rebuttal_md = feedback_mod.compose_rebuttal_md(analyst_responses) or None

    if input_id:
        try:
            store.mark_feedback_resolved(str(input_id), decision_shifted=should_revise)
        except Exception as exc:
            logger.warning(
                "committee_feedback_resolved_persist_failed",
                run_id=run_id,
                input_id=input_id,
                error=str(exc),
            )

    await emit(
        "run.feedback.resolved",
        stage_name="feedback",
        content={
            "round": round_num,
            "decision_shifted": should_revise,
            "rebuttal_md": rebuttal_md,
            "telemetry": telemetry,
        },
    )
    _ = household_id  # household scoping handled by store layer today
    return decision


async def _run_analyst_feedback_stage(
    *,
    symbol: str,
    context: dict[str, Any],
    analyst_outputs: list[AnalystOutput],
    debate_summary: list[dict[str, Any]],
    new_claim: str,
) -> list[FeedbackAgentResponse]:
    tasks = [
        stages.run_analyst_feedback(
            output.agent_slug,
            symbol=symbol,
            context=context,
            prior_output=output,
            debate_summary=debate_summary,
            new_claim=new_claim,
        )
        for output in analyst_outputs
    ]
    return list(await asyncio.gather(*tasks))


async def _run_risk_feedback_stage(
    *,
    proposal: TradeProposal,
    ips_result: IpsResult,
    prior_votes: list[RiskVoteOutput],
    debate_summary: list[dict[str, Any]],
    new_claim: str,
) -> list[RiskVoteOutput]:
    tasks = [
        stages.run_risk_feedback(
            vote.agent_slug,
            proposal=proposal,
            ips_result=ips_result,
            prior_vote=vote,
            debate_summary=debate_summary,
            new_claim=new_claim,
        )
        for vote in prior_votes
    ]
    return list(await asyncio.gather(*tasks))


async def _cancel_ticker(task: asyncio.Task[None] | None) -> None:
    """Cancel and await a ticker task; idempotent if already cancelled or None."""
    import contextlib

    if task is None or task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


# IpsCheck used only for type hints; re-export to keep imports tidy.
__all__ = [
    "GRAPH_VERSION",
    "IpsCheck",
    "run_committee",
]
