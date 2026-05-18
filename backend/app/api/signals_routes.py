"""Unified signals API — L1 macro gate + L2 scanner + L3 committee blender.

Read-only endpoints. All writes happen in the workflows
(``macro_gate_wf`` → ``scanner_wf`` → ``committee_fanout_wf``).

* ``GET /api/signals/blended``     — latest scanner run, blended with
  the freshest committee verdict per symbol, sorted by blended score.
* ``GET /api/signals/rank-deltas`` — only the rows whose committee
  blend moves them at least three places vs. their scanner-only rank.
* ``GET /api/signals/symbol/{t}``  — one symbol's macro context +
  scanner history + latest committee verdict (the data the
  ``/symbols/[ticker]`` UI cards consume).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ..agents.committee import store as committee_store
from ..logging_config import get_logger
from ..macro_gate import repository as macro_repo
from ..scanner import blender as blender_mod
from ..scanner import repository as scanner_repo
from ..scanner.factors import FACTOR_NAMES

logger = get_logger(__name__)
router = APIRouter(prefix="/api/signals", tags=["signals"])


# ---------------------------------------------------------------- response shapes


class CommitteeSignalResponse(BaseModel):
    run_id: str
    action: str | None
    confidence: float | None
    pm_score: float          # 0-10 derived from action+confidence
    completed_at: str | None
    source: str | None
    scanner_rank: int | None


class BlendedRowResponse(BaseModel):
    symbol: str
    scanner_rank: int
    blended_rank: int
    delta_rank: int
    flagged: bool
    scanner_composite_pct: float
    blended_score: float
    committee: CommitteeSignalResponse | None


class ScannerRunMeta(BaseModel):
    run_id: str
    run_date: str
    gate_zone: str
    gate_score: float | None
    universe_size: int
    scored_count: int
    skip_reason: str | None = None


class BlendWeightsResponse(BaseModel):
    scanner: float
    committee: float


class BlendedResponse(BaseModel):
    run: ScannerRunMeta
    weights: BlendWeightsResponse
    rows: list[BlendedRowResponse]


class RankDeltasResponse(BaseModel):
    run: ScannerRunMeta
    weights: BlendWeightsResponse
    threshold: int
    rows: list[BlendedRowResponse]


class MacroContextResponse(BaseModel):
    snapshot_date: str | None
    zone: str | None
    deployment_score: float | None
    components: dict[str, float | None]


class SymbolScannerRow(BaseModel):
    run_date: str
    gate_zone: str
    rank: int
    composite_pct: float | None
    factor_coverage: float | None
    percentiles: dict[str, float | None]


class SymbolUnifiedResponse(BaseModel):
    symbol: str
    macro: MacroContextResponse
    scanner: list[SymbolScannerRow]
    committee: CommitteeSignalResponse | None


# ---------------------------------------------------------------- helpers


def _committee_signal(payload: dict[str, Any] | None) -> blender_mod.CommitteeSignal | None:
    if not payload:
        return None
    action = payload.get("action")
    confidence = payload.get("confidence")
    return blender_mod.CommitteeSignal(
        run_id=str(payload["run_id"]),
        action=str(action) if action else "",
        confidence=float(confidence) if confidence is not None else 0.0,
        pm_score=blender_mod.pm_score_from_decision(action, confidence),
    )


def _committee_response(
    signal: blender_mod.CommitteeSignal | None,
    raw: dict[str, Any] | None,
) -> CommitteeSignalResponse | None:
    if signal is None or raw is None:
        return None
    return CommitteeSignalResponse(
        run_id=signal.run_id,
        action=raw.get("action"),
        confidence=raw.get("confidence"),
        pm_score=signal.pm_score,
        completed_at=raw.get("completed_at"),
        source=raw.get("source"),
        scanner_rank=raw.get("scanner_rank"),
    )


def _macro_context(snapshot: dict[str, Any] | None) -> MacroContextResponse:
    if snapshot is None:
        return MacroContextResponse(
            snapshot_date=None,
            zone=None,
            deployment_score=None,
            components={
                "vix": None,
                "term": None,
                "breadth": None,
                "credit": None,
                "putcall": None,
                "crowding": None,
            },
        )
    return MacroContextResponse(
        snapshot_date=snapshot.get("snapshot_date"),
        zone=snapshot.get("zone"),
        deployment_score=snapshot.get("deployment_score"),
        components={
            "vix": snapshot.get("vix_score"),
            "term": snapshot.get("term_score"),
            "breadth": snapshot.get("breadth_score"),
            "credit": snapshot.get("credit_score"),
            "putcall": snapshot.get("putcall_score"),
            "crowding": snapshot.get("crowding_score"),
        },
    )


def _scanner_meta(run: dict[str, Any]) -> ScannerRunMeta:
    return ScannerRunMeta(
        run_id=run["run_id"],
        run_date=run["run_date"],
        gate_zone=run["gate_zone"],
        gate_score=run.get("gate_score"),
        universe_size=run["universe_size"],
        scored_count=run["scored_count"],
        skip_reason=run.get("skip_reason"),
    )


def _weights_response(w: blender_mod.BlendWeights) -> BlendWeightsResponse:
    return BlendWeightsResponse(scanner=w.scanner, committee=w.committee)


def _row_response(
    row: blender_mod.BlendedRow,
    committee_raw_by_symbol: dict[str, dict[str, Any]],
) -> BlendedRowResponse:
    raw = committee_raw_by_symbol.get(row.symbol)
    return BlendedRowResponse(
        symbol=row.symbol,
        scanner_rank=row.scanner_rank,
        blended_rank=row.blended_rank,
        delta_rank=row.delta_rank,
        flagged=row.flagged,
        scanner_composite_pct=row.scanner_composite_pct,
        blended_score=row.blended_score,
        committee=_committee_response(row.committee, raw),
    )


def _build_blended(
    limit: int,
    weights: blender_mod.BlendWeights | None = None,
) -> tuple[dict[str, Any], blender_mod.BlendWeights, list[blender_mod.BlendedRow], dict[str, dict[str, Any]]] | None:
    run = scanner_repo.get_latest_run()
    if run is None:
        return None
    scores: list[dict[str, Any]] = []
    if run.get("skip_reason") is None:
        scores = scanner_repo.get_scores_for_run(UUID(run["run_id"]), limit=limit)
    if not scores:
        return run, weights or blender_mod.env_weights(), [], {}
    symbols = [str(r["symbol"]) for r in scores]
    raw_by_symbol = committee_store.get_latest_completed_by_symbol(symbols)
    signal_by_symbol = {
        sym: signal
        for sym, payload in raw_by_symbol.items()
        if (signal := _committee_signal(payload)) is not None
    }
    weights_eff = weights or blender_mod.env_weights()
    rows = blender_mod.blend(scores, signal_by_symbol, weights=weights_eff)
    return run, weights_eff, rows, raw_by_symbol


# ---------------------------------------------------------------- routes


@router.get("/blended", response_model=BlendedResponse)
async def blended(
    limit: int = Query(default=50, ge=1, le=500),
    weight_scanner: float | None = Query(default=None, ge=0.0, le=1.0),
    weight_committee: float | None = Query(default=None, ge=0.0, le=1.0),
) -> BlendedResponse:
    weights = _resolve_weights(weight_scanner, weight_committee)
    result = await run_in_threadpool(_build_blended, limit, weights)
    if result is None:
        raise HTTPException(status_code=503, detail="signals_no_scanner_run_yet")
    run, weights_eff, rows, raw_by_symbol = result
    return BlendedResponse(
        run=_scanner_meta(run),
        weights=_weights_response(weights_eff),
        rows=[_row_response(r, raw_by_symbol) for r in rows],
    )


@router.get("/rank-deltas", response_model=RankDeltasResponse)
async def rank_deltas(
    limit: int = Query(default=200, ge=1, le=500),
    weight_scanner: float | None = Query(default=None, ge=0.0, le=1.0),
    weight_committee: float | None = Query(default=None, ge=0.0, le=1.0),
) -> RankDeltasResponse:
    weights = _resolve_weights(weight_scanner, weight_committee)
    result = await run_in_threadpool(_build_blended, limit, weights)
    if result is None:
        raise HTTPException(status_code=503, detail="signals_no_scanner_run_yet")
    run, weights_eff, rows, raw_by_symbol = result
    flagged = [r for r in rows if r.flagged]
    return RankDeltasResponse(
        run=_scanner_meta(run),
        weights=_weights_response(weights_eff),
        threshold=blender_mod.DELTA_RANK_FLAG_THRESHOLD,
        rows=[_row_response(r, raw_by_symbol) for r in flagged],
    )


@router.get("/symbol/{ticker}", response_model=SymbolUnifiedResponse)
async def symbol_unified(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365),
) -> SymbolUnifiedResponse:
    sym = ticker.upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="empty_ticker")

    macro = await run_in_threadpool(macro_repo.get_latest)
    scanner_rows = await run_in_threadpool(scanner_repo.get_history_for_symbol, sym, days)
    raw_committee = await run_in_threadpool(
        committee_store.get_latest_completed_by_symbol, [sym]
    )
    raw = raw_committee.get(sym)
    signal = _committee_signal(raw)

    return SymbolUnifiedResponse(
        symbol=sym,
        macro=_macro_context(macro),
        scanner=[
            SymbolScannerRow(
                run_date=row["run_date"],
                gate_zone=row["gate_zone"],
                rank=int(row["rank"]),
                composite_pct=row.get("composite_pct"),
                factor_coverage=row.get("factor_coverage"),
                percentiles={name: row.get(f"{name}_pct") for name in FACTOR_NAMES},
            )
            for row in scanner_rows
        ],
        committee=_committee_response(signal, raw),
    )


def _resolve_weights(
    weight_scanner: float | None, weight_committee: float | None
) -> blender_mod.BlendWeights | None:
    """Build a per-call weights override from query params, or fall back to env."""
    if weight_scanner is None and weight_committee is None:
        return None
    base = blender_mod.env_weights()
    return blender_mod.BlendWeights(
        scanner=weight_scanner if weight_scanner is not None else base.scanner,
        committee=weight_committee if weight_committee is not None else base.committee,
    ).normalised()
