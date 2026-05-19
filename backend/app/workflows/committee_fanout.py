"""L3 committee fan-out workflow.

Chained off the L2 scanner. Reads the latest scanner run, drops the
DEFENSIVE case, applies the cross-run cache, enforces a per-day rate
cap, and spawns up to N committee runs against the top-ranked tickers.

Each spawned ``committee_runs`` row carries ``source='scanner_fanout'``
+ ``scanner_rank`` so the unified ``/api/signals/*`` views can show
provenance and the cost ledger can attribute spend to the fan-out
versus user-triggered runs.

The actual committee orchestration runs as in-process asyncio tasks
attached to the worker's event loop — same pattern the
``/api/portfolio/committee/runs`` route uses. We do not block the fan-out
task on completion; the fan-out's job is to *kick off* the runs and
return.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from importlib import import_module
from typing import Any
from uuid import UUID

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.agents.committee import (
    GRAPH_VERSION,
    cache,
    candidate_fundamentals,
    graph,
    readiness,
    stages,
)
from app.agents.committee import store as committee_store
from app.agents.committee import stream as committee_stream
from app.agents.committee.schemas import Tier1Verdict
from app.hatchet_app import hatchet
from app.logging_config import get_logger
from app.scanner import repository as scanner_repo
from app.storage.connection import get_connection_manager

from .models import EmptyInput

logger = get_logger(__name__)

DEFAULT_TOP_N = 25
DEFAULT_MAX_DAILY = 25  # belt-and-braces in addition to top-N
# How many of the scanner top-N survive Tier-1 and trigger the deep committee.
# Sized to the funnel literature (cheap pre-filter → deep dive shortlist).
DEFAULT_TIER1_KEEP = 8
_CONVICTION_RANK: dict[str, int] = {"high": 2, "mid": 1, "low": 0}

# Worker-process registry of spawned tasks; mirrors
# ``app.api.committee_runs._RUNNER_TASKS`` so the loop holds a strong
# reference until each run completes.
_FANOUT_TASKS: set[asyncio.Task[None]] = set()


@dataclass(frozen=True, slots=True)
class FanoutOutput:
    run_date: date
    gate_zone: str
    scanner_run_id: str | None
    spawned: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    skip_reason: str | None
    tier1_verdicts: list[dict[str, Any]] = field(default_factory=list)


@hatchet.task(
    name="portfolio-committee-fanout",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=1,
    backoff_factor=2.0,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-committee-fanout'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def committee_fanout_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    output = await asyncio.to_thread(run_fanout, loop=loop)
    payload: dict[str, Any] = {
        "status": "ok" if output.skip_reason is None else "skipped",
        "gate_zone": output.gate_zone,
        "run_date": output.run_date.isoformat(),
        "scanner_run_id": output.scanner_run_id,
        "spawned_count": len(output.spawned),
        "skipped_count": len(output.skipped),
        "tier1_verdict_count": len(output.tier1_verdicts),
        "spawned": output.spawned,
        "skipped": output.skipped,
        "tier1_verdicts": output.tier1_verdicts,
    }
    if output.skip_reason:
        payload["skip_reason"] = output.skip_reason
    return payload


def run_fanout(
    *,
    top_n: int | None = None,
    max_daily: int | None = None,
    now: datetime | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> FanoutOutput:
    """Synchronous fan-out kernel; safe to call from a worker thread.

    Spawns the committee tasks on ``loop`` when supplied (the Hatchet
    worker passes its own running loop); otherwise — e.g. when called
    from a backfill script with no loop attached — records the planned
    spawns but does not start them. That guard keeps the function
    testable without a live worker.
    """
    top_n = top_n if top_n is not None else _int_env("COMMITTEE_FANOUT_TOP_N", DEFAULT_TOP_N)
    max_daily = (
        max_daily
        if max_daily is not None
        else _int_env("COMMITTEE_FANOUT_MAX_DAILY", DEFAULT_MAX_DAILY)
    )
    current = (now or datetime.now(tz=UTC)).astimezone(UTC)

    latest = scanner_repo.get_latest_run()
    if latest is None:
        logger.warning("committee_fanout_no_scanner_run")
        return FanoutOutput(
            run_date=current.date(),
            gate_zone="UNKNOWN",
            scanner_run_id=None,
            spawned=[],
            skipped=[],
            skip_reason="no_scanner_run",
        )

    gate_zone = str(latest["gate_zone"])
    scanner_run_id = str(latest["run_id"])
    run_date = _parse_date(latest.get("run_date")) or current.date()

    if gate_zone == "DEFENSIVE":
        logger.info(
            "committee_fanout_skipped_defensive",
            scanner_run_id=scanner_run_id,
            run_date=run_date.isoformat(),
        )
        return FanoutOutput(
            run_date=run_date,
            gate_zone=gate_zone,
            scanner_run_id=scanner_run_id,
            spawned=[],
            skipped=[],
            skip_reason="gate_defensive",
        )

    scores = scanner_repo.get_scores_for_run(UUID(scanner_run_id), limit=top_n)
    if not scores:
        return FanoutOutput(
            run_date=run_date,
            gate_zone=gate_zone,
            scanner_run_id=scanner_run_id,
            spawned=[],
            skipped=[],
            skip_reason="no_scores",
        )

    already_today = _count_fanout_today(run_date=run_date)
    remaining_budget = max(0, max_daily - already_today)
    if remaining_budget <= 0:
        logger.info(
            "committee_fanout_rate_capped",
            run_date=run_date.isoformat(),
            already_today=already_today,
            max_daily=max_daily,
        )
        return FanoutOutput(
            run_date=run_date,
            gate_zone=gate_zone,
            scanner_run_id=scanner_run_id,
            spawned=[],
            skipped=[
                {"symbol": str(row["symbol"]).upper(),
                 "scanner_rank": int(row["rank"]),
                 "reason": "max_daily_reached"}
                for row in scores
            ],
            skip_reason="max_daily_reached",
        )

    spawned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    tier1_verdicts: list[dict[str, Any]] = []
    spawn_loop = loop

    # Filter scanner rows by cache + readiness + remaining budget _before_
    # Tier-1, so we don't burn screener calls on symbols we'd skip anyway.
    # Tier-1 itself is an LLM call; the readiness gate has to fire ahead of
    # it or the cost-saving promise is hollow.
    candidates: list[dict[str, Any]] = []
    for row in scores:
        symbol = str(row["symbol"]).upper()
        scanner_rank = int(row["rank"])
        decision = cache.should_run(symbol, current_zone=gate_zone, now=current)
        if not decision.should_run:
            skipped.append(
                {
                    "symbol": symbol,
                    "scanner_rank": scanner_rank,
                    "reason": decision.reason,
                    "last_run_id": decision.last_run_id,
                }
            )
            continue
        # Pre-fundamentals check: OHLCV + indicators + news must be present.
        # Fundamentals are pulled on-demand below; the post-fetch gate runs
        # again on the Tier-1 survivors only.
        report = readiness.check_committee_readiness(
            symbol, now=current, source="scanner_fanout"
        )
        blocking_pre = {i.check for i in report.blocking_issues}
        # The fundamentals-missing block is expected at this stage — we
        # haven't fetched yet. Any other block is a real input gap that
        # disqualifies the candidate before Tier-1.
        non_fundamentals_blocks = blocking_pre - {
            "candidate_fundamentals_missing",
            "candidate_fundamentals_stale",
            "candidate_fundamentals_fetch_failed",
        }
        if non_fundamentals_blocks:
            logger.info(
                "committee_fanout_skipped_data_unready",
                symbol=symbol,
                scanner_rank=scanner_rank,
                blocking=sorted(non_fundamentals_blocks),
            )
            skipped.append(
                {
                    "symbol": symbol,
                    "scanner_rank": scanner_rank,
                    "reason": "data_unready",
                    "blocking_checks": sorted(non_fundamentals_blocks),
                    "report": report.to_dict(),
                }
            )
            continue
        candidates.append({"symbol": symbol, "scanner_rank": scanner_rank, "row": row})

    # Tier-1 cheap pre-screen: only when there's a running loop to await on.
    # Tests pass loop=None and fall back to scanner-rank ordering.
    tier1_keep = _int_env("COMMITTEE_TIER1_KEEP", DEFAULT_TIER1_KEEP)
    if spawn_loop is not None and candidates:
        verdicts = _run_tier1_batch(spawn_loop, candidates, gate_zone=gate_zone)
        ranked = _rank_candidates_by_tier1(candidates, verdicts)
        # Record every verdict for telemetry / cost ledger.
        tier1_verdicts = [
            {
                "symbol": v.symbol,
                "score": v.score,
                "conviction": v.conviction,
                "top_factor": v.top_factor,
                "one_line_rationale": v.one_line_rationale,
                "tokens": v.tokens,
                "latency_ms": v.latency_ms,
            }
            for v in verdicts
        ]
        # Everything past tier1_keep is dropped from this fan-out with a clean reason.
        for entry in ranked[tier1_keep:]:
            skipped.append(
                {
                    "symbol": entry["symbol"],
                    "scanner_rank": entry["scanner_rank"],
                    "reason": "tier1_below_cut",
                    "tier1_score": entry.get("tier1_score"),
                    "tier1_conviction": entry.get("tier1_conviction"),
                }
            )
        ordered = ranked[:tier1_keep]
    else:
        ordered = candidates

    # On-demand fundamentals: pull 4 quarters + derived ratios for each
    # Tier-1 survivor before spawning the deep run. Failures bump the
    # candidate to skipped[] so we never spawn a deep run on a symbol
    # the analyst can't ground its decision in.
    ordered_with_fundamentals: list[dict[str, Any]] = []
    for entry in ordered:
        symbol = entry["symbol"]
        payload = candidate_fundamentals.fetch_candidate_fundamentals(symbol)
        if payload is None:
            skipped.append(
                {
                    "symbol": symbol,
                    "scanner_rank": entry["scanner_rank"],
                    "reason": "fundamentals_fetch_failed",
                    "tier1_score": entry.get("tier1_score"),
                    "tier1_conviction": entry.get("tier1_conviction"),
                }
            )
            continue
        ordered_with_fundamentals.append(entry)
    ordered = ordered_with_fundamentals

    for entry in ordered:
        symbol = entry["symbol"]
        scanner_rank = entry["scanner_rank"]
        if len(spawned) >= remaining_budget:
            skipped.append(
                {
                    "symbol": symbol,
                    "scanner_rank": scanner_rank,
                    "reason": "max_daily_reached",
                }
            )
            continue
        run_id = committee_store.create_run(
            symbol=symbol,
            household_id=None,
            parent_run_id=None,
            graph_version=GRAPH_VERSION,
            source="scanner_fanout",
            scanner_rank=scanner_rank,
        )
        if spawn_loop is not None:
            asyncio.run_coroutine_threadsafe(
                _register_and_run(run_id=run_id, symbol=symbol), spawn_loop
            )
        spawned.append(
            {
                "symbol": symbol,
                "scanner_rank": scanner_rank,
                "run_id": run_id,
                "tier1_score": entry.get("tier1_score"),
                "tier1_conviction": entry.get("tier1_conviction"),
            }
        )

    logger.info(
        "committee_fanout_completed",
        scanner_run_id=scanner_run_id,
        gate_zone=gate_zone,
        spawned=len(spawned),
        skipped=len(skipped),
        tier1_verdicts=len(tier1_verdicts),
    )
    return FanoutOutput(
        run_date=run_date,
        gate_zone=gate_zone,
        scanner_run_id=scanner_run_id,
        spawned=spawned,
        skipped=skipped,
        skip_reason=None,
        tier1_verdicts=tier1_verdicts,
    )


async def _register_and_run(*, run_id: str, symbol: str) -> None:
    """Attach a stream queue and run the committee orchestrator.

    Mirrors ``app.api.committee_runs._schedule_run`` + ``_run_committee_safely``.
    """
    if committee_stream.get(run_id) is None:
        await committee_stream.register(run_id)
    task = asyncio.create_task(_run_committee_safely(run_id=run_id, symbol=symbol))
    _FANOUT_TASKS.add(task)
    task.add_done_callback(_FANOUT_TASKS.discard)


async def _run_committee_safely(*, run_id: str, symbol: str) -> None:
    try:
        await graph.run_committee(
            run_id=run_id,
            symbol=symbol,
            household_id=None,
            parent_run_id=None,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("committee_fanout_runner_crashed", run_id=run_id, symbol=symbol)


def _run_tier1_batch(
    spawn_loop: asyncio.AbstractEventLoop,
    candidates: list[dict[str, Any]],
    *,
    gate_zone: str,
) -> list[Tier1Verdict]:
    """Run Tier-1 screening concurrently for every candidate on ``spawn_loop``.

    Called from the synchronous ``run_fanout`` thread; submits the gather
    onto the worker's event loop via ``run_coroutine_threadsafe`` and
    blocks the calling thread until the batch completes. The per-call
    concurrency cap is enforced by the semaphore inside ``stages._complete``.
    """

    async def _gather() -> list[Tier1Verdict | BaseException]:
        tasks = [
            stages.run_tier1_screen(
                symbol=c["symbol"],
                scanner_factors=_scanner_factors_payload(c["row"]),
                context_bundle=await asyncio.to_thread(
                    _build_tier1_context_bundle, c["symbol"]
                ),
                gate_zone=gate_zone,
            )
            for c in candidates
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    future = asyncio.run_coroutine_threadsafe(_gather(), spawn_loop)
    results = future.result()
    verdicts: list[Tier1Verdict] = []
    for cand, result in zip(candidates, results, strict=True):
        if isinstance(result, BaseException):
            logger.warning(
                "committee_tier1_failed",
                symbol=cand["symbol"],
                error=str(result),
            )
            # On failure, fall back to a neutral conviction=low so the symbol
            # ranks behind anything Tier-1 actually evaluated. This keeps a
            # transient LLM failure from bumping a low-quality candidate above
            # a known-strong one purely by absence.
            verdicts.append(
                Tier1Verdict(
                    agent_slug=stages.SLUG_TIER1,
                    symbol=cand["symbol"],
                    score=0.0,
                    conviction="low",
                    one_line_rationale="Tier-1 screen failed; defaulted to neutral.",
                    top_factor="other",
                )
            )
        else:
            verdicts.append(result)
    return verdicts


def _rank_candidates_by_tier1(
    candidates: list[dict[str, Any]],
    verdicts: list[Tier1Verdict],
) -> list[dict[str, Any]]:
    """Sort candidates by (conviction tier, score, scanner_rank) desc.

    Ties broken by the deterministic scanner rank so the ordering is stable
    across re-fires when Tier-1 returns the same numbers.
    """
    by_symbol = {v.symbol: v for v in verdicts}
    enriched: list[dict[str, Any]] = []
    for cand in candidates:
        v = by_symbol.get(cand["symbol"])
        enriched.append(
            {
                **cand,
                "tier1_score": v.score if v else 0.0,
                "tier1_conviction": v.conviction if v else "low",
            }
        )
    enriched.sort(
        key=lambda e: (
            -_CONVICTION_RANK.get(str(e["tier1_conviction"]), 0),
            -float(e["tier1_score"]),
            int(e["scanner_rank"]),
        )
    )
    return enriched


def _scanner_factors_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Slim down the scanner score row to the fields the Tier-1 prompt cares about."""
    keys = (
        "rank",
        "composite_pct",
        "factor_coverage",
        "mom_xover_pct",
        "vol_surge_pct",
        "rs_vs_spy_pct",
        "high_52w_proximity_pct",
        "short_interest_decline_pct",
    )
    return {k: row.get(k) for k in keys if row.get(k) is not None}


