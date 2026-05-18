"""L2 quantitative scanner service.

Pulls the active universe + OHLCV + short interest in one pass, computes
the five factors per symbol, percentile-ranks within the universe, builds
the equal-weight composite, and persists the run.

Macro-gate zone governs the write behaviour:

- ``FULL_DEPLOY`` writes every member with at least one valid factor.
- ``REDUCED``     writes only members with ``composite_pct > 75``.
- ``DEFENSIVE``   writes nothing (header row with ``skip_reason``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from ..logging_config import get_logger
from ..macro_gate import repository as macro_repo
from ..services import research_universe as universe_service
from ..storage.facade import get_storage
from . import factors, repository

logger = get_logger(__name__)

SPY_SYMBOL = "SPY"
OHLCV_LOOKBACK_DAYS = 260  # 252 trading days + buffer for 52WHighProximity
REDUCED_THRESHOLD = 75.0   # composite_pct cutoff for REDUCED zone


@dataclass(frozen=True, slots=True)
class ScannerOutput:
    run_id: UUID
    run_date: date
    gate_zone: str
    universe_size: int
    scored_count: int
    skip_reason: str | None


def run(snapshot_date: date | None = None) -> ScannerOutput | None:
    """Compute and persist today's scanner run.

    ``snapshot_date`` lets backtests replay against a historical gate +
    bar window; default is today.
    """
    gate = macro_repo.get_latest()
    if gate is None:
        logger.warning("scanner_no_macro_snapshot")
        return None

    gate_zone = str(gate["zone"])
    gate_score = gate.get("deployment_score")
    run_date = snapshot_date or date.today()
    universe = universe_service.list_active_symbols()

    if gate_zone == "DEFENSIVE":
        run_id = repository.create_run(
            run_date=run_date,
            gate_zone=gate_zone,
            gate_score=gate_score,
            universe_size=len(universe),
            skip_reason="gate_defensive",
        )
        repository.finalize_run(run_id, scored_count=0)
        logger.info(
            "scanner_skipped_defensive",
            run_id=str(run_id),
            universe_size=len(universe),
        )
        return ScannerOutput(
            run_id=run_id,
            run_date=run_date,
            gate_zone=gate_zone,
            universe_size=len(universe),
            scored_count=0,
            skip_reason="gate_defensive",
        )

    if not universe:
        logger.warning("scanner_no_universe", gate_zone=gate_zone)
        return None

    spy_closes = _fetch_closes(SPY_SYMBOL, snapshot_date=snapshot_date)
    if len(spy_closes) < 21:
        logger.warning("scanner_spy_data_thin", available=len(spy_closes))

    raw_per_symbol: dict[str, dict[str, float | None]] = {}
    for sym in universe:
        raw_per_symbol[sym] = _factors_for(sym, spy_closes, snapshot_date=snapshot_date)

    percentiles = _percentile_ranks(raw_per_symbol)
    composites = _composites(percentiles)
    ranked = _rank(composites)

    if gate_zone == "REDUCED":
        ranked = [(sym, comp) for sym, comp in ranked if comp > REDUCED_THRESHOLD]

    score_rows = list(
        _build_score_rows(ranked, raw_per_symbol, percentiles, composites)
    )

    run_id = repository.create_run(
        run_date=run_date,
        gate_zone=gate_zone,
        gate_score=gate_score,
        universe_size=len(universe),
    )
    repository.insert_scores(run_id, score_rows)
    repository.finalize_run(run_id, scored_count=len(score_rows))

    logger.info(
        "scanner_run_completed",
        run_id=str(run_id),
        gate_zone=gate_zone,
        universe_size=len(universe),
        scored_count=len(score_rows),
    )
    return ScannerOutput(
        run_id=run_id,
        run_date=run_date,
        gate_zone=gate_zone,
        universe_size=len(universe),
        scored_count=len(score_rows),
        skip_reason=None,
    )


def _fetch_closes(symbol: str, *, snapshot_date: date | None) -> list[float]:
    storage = get_storage()
    if snapshot_date is None:
        sql = (
            "SELECT date, close FROM day_bars "
            "WHERE symbol = %s ORDER BY date DESC LIMIT %s"
        )
        params: list[Any] = [symbol, OHLCV_LOOKBACK_DAYS]
    else:
        sql = (
            "SELECT date, close FROM day_bars "
            "WHERE symbol = %s AND date <= %s::date "
            "ORDER BY date DESC LIMIT %s"
        )
        params = [symbol, str(snapshot_date), OHLCV_LOOKBACK_DAYS]
    with storage.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    # DESC fetch -> reverse to ascending so factor functions get oldest→newest
    return [float(r[1]) for r in reversed(rows) if r[1] is not None]


def _fetch_volumes(symbol: str, *, snapshot_date: date | None) -> list[float]:
    storage = get_storage()
    if snapshot_date is None:
        sql = (
            "SELECT date, volume FROM day_bars "
            "WHERE symbol = %s ORDER BY date DESC LIMIT %s"
        )
        params: list[Any] = [symbol, 30]
    else:
        sql = (
            "SELECT date, volume FROM day_bars "
            "WHERE symbol = %s AND date <= %s::date "
            "ORDER BY date DESC LIMIT %s"
        )
        params = [symbol, str(snapshot_date), 30]
    with storage.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [float(r[1]) for r in reversed(rows) if r[1] is not None]


def _fetch_short_interest(symbol: str) -> tuple[float | None, float | None]:
    """Return ``(current_pct_of_float, prior_pct_of_float)`` for ``symbol``."""
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT short_percent_of_float, short_prior_month
            FROM short_interest
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [symbol],
        ).fetchone()
    if not row:
        return None, None
    return _to_float(row[0]), _to_float(row[1])


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _factors_for(
    symbol: str,
    spy_closes: list[float],
    *,
    snapshot_date: date | None,
) -> dict[str, float | None]:
    closes = _fetch_closes(symbol, snapshot_date=snapshot_date)
    volumes = _fetch_volumes(symbol, snapshot_date=snapshot_date)
    current_si, prior_si = _fetch_short_interest(symbol)
    return {
        "mom_xover": factors.mom_xover(closes),
        "vol_surge": factors.vol_surge(volumes),
        "rs_vs_spy": factors.rs_vs_spy(closes, spy_closes),
        "high_52w_proximity": factors.high_52w_proximity(closes),
        "short_interest_decline": factors.short_interest_decline(current_si, prior_si),
    }


def _percentile_ranks(
    raw_per_symbol: dict[str, dict[str, float | None]],
) -> dict[str, dict[str, float | None]]:
    """For each factor, rank-percentile across all symbols with a value.

    Missing values stay ``None``. Ties share the average percentile.
    Result is the 0-100 percentile of the raw value within the universe;
    higher = stronger on that factor.
    """
    out: dict[str, dict[str, float | None]] = {sym: {} for sym in raw_per_symbol}
    for factor in factors.FACTOR_NAMES:
        observed = [
            (sym, v) for sym, raw in raw_per_symbol.items()
            for k, v in raw.items() if k == factor and v is not None
        ]
        if not observed:
            for sym in raw_per_symbol:
                out[sym][factor] = None
            continue
        observed.sort(key=lambda pair: pair[1])
        n = len(observed)
        # Assign avg-percentile for ties
        i = 0
        ranks: dict[str, float] = {}
        while i < n:
            j = i
            while j + 1 < n and observed[j + 1][1] == observed[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0  # 0-indexed average position in sorted asc
            pct = (avg_rank / (n - 1) * 100.0) if n > 1 else 100.0
            for k in range(i, j + 1):
                ranks[observed[k][0]] = pct
            i = j + 1
        for sym in raw_per_symbol:
            out[sym][factor] = ranks.get(sym)
    return out


def _composites(
    percentiles: dict[str, dict[str, float | None]],
) -> dict[str, tuple[float, float]]:
    """Equal-weight composite. Returns ``{symbol: (composite_pct, coverage)}``.

    Missing factors are dropped from the mean; ``coverage`` is the share of
    factors present, so callers can filter by coverage if desired.
    """
    out: dict[str, tuple[float, float]] = {}
    for sym, by_factor in percentiles.items():
        present = [v for v in by_factor.values() if v is not None]
        if not present:
            continue
        coverage = len(present) / len(factors.FACTOR_NAMES)
        out[sym] = (sum(present) / len(present), coverage)
    return out


def _rank(composites: dict[str, tuple[float, float]]) -> list[tuple[str, float]]:
    """Return ``[(symbol, composite_pct), ...]`` sorted desc by composite."""
    return sorted(
        ((sym, comp) for sym, (comp, _) in composites.items()),
        key=lambda pair: pair[1],
        reverse=True,
    )


def _build_score_rows(
    ranked: list[tuple[str, float]],
    raw_per_symbol: dict[str, dict[str, float | None]],
    percentiles: dict[str, dict[str, float | None]],
    composites: dict[str, tuple[float, float]],
) -> Iterable[repository.ScoreRow]:
    for rank_idx, (sym, comp) in enumerate(ranked, start=1):
        _, coverage = composites[sym]
        yield repository.ScoreRow(
            symbol=sym,
            factors=raw_per_symbol[sym],
            percentiles=percentiles[sym],
            composite_pct=comp,
            rank=rank_idx,
            factor_coverage=coverage,
        )
