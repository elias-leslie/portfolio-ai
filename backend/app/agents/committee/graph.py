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
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import import_module
from typing import Any

from app.logging_config import get_logger

from . import GRAPH_VERSION, payloads, readiness, stages, store, stream
from . import feedback as feedback_mod
from . import ips as ips_mod
from .schemas import (
    AnalystOutput,
    DebateRound,
    Evidence,
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


# One round captures the value (Liang et al., Degeneration of Thought,
# arxiv 2305.19118). Rounds 2-3 amplify persuasion-over-truth and the
# echo-chamber effect dominates the marginal information gain.
_DEBATE_ROUNDS = 1
# After pm.decision the runner stays alive briefly so user feedback
# submitted within this window is processed by the consensus-shift
# round. Reset every time a claim lands so the user can submit a
# follow-up. Capped to keep idle runs from holding background slots.
_FEEDBACK_WAIT_SECONDS = 30.0
_FEEDBACK_POLL_INTERVAL = 0.5
_KPI_TICK_INTERVAL = 1.0
_TERMINAL_EVENT_TYPES = {"run.complete", "run.aborted", "run.failed"}
_IPS_CHECK_ORDER = ("concentration", "tax_bill", "sector_exposure", "wash_sale")


class CommitteeRunRecoveryError(RuntimeError):
    """Raised when persisted events cannot be rebuilt into a runnable checkpoint."""


@dataclass
class _PartialDebateRound:
    round_idx: int
    started: bool = False
    ended: bool = False
    bull: ResearcherOutput | None = None
    bear: ResearcherOutput | None = None


@dataclass
class _RunCheckpoint:
    started: bool = False
    terminal_event_type: str | None = None
    stage_enters: set[str] = field(default_factory=set)
    analyst_outputs: dict[str, AnalystOutput] = field(default_factory=dict)
    debate_rounds: dict[int, _PartialDebateRound] = field(default_factory=dict)
    proposal: TradeProposal | None = None
    ips_checks: dict[str, IpsCheck] = field(default_factory=dict)
    risk_votes: dict[str, RiskVoteOutput] = field(default_factory=dict)
    decision: PmDecision | None = None


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
    try:
        prior_events = store.load_events(run_id)
        checkpoint = _rebuild_checkpoint(prior_events)
        run_summary = store.get_run_summary(run_id)
    except Exception as exc:
        logger.exception("committee_run_recovery_failed", run_id=run_id)
        failed_seq = _mark_recovery_failed(run_id, error=str(exc))
        await stream.emit(
            run_id,
            {
                "seq": failed_seq,
                "ts": datetime.now(tz=UTC).isoformat(),
                "run_id": run_id,
                "type": "run.failed",
                "stage": "system",
                "agent_slug": None,
                "role": None,
                "content": {"error": str(exc)},
                "score": None,
                "tokens": None,
                "latency_ms": None,
            },
        )
        return
    if checkpoint.terminal_event_type is not None:
        logger.info(
            "committee_run_already_terminal",
            run_id=run_id,
            terminal_event_type=checkpoint.terminal_event_type,
        )
        return

    started_at = _monotonic_anchor_for_run(run_summary)
    counters: dict[str, float] = {"tokens": 0.0, "cost_usd": 0.0}
    counters["tokens"] = float(_sum_event_tokens(prior_events))
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
        if checkpoint.started:
            await emit(
                "run.resume",
                stage_name="system",
                content={
                    "symbol": symbol,
                    "parent_run_id": parent_run_id,
                    "graph_version": GRAPH_VERSION,
                    "resume_from": _next_stage_name(checkpoint),
                },
            )
        else:
            await emit(
                "run.start",
                stage_name="system",
                content={"symbol": symbol, "parent_run_id": parent_run_id, "graph_version": GRAPH_VERSION},
            )
        ticker_task = asyncio.create_task(
            _kpi_ticker(run_id=run_id, counters=counters, started_at=started_at, emit=emit)
        )

        await _ensure_ohlcv(symbol)

        # Belt-and-suspenders: re-check readiness after the OHLCV backfill.
        # The API/fan-out caller may have already run the gate, but data can
        # go stale between scheduling and execution, and the API path can be
        # bypassed (resumes, retros). Failing here costs zero LLM calls.
        ready_report = await asyncio.to_thread(
            readiness.check_committee_readiness, symbol
        )
        if not ready_report.ok:
            logger.warning(
                "committee_run_data_unready",
                run_id=run_id,
                symbol=symbol,
                blocking=[i.check for i in ready_report.blocking_issues],
            )
            error_payload = {
                "error": "data_unready",
                "report": ready_report.to_dict(),
            }
            store.mark_failed(run_id, error=json.dumps(error_payload, default=str))
            await _cancel_ticker(ticker_task)
            ticker_task = None
            await emit(
                "run.failed",
                stage_name="system",
                content=error_payload,
            )
            return

        await stream.check_control(run_id)
        context = await _build_context(symbol)
        # Portfolio context flows into trader / risk / PM only — keeping
        # the analyst slices position-blind avoids anchoring their reads
        # on what we already own.
        portfolio_context = await asyncio.to_thread(
            payloads.fetch_portfolio_context, symbol, household_id
        )
        past_decisions = store.load_past_decisions(symbol, household_id, limit=5)

        # Stage 1: Analysts (concurrent — independent data slices).
        await _emit_stage_enter_once(checkpoint, "analysts", emit)
        await stream.check_control(run_id)
        analyst_outputs = await _run_analyst_stage(
            symbol,
            context,
            emit,
            existing=checkpoint.analyst_outputs,
        )
        counters["tokens"] += sum(
            a.tokens for a in analyst_outputs if a.agent_slug not in checkpoint.analyst_outputs
        )

        # Stage 2: 3-round bull/bear debate.
        await _emit_stage_enter_once(checkpoint, "researchers", emit)
        debate_history: list[DebateRound] = []
        for round_idx in range(_DEBATE_ROUNDS):
            partial_round = checkpoint.debate_rounds.get(round_idx)
            await stream.check_control(run_id)
            if partial_round is None or not partial_round.started:
                await emit(
                    "debate.round.start",
                    stage_name="researchers",
                    content={"round": round_idx},
                )
            bull, bear = await _run_debate_round(
                symbol,
                analyst_outputs,
                debate_history,
                emit,
                existing_bull=partial_round.bull if partial_round else None,
                existing_bear=partial_round.bear if partial_round else None,
            )
            if partial_round is None or partial_round.bull is None:
                counters["tokens"] += bull.tokens
            if partial_round is None or partial_round.bear is None:
                counters["tokens"] += bear.tokens
            debate_history.append(DebateRound(round_idx=round_idx, bull=bull, bear=bear))
            if partial_round is None or not partial_round.ended:
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
        await _emit_stage_enter_once(checkpoint, "trader", emit)
        await stream.check_control(run_id)
        portfolio_value = _portfolio_value_estimate(household_id)
        current_price = float(context.get("current_price") or 0.0)
        proposal = checkpoint.proposal
        if proposal is None:
            proposal = await stages.run_trader(
                symbol=symbol,
                analyst_outputs=analyst_outputs,
                debate_history=debate_history,
                portfolio_value=portfolio_value,
                current_price=current_price,
                past_decisions=past_decisions,
                portfolio_context=portfolio_context,
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
        await _emit_stage_enter_once(checkpoint, "ips", emit)
        await stream.check_control(run_id)
        ips_result = await _run_ips_stage(
            proposal,
            symbol=symbol,
            household_id=household_id,
            emit=emit,
            existing=checkpoint.ips_checks,
        )

        # Stage 5: Risk vote (ordered so later voters can rebut prior risk stances).
        await _emit_stage_enter_once(checkpoint, "risk", emit)
        await stream.check_control(run_id)
        risk_votes = await _run_risk_stage(
            proposal,
            analyst_outputs,
            debate_history,
            ips_result,
            emit,
            existing=checkpoint.risk_votes,
            portfolio_context=portfolio_context,
        )
        counters["tokens"] += sum(
            v.tokens for v in risk_votes if v.agent_slug not in checkpoint.risk_votes
        )

        # Stage 6: PM final decision.
        await _emit_stage_enter_once(checkpoint, "pm", emit)
        await stream.check_control(run_id)
        decision = checkpoint.decision
        if decision is None:
            decision = await stages.run_pm(
                proposal=proposal,
                debate_history=debate_history,
                risk_votes=risk_votes,
                ips_result=ips_result,
                past_decisions=past_decisions,
                portfolio_context=portfolio_context,
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
        if checkpoint.started:
            for claim in store.load_unresolved_feedback_inputs(run_id):
                stream.enqueue_feedback(run_id, claim)

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
    *,
    existing: dict[str, AnalystOutput] | None = None,
) -> list[AnalystOutput]:
    """Fan-out the four analysts concurrently and emit their outputs."""
    existing = existing or {}
    tasks = [
        stages.run_analyst(slug, symbol=symbol, context=context)
        for slug in stages.ANALYST_SLUGS
        if slug not in existing
    ]
    missing_slugs = [slug for slug in stages.ANALYST_SLUGS if slug not in existing]
    outputs = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
    parsed: list[AnalystOutput] = [
        existing[slug] for slug in stages.ANALYST_SLUGS if slug in existing
    ]
    for slug, result in zip(missing_slugs, outputs, strict=True):
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
    *,
    existing_bull: ResearcherOutput | None = None,
    existing_bear: ResearcherOutput | None = None,
) -> tuple[ResearcherOutput, ResearcherOutput]:
    """Run one bull/bear pair concurrently."""
    tasks: dict[str, Any] = {}
    if existing_bull is None:
        tasks["bull"] = stages.run_researcher(
            "bull",
            symbol=symbol,
            analyst_outputs=analyst_outputs,
            debate_history=debate_history,
        )
    if existing_bear is None:
        tasks["bear"] = stages.run_researcher(
            "bear",
            symbol=symbol,
            analyst_outputs=analyst_outputs,
            debate_history=debate_history,
        )
    results = await asyncio.gather(*tasks.values()) if tasks else []
    generated = dict(zip(tasks.keys(), results, strict=True))
    bull = existing_bull or generated.get("bull")
    bear = existing_bear or generated.get("bear")
    if bull is None or bear is None:
        raise CommitteeRunRecoveryError("debate round cannot resume without bull and bear outputs")
    for side, output in (("bull", bull), ("bear", bear)):
        if (side == "bull" and existing_bull is not None) or (
            side == "bear" and existing_bear is not None
        ):
            continue
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


async def _run_ips_stage(
    proposal: TradeProposal,
    *,
    symbol: str,
    household_id: str | None,
    emit,
    existing: dict[str, IpsCheck] | None = None,
) -> IpsResult:
    existing = existing or {}
    if all(name in existing for name in _IPS_CHECK_ORDER):
        checks = [existing[name] for name in _IPS_CHECK_ORDER]
        return IpsResult(checks=checks, all_passed=all(check.passed for check in checks))

    ips_result = await asyncio.to_thread(
        ips_mod.ips_evaluate, proposal, symbol=symbol, household_id=household_id
    )
    merged = dict(existing)
    for check in ips_result.checks:
        if check.name in merged:
            continue
        merged[check.name] = check
        await emit(
            "ips.check",
            stage_name="ips",
            content=check.model_dump(mode="json"),
        )
    missing = [name for name in _IPS_CHECK_ORDER if name not in merged]
    if missing:
        raise CommitteeRunRecoveryError(f"IPS resume missing checks: {', '.join(missing)}")
    checks = [merged[name] for name in _IPS_CHECK_ORDER]
    return IpsResult(checks=checks, all_passed=all(check.passed for check in checks))


async def _run_risk_stage(
    proposal: TradeProposal,
    analyst_outputs: list[AnalystOutput],
    debate_history: list[DebateRound],
    ips_result: IpsResult,
    emit,
    *,
    existing: dict[str, RiskVoteOutput] | None = None,
    portfolio_context: dict[str, Any] | None = None,
) -> list[RiskVoteOutput]:
    existing = existing or {}
    votes: list[RiskVoteOutput] = []
    for slug in stages.RISK_SLUGS:
        if slug in existing:
            votes.append(existing[slug])
            continue
        vote = await stages.run_risk(
            slug,
            proposal=proposal,
            analyst_outputs=analyst_outputs,
            debate_history=debate_history,
            ips_result=ips_result,
            risk_history=votes,
            portfolio_context=portfolio_context,
        )
        votes.append(vote)
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


def _rebuild_checkpoint(events: list[dict[str, Any]]) -> _RunCheckpoint:
    """Fold persisted events into typed outputs the runner can resume from."""
    checkpoint = _RunCheckpoint()
    current_round: int | None = None

    for event in events:
        event_type = str(event.get("type") or "")
        stage = event.get("stage")
        content = event.get("content") if isinstance(event.get("content"), dict) else {}

        if event_type == "run.start":
            checkpoint.started = True
        elif event_type in _TERMINAL_EVENT_TYPES:
            checkpoint.terminal_event_type = event_type
        elif event_type == "stage.enter" and isinstance(stage, str):
            checkpoint.stage_enters.add(stage)
        elif event_type == "agent.output" and stage == "analysts":
            output = _analyst_from_event(event)
            checkpoint.analyst_outputs[output.agent_slug] = output
        elif event_type == "debate.round.start":
            round_idx = int(content.get("round") or 0)
            checkpoint.debate_rounds.setdefault(
                round_idx, _PartialDebateRound(round_idx=round_idx)
            ).started = True
            current_round = round_idx
        elif event_type == "agent.output" and stage == "researchers":
            round_idx = current_round
            if round_idx is None:
                round_idx = max(checkpoint.debate_rounds.keys(), default=0)
            partial = checkpoint.debate_rounds.setdefault(
                round_idx, _PartialDebateRound(round_idx=round_idx, started=True)
            )
            output = _researcher_from_event(event)
            if output.role == "bull":
                partial.bull = output
            else:
                partial.bear = output
        elif event_type == "debate.round.end":
            round_idx = int(content.get("round") or 0)
            checkpoint.debate_rounds.setdefault(
                round_idx, _PartialDebateRound(round_idx=round_idx, started=True)
            ).ended = True
            current_round = None
        elif event_type == "trader.proposal":
            checkpoint.proposal = _proposal_from_event(event)
        elif event_type == "ips.check":
            check = IpsCheck.model_validate(content)
            checkpoint.ips_checks[check.name] = check
        elif event_type == "risk.vote":
            vote = _risk_vote_from_event(event)
            checkpoint.risk_votes[vote.agent_slug] = vote
        elif event_type == "pm.decision":
            checkpoint.decision = _pm_decision_from_event(event)

    return checkpoint


def _analyst_from_event(event: dict[str, Any]) -> AnalystOutput:
    content = event.get("content") if isinstance(event.get("content"), dict) else {}
    agent_slug = str(event.get("agent_slug") or "")
    if not agent_slug:
        raise CommitteeRunRecoveryError("analyst event missing agent_slug")
    return AnalystOutput(
        agent_slug=agent_slug,
        content_md=str(content.get("content_md") or ""),
        score=float(event.get("score") or 0.0),
        evidence=[
            Evidence.model_validate(item)
            for item in content.get("evidence", [])
            if isinstance(item, dict)
        ],
        tokens=int(event.get("tokens") or 0),
        latency_ms=int(event.get("latency_ms") or 0),
    )


def _researcher_from_event(event: dict[str, Any]) -> ResearcherOutput:
    content = event.get("content") if isinstance(event.get("content"), dict) else {}
    role = str(event.get("role") or "")
    if role not in {"bull", "bear"}:
        raise CommitteeRunRecoveryError(f"researcher event has invalid role={role!r}")
    return ResearcherOutput(
        agent_slug=str(event.get("agent_slug") or ""),
        role=role,
        argument_md=str(content.get("argument_md") or ""),
        rebuttals_md=str(content.get("rebuttals_md") or ""),
        score=float(event.get("score") or 0.0),
        evidence=[
            Evidence.model_validate(item)
            for item in content.get("evidence", [])
            if isinstance(item, dict)
        ],
        tokens=int(event.get("tokens") or 0),
        latency_ms=int(event.get("latency_ms") or 0),
    )


def _proposal_from_event(event: dict[str, Any]) -> TradeProposal:
    content = dict(event.get("content") if isinstance(event.get("content"), dict) else {})
    content["tokens"] = int(event.get("tokens") or content.get("tokens") or 0)
    content["latency_ms"] = int(event.get("latency_ms") or content.get("latency_ms") or 0)
    return TradeProposal.model_validate(content)


def _risk_vote_from_event(event: dict[str, Any]) -> RiskVoteOutput:
    content = dict(event.get("content") if isinstance(event.get("content"), dict) else {})
    content["agent_slug"] = str(event.get("agent_slug") or content.get("agent_slug") or "")
    content["score"] = float(event.get("score") or content.get("score") or 0.0)
    content["tokens"] = int(event.get("tokens") or content.get("tokens") or 0)
    content["latency_ms"] = int(event.get("latency_ms") or content.get("latency_ms") or 0)
    return RiskVoteOutput.model_validate(content)


def _pm_decision_from_event(event: dict[str, Any]) -> PmDecision:
    content = dict(event.get("content") if isinstance(event.get("content"), dict) else {})
    content["tokens"] = int(event.get("tokens") or content.get("tokens") or 0)
    content["latency_ms"] = int(event.get("latency_ms") or content.get("latency_ms") or 0)
    return PmDecision.model_validate(content)


def _sum_event_tokens(events: list[dict[str, Any]]) -> int:
    return sum(
        int(event.get("tokens") or 0)
        for event in events
        if event.get("type") not in {"kpi.tick", "run.complete"}
    )


def _mark_recovery_failed(run_id: str, *, error: str) -> int:
    store.mark_failed(run_id, error=error)
    _event_id, seq = store.persist_event(
        run_id,
        type="run.failed",
        stage="system",
        content={"error": error},
    )
    return seq


def _monotonic_anchor_for_run(summary: dict[str, Any] | None) -> float:
    if summary is None:
        return time.monotonic()
    started_at = summary.get("started_at")
    if isinstance(started_at, datetime):
        started_dt = started_at
    elif isinstance(started_at, str) and started_at:
        try:
            started_dt = datetime.fromisoformat(started_at)
        except ValueError:
            return time.monotonic()
    else:
        return time.monotonic()
    if started_dt.tzinfo is None:
        started_dt = started_dt.replace(tzinfo=UTC)
    elapsed_seconds = max(0.0, (datetime.now(tz=UTC) - started_dt).total_seconds())
    return time.monotonic() - elapsed_seconds


async def _emit_stage_enter_once(checkpoint: _RunCheckpoint, stage: str, emit) -> None:
    if stage in checkpoint.stage_enters:
        return
    await emit("stage.enter", stage_name=stage, content={"stage": stage})
    checkpoint.stage_enters.add(stage)


def _next_stage_name(checkpoint: _RunCheckpoint) -> str:
    if any(slug not in checkpoint.analyst_outputs for slug in stages.ANALYST_SLUGS):
        return "analysts"
    for round_idx in range(_DEBATE_ROUNDS):
        partial = checkpoint.debate_rounds.get(round_idx)
        if partial is None or not partial.ended or partial.bull is None or partial.bear is None:
            return "researchers"
    if checkpoint.proposal is None:
        return "trader"
    if any(name not in checkpoint.ips_checks for name in _IPS_CHECK_ORDER):
        return "ips"
    if any(slug not in checkpoint.risk_votes for slug in stages.RISK_SLUGS):
        return "risk"
    if checkpoint.decision is None:
        return "pm"
    return "feedback"


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
    context = _context_from_intelligence_payload(payload)
    # Hydrate per-table snapshots the intelligence payload doesn't carry
    # (intelligence is score-shaped; analysts need the raw rows their
    # prompts cite by name). One narrow query per fetcher, all off the
    # event loop.
    indicators_raw = await asyncio.to_thread(payloads.fetch_technical_indicators, symbol)
    if indicators_raw:
        context["technical_indicators_raw"] = indicators_raw
    fundamentals_raw = await asyncio.to_thread(payloads.fetch_fundamental_snapshot, symbol)
    if fundamentals_raw:
        context["fundamentals_raw"] = fundamentals_raw
    news_raw = await asyncio.to_thread(payloads.fetch_news_sentiment, symbol)
    if news_raw:
        context["news_raw"] = news_raw
    return context


def _context_from_intelligence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Symbol Intelligence sections into the committee analyst slices."""
    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    pillars = scores.get("pillars") if isinstance(scores.get("pillars"), dict) else {}
    news = payload.get("news") if isinstance(payload.get("news"), dict) else None
    return {
        "current_price": _extract_price(payload),
        "fundamentals": _compact_dict(
            {
                "pillar": pillars.get("fundamental"),
                "company": payload.get("company"),
                "portfolio": payload.get("portfolio"),
                "data_quality": scores.get("data_quality"),
            }
        ),
        "valuation": _compact_dict(
            {
                "overall_score": scores.get("overall"),
                "signal_type": scores.get("signal_type"),
                "signal_strength": scores.get("signal_strength"),
                "signal": payload.get("signal"),
                "trading": payload.get("trading"),
                "recommendation": payload.get("recommendation"),
                "decision": payload.get("decision"),
            }
        ),
        "news": _compact_dict(
            {
                "section": news,
                "catalyst_pillar": pillars.get("catalyst"),
                "alerts": payload.get("alerts"),
            }
        ),
        "sentiment": _compact_dict(
            {
                "news_sentiment_score": news.get("sentiment_score") if news else None,
                "news_sentiment_label": news.get("sentiment_label") if news else None,
                "market": payload.get("market"),
                "signal": payload.get("signal"),
            }
        ),
        "options": _compact_dict({"pillar": pillars.get("options_flow")}),
        "ohlcv": _compact_dict(
            {
                "price_pillar": pillars.get("price"),
                "trends": payload.get("trends"),
                "current_price": _extract_price(payload),
            }
        ),
        "indicators": _compact_dict(
            {
                "technical_pillar": pillars.get("technical"),
                "trends": payload.get("trends"),
            }
        ),
    }


def _extract_price(payload: dict[str, Any]) -> float | None:
    """Best-effort current-price extraction from the intelligence payload."""
    for path in (
        ("price",),
        ("market", "price"),
        ("quote", "price"),
        ("technicals", "last_close"),
        ("scores", "pillars", "price", "metadata", "price"),
        ("trading", "entry_price"),
    ):
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


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Remove empty top-level context fields while preserving nested payload shape."""
    compacted: dict[str, Any] = {}
    for key, item in value.items():
        if item is None:
            continue
        if isinstance(item, (dict, list)) and not item:
            continue
        compacted[key] = item
    return compacted


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