def _build_tier1_context_bundle(symbol: str) -> dict[str, Any]:
    """Minimal context bundle: price snapshot + top-3 news + fundamentals summary.

    Built off ``build_symbol_intelligence`` since that pipeline already
    aggregates the relevant sources behind one entry point. Failures here
    are non-fatal — Tier-1 just sees an empty bundle and scores cautiously.
    """
    try:
        svc = import_module("app.api.symbols.service")
        intelligence = svc.build_symbol_intelligence(symbol)
        payload: dict[str, Any] = (
            intelligence.model_dump(mode="json")
            if hasattr(intelligence, "model_dump")
            else dict(intelligence)
        )
    except Exception as exc:
        logger.warning("committee_tier1_bundle_build_failed", symbol=symbol, error=str(exc))
        return {}
    news = payload.get("news") if isinstance(payload.get("news"), dict) else {}
    headlines = news.get("headlines") if isinstance(news, dict) else None
    top_headlines: list[dict[str, Any]] = []
    if isinstance(headlines, list):
        for item in headlines[:3]:
            if isinstance(item, dict):
                top_headlines.append(
                    {k: item.get(k) for k in ("title", "url", "published_at", "source") if item.get(k)}
                )
    company = payload.get("company") if isinstance(payload.get("company"), dict) else None
    market = payload.get("market") if isinstance(payload.get("market"), dict) else None
    scores = payload.get("scores") if isinstance(payload.get("scores"), dict) else {}
    pillars = scores.get("pillars") if isinstance(scores.get("pillars"), dict) else {}
    bundle: dict[str, Any] = {
        "current_price": _extract_price(payload),
        "company_summary": {
            k: company.get(k)
            for k in ("sector", "industry", "market_cap")
            if company and company.get(k) is not None
        } if company else None,
        "market_snapshot": {
            k: market.get(k)
            for k in ("change_pct", "volume", "avg_volume_30d")
            if market and market.get(k) is not None
        } if market else None,
        "fundamentals_pillar": pillars.get("fundamental") if isinstance(pillars, dict) else None,
        "technical_pillar": pillars.get("technical") if isinstance(pillars, dict) else None,
        "news_sentiment": {
            "score": news.get("sentiment_score") if news else None,
            "label": news.get("sentiment_label") if news else None,
            "top_headlines": top_headlines,
        },
    }
    return {k: v for k, v in bundle.items() if v not in (None, {}, [])}


def _extract_price(payload: dict[str, Any]) -> float | None:
    for path in (
        ("price",),
        ("market", "price"),
        ("quote", "price"),
        ("scores", "pillars", "price", "metadata", "price"),
    ):
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _count_fanout_today(*, run_date: date) -> int:
    """Count fan-out runs already initiated on ``run_date`` (any status)."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM committee_runs
            WHERE source = 'scanner_fanout'
              AND started_at::date = %s::date
            """,
            (run_date,),
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default
