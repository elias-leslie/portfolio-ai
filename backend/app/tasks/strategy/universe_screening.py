"""Universe-wide walk-forward screening.

Sweeps the active research universe (S&P 500 constituents) through the
walk-forward backtest harness against the generic EnhancedSignalStrategy,
persists per-symbol results, and computes a denormalized edge_score so the
catalog UI can rank candidates without recomputing.

Schedule (suggested): weekly Hatchet workflow, Sunday 06:30 UTC, after
research universe refresh.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Any

from app.backtest.walk_forward import WalkForwardEngine, WalkForwardResult
from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

DEFAULT_BACKTEST_YEARS = 6
MIN_TRADES_FOR_RANKING = 10
MIN_FOLDS_FOR_RANKING = 3
DEFAULT_STRATEGY_TYPE = "enhanced"


def compute_edge_score(result: WalkForwardResult) -> float | None:
    """Composite ranking score for the catalog.

    Combines mean Sharpe with statistical significance and out-of-sample
    consistency. Returns None when the sample is too small to be trusted.

    edge_score = mean_sharpe * significance_factor * consistency_factor

    Where:
    - significance_factor weights Wilcoxon p-value: 1.0 if p<0.05, 0.5 if
      0.05<=p<0.10, 0.2 otherwise. None p-value => 0.5 (neutral).
    - consistency_factor weights pct_folds_beat_bh: 0.5 + 0.5 * pct.
    """
    if result.total_trades < MIN_TRADES_FOR_RANKING:
        return None
    if result.num_folds < MIN_FOLDS_FOR_RANKING:
        return None

    p = result.wilcoxon_p_value
    if p is None:
        significance_factor = 0.5
    elif p < 0.05:
        significance_factor = 1.0
    elif p < 0.10:
        significance_factor = 0.5
    else:
        significance_factor = 0.2

    consistency_factor = 0.5 + 0.5 * result.pct_folds_beat_bh
    return result.mean_sharpe * significance_factor * consistency_factor


def _serialise_folds(result: WalkForwardResult) -> str:
    """JSON-serialise per-fold metrics for the folds_json column."""
    payload = []
    for fold in result.folds:
        d = dataclasses.asdict(fold)
        # Dates aren't JSON-serializable by default
        d["test_start"] = fold.test_start.isoformat()
        d["test_end"] = fold.test_end.isoformat()
        payload.append(d)
    return json.dumps(payload, default=str)


def _load_universe_symbols(conn: Any) -> list[str]:
    """Active research universe with at least one bar of OHLCV data."""
    rows = conn.execute(
        """
        SELECT u.symbol
        FROM research_universe_symbols u
        WHERE u.removed_at IS NULL
          AND EXISTS (SELECT 1 FROM day_bars d WHERE d.symbol = u.symbol)
        ORDER BY u.symbol
        """
    ).fetchall()
    return [str(row[0]) for row in rows]


def _resolve_history_window(conn: Any, symbol: str, years: int) -> tuple[dt.date, dt.date] | None:
    """Latest available OHLCV window, capped at *years*."""
    row = conn.execute(
        "SELECT MIN(date), MAX(date) FROM day_bars WHERE symbol = %s",
        (symbol,),
    ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return None
    earliest, latest = row[0], row[1]
    target_start = latest - dt.timedelta(days=int(years * 365.25))
    start = max(earliest, target_start)
    if (latest - start).days < TRADING_DAYS_PER_YEAR:
        return None  # Insufficient history for even one fold
    return start, latest


def _upsert_screening_row(
    conn: Any,
    *,
    symbol: str,
    strategy_type: str,
    run_date: dt.date,
    backtest_start: dt.date,
    backtest_end: dt.date,
    result: WalkForwardResult,
    edge_score: float | None,
) -> None:
    """UPSERT one screening result keyed on (symbol, strategy_type, run_date)."""
    conn.execute(
        """
        INSERT INTO strategy_screening_results (
            symbol, strategy_type, run_date,
            backtest_start_date, backtest_end_date,
            num_folds, total_trades,
            mean_sharpe, std_sharpe, mean_win_rate, max_drawdown_pct,
            mean_excess_vs_bh, pct_folds_beat_bh,
            wilcoxon_p_value, statistically_significant, significance_level,
            edge_score, folds_json
        ) VALUES (
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s::jsonb
        )
        ON CONFLICT (symbol, strategy_type, run_date) DO UPDATE SET
            backtest_start_date = EXCLUDED.backtest_start_date,
            backtest_end_date = EXCLUDED.backtest_end_date,
            num_folds = EXCLUDED.num_folds,
            total_trades = EXCLUDED.total_trades,
            mean_sharpe = EXCLUDED.mean_sharpe,
            std_sharpe = EXCLUDED.std_sharpe,
            mean_win_rate = EXCLUDED.mean_win_rate,
            max_drawdown_pct = EXCLUDED.max_drawdown_pct,
            mean_excess_vs_bh = EXCLUDED.mean_excess_vs_bh,
            pct_folds_beat_bh = EXCLUDED.pct_folds_beat_bh,
            wilcoxon_p_value = EXCLUDED.wilcoxon_p_value,
            statistically_significant = EXCLUDED.statistically_significant,
            significance_level = EXCLUDED.significance_level,
            edge_score = EXCLUDED.edge_score,
            folds_json = EXCLUDED.folds_json,
            created_at = NOW()
        """,
        (
            symbol,
            strategy_type,
            run_date,
            backtest_start,
            backtest_end,
            result.num_folds,
            result.total_trades,
            Decimal(str(round(result.mean_sharpe, 4))),
            Decimal(str(round(result.std_sharpe, 4))),
            Decimal(str(round(result.mean_win_rate, 4))),
            Decimal(str(round(result.max_drawdown_pct, 4))),
            Decimal(str(round(result.mean_excess_vs_bh, 4))),
            Decimal(str(round(result.pct_folds_beat_bh, 4))),
            Decimal(str(round(result.wilcoxon_p_value, 6))) if result.wilcoxon_p_value is not None else None,
            bool(result.statistically_significant),
            result.significance_level,
            Decimal(str(round(edge_score, 4))) if edge_score is not None else None,
            _serialise_folds(result),
        ),
    )


def screen_universe(
    *,
    symbols: list[str] | None = None,
    years: int = DEFAULT_BACKTEST_YEARS,
    strategy_type: str = DEFAULT_STRATEGY_TYPE,
    benchmark_symbol: str = "SPY",
    limit: int | None = None,
) -> dict[str, Any]:
    """Run the walk-forward sweep across the research universe.

    Args:
        symbols: Override the default universe (mainly for tests / one-shot
            screens of a small list).
        years: Backtest history window in years.
        strategy_type: WalkForwardEngine strategy_type ('enhanced' or
            'signal_classifier').
        benchmark_symbol: Symbol used for buy-and-hold comparison.
        limit: Cap symbols processed per call (None = all). Useful when
            partitioning across worker invocations.

    Returns:
        Summary dict with counts, errors, and the run_date used.
    """
    task_id = str(uuid.uuid4())
    started_at = dt.datetime.now(dt.UTC)
    run_date = started_at.date()
    logger.info("screen_universe_started", task_id=task_id, run_date=str(run_date))

    conn_mgr = get_connection_manager()
    engine = WalkForwardEngine()

    with conn_mgr.connection() as conn:
        target_symbols = symbols if symbols is not None else _load_universe_symbols(conn)
        if limit:
            target_symbols = target_symbols[:limit]

    processed = 0
    skipped_no_history = 0
    failed = 0
    errors: list[dict[str, str]] = []

    for symbol in target_symbols:
        with conn_mgr.connection() as conn:
            window = _resolve_history_window(conn, symbol, years)
            if window is None:
                skipped_no_history += 1
                continue
            start_date, end_date = window

            try:
                result = engine.run_walk_forward(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    strategy_type=strategy_type,
                    benchmark_symbol=benchmark_symbol,
                )
            except Exception as exc:  # individual symbol failure shouldn't kill the sweep
                failed += 1
                errors.append({"symbol": symbol, "error": str(exc)[:240]})
                logger.warning(
                    "screen_universe_symbol_failed",
                    task_id=task_id,
                    symbol=symbol,
                    error=str(exc),
                )
                continue

            edge_score = compute_edge_score(result)
            try:
                _upsert_screening_row(
                    conn,
                    symbol=symbol,
                    strategy_type=strategy_type,
                    run_date=run_date,
                    backtest_start=start_date,
                    backtest_end=end_date,
                    result=result,
                    edge_score=edge_score,
                )
                conn.commit()
                processed += 1
            except Exception as exc:
                failed += 1
                errors.append({"symbol": symbol, "error": f"persist: {exc}"[:240]})
                logger.exception(
                    "screen_universe_persist_failed",
                    task_id=task_id,
                    symbol=symbol,
                )

    duration = (dt.datetime.now(dt.UTC) - started_at).total_seconds()
    summary = {
        "task_id": task_id,
        "status": "completed",
        "run_date": run_date.isoformat(),
        "processed": processed,
        "skipped_no_history": skipped_no_history,
        "failed": failed,
        "duration_seconds": duration,
        "errors": errors[:25],
    }
    logger.info(
        "screen_universe_completed",
        task_id=task_id,
        processed=processed,
        skipped_no_history=skipped_no_history,
        failed=failed,
        duration_seconds=duration,
    )
    return summary
