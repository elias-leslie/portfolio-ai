"""Compute and cache buy-and-hold benchmark comparisons.

Lazy: comparisons populate on first catalog request for a (symbol,
screen_run_date) pair, then stay cached in benchmark_comparisons until
the next screen run produces a new run_date. Adding a new benchmark to
``BENCHMARKS`` does NOT require a backfill; the next access for any
symbol fills it in.
"""

from __future__ import annotations

import datetime as dt
import statistics
from decimal import Decimal
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

from .benchmarks import (
    BENCHMARKS,
    BENCHMARKS_BY_KEY,
    BenchmarkDefinition,
    required_symbols,
)

logger = get_logger(__name__)


def _fetch_daily_closes(
    conn: Any,
    symbol: str,
    start: dt.date,
    end: dt.date,
) -> list[tuple[dt.date, float]]:
    """Daily close prices for *symbol* between [start, end] inclusive."""
    rows = conn.execute(
        """
        SELECT date, close
        FROM day_bars
        WHERE symbol = %s AND date >= %s AND date <= %s
        ORDER BY date
        """,
        (symbol, start, end),
    ).fetchall()
    return [(row[0], float(row[1])) for row in rows if row[1] is not None]


def _compute_curve_metrics(daily_returns: list[float]) -> dict[str, float]:
    """Total return, max drawdown, annualized volatility from daily returns."""
    if not daily_returns:
        return {"total_return_pct": 0.0, "max_drawdown_pct": 0.0, "volatility_pct": 0.0}

    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in daily_returns:
        cumulative *= 1.0 + r
        peak = max(peak, cumulative)
        if peak > 0:
            dd = (peak - cumulative) / peak
            max_dd = max(max_dd, dd)
    total_return_pct = (cumulative - 1.0) * 100.0

    if len(daily_returns) > 1:
        vol_pct = statistics.stdev(daily_returns) * (252**0.5) * 100.0
    else:
        vol_pct = 0.0

    return {
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd,
        "volatility_pct": vol_pct,
    }


def _compute_ticker_returns(
    conn: Any,
    symbol: str,
    start: dt.date,
    end: dt.date,
) -> dict[str, float] | None:
    closes = _fetch_daily_closes(conn, symbol, start, end)
    if len(closes) < 2:
        return None
    daily_returns: list[float] = []
    prev = closes[0][1]
    for _, close in closes[1:]:
        if prev > 0:
            daily_returns.append((close - prev) / prev)
        prev = close
    return _compute_curve_metrics(daily_returns)


def _compute_basket_returns(
    conn: Any,
    symbols: list[str],
    start: dt.date,
    end: dt.date,
) -> dict[str, float] | None:
    """Equal-weight basket: average daily returns across constituents."""
    per_symbol_returns: dict[str, dict[dt.date, float]] = {}
    for sym in symbols:
        closes = _fetch_daily_closes(conn, sym, start, end)
        if len(closes) < 2:
            continue
        ret_by_date: dict[dt.date, float] = {}
        prev = closes[0][1]
        for date_, close in closes[1:]:
            if prev > 0:
                ret_by_date[date_] = (close - prev) / prev
            prev = close
        per_symbol_returns[sym] = ret_by_date

    if not per_symbol_returns:
        return None

    all_dates = sorted({d for series in per_symbol_returns.values() for d in series})
    daily_returns: list[float] = []
    for d in all_dates:
        same_day = [series[d] for series in per_symbol_returns.values() if d in series]
        if same_day:
            daily_returns.append(sum(same_day) / len(same_day))
    return _compute_curve_metrics(daily_returns)


def _compute_weighted_returns(
    conn: Any,
    weights: dict[str, float],
    start: dt.date,
    end: dt.date,
) -> dict[str, float] | None:
    """Weighted basket: weighted average of constituents' daily returns."""
    per_symbol_returns: dict[str, dict[dt.date, float]] = {}
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        return None

    for sym, weight in weights.items():
        if weight <= 0:
            continue
        closes = _fetch_daily_closes(conn, sym, start, end)
        if len(closes) < 2:
            continue
        ret_by_date: dict[dt.date, float] = {}
        prev = closes[0][1]
        for date_, close in closes[1:]:
            if prev > 0:
                ret_by_date[date_] = (close - prev) / prev
            prev = close
        per_symbol_returns[sym] = ret_by_date

    if not per_symbol_returns:
        return None

    all_dates = sorted({d for series in per_symbol_returns.values() for d in series})
    daily_returns: list[float] = []
    for d in all_dates:
        weighted = 0.0
        weight_for_day = 0.0
        for sym, series in per_symbol_returns.items():
            if d in series:
                weighted += series[d] * weights[sym]
                weight_for_day += weights[sym]
        if weight_for_day > 0:
            daily_returns.append(weighted / weight_for_day)
    return _compute_curve_metrics(daily_returns)


def _compute_benchmark_metrics(
    conn: Any,
    benchmark: BenchmarkDefinition,
    start: dt.date,
    end: dt.date,
) -> dict[str, float] | None:
    if benchmark.kind == "ticker":
        symbol = str(benchmark.definition.get("symbol", ""))
        if not symbol:
            return None
        return _compute_ticker_returns(conn, symbol, start, end)
    if benchmark.kind == "basket":
        symbols = required_symbols(benchmark)
        return _compute_basket_returns(conn, symbols, start, end)
    if benchmark.kind == "weighted":
        weights_raw = benchmark.definition.get("weights", {})
        if not isinstance(weights_raw, dict):
            return None
        weights = {str(k): float(v) for k, v in weights_raw.items()}
        return _compute_weighted_returns(conn, weights, start, end)
    return None


def _load_screening_window(
    conn: Any,
    symbol: str,
    run_date: dt.date,
) -> tuple[dt.date, dt.date, float | None] | None:
    """Backtest window + strategy total return for a screening row."""
    row = conn.execute(
        """
        SELECT backtest_start_date, backtest_end_date, folds_json
        FROM strategy_screening_results
        WHERE symbol = %s AND run_date = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (symbol, run_date),
    ).fetchone()
    if not row or not row[0] or not row[1]:
        return None
    start, end, folds_json = row[0], row[1], row[2]
    strategy_total_return: float | None = None
    if isinstance(folds_json, list) and folds_json:
        try:
            returns = [float(f.get("total_return_pct", 0.0)) for f in folds_json if isinstance(f, dict)]
            if returns:
                strategy_total_return = sum(returns) / len(returns)
        except (TypeError, ValueError):
            strategy_total_return = None
    return start, end, strategy_total_return


def _persist_comparison(
    conn: Any,
    *,
    symbol: str,
    benchmark_key: str,
    run_date: dt.date,
    start: dt.date,
    end: dt.date,
    strategy_return_pct: float | None,
    benchmark_metrics: dict[str, float] | None,
) -> dict[str, Any]:
    if benchmark_metrics is None:
        # Insert a row anyway so we don't recompute on every read for symbols
        # with insufficient data.
        conn.execute(
            """
            INSERT INTO benchmark_comparisons (
                symbol, benchmark_key, screen_run_date,
                backtest_start_date, backtest_end_date,
                strategy_return_pct, benchmark_return_pct, excess_return_pct,
                benchmark_max_drawdown_pct, benchmark_volatility_pct,
                beats_benchmark
            ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, FALSE)
            ON CONFLICT (symbol, benchmark_key, screen_run_date) DO NOTHING
            """,
            (
                symbol,
                benchmark_key,
                run_date,
                start,
                end,
                Decimal(str(strategy_return_pct)) if strategy_return_pct is not None else None,
            ),
        )
        return {
            "benchmark_key": benchmark_key,
            "benchmark_return_pct": None,
            "excess_return_pct": None,
            "max_drawdown_pct": None,
            "volatility_pct": None,
            "beats_benchmark": False,
        }

    bench_return = benchmark_metrics["total_return_pct"]
    excess = (
        strategy_return_pct - bench_return if strategy_return_pct is not None else None
    )
    beats = excess is not None and excess > 0

    conn.execute(
        """
        INSERT INTO benchmark_comparisons (
            symbol, benchmark_key, screen_run_date,
            backtest_start_date, backtest_end_date,
            strategy_return_pct, benchmark_return_pct, excess_return_pct,
            benchmark_max_drawdown_pct, benchmark_volatility_pct,
            beats_benchmark
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s
        )
        ON CONFLICT (symbol, benchmark_key, screen_run_date) DO UPDATE SET
            strategy_return_pct = EXCLUDED.strategy_return_pct,
            benchmark_return_pct = EXCLUDED.benchmark_return_pct,
            excess_return_pct = EXCLUDED.excess_return_pct,
            benchmark_max_drawdown_pct = EXCLUDED.benchmark_max_drawdown_pct,
            benchmark_volatility_pct = EXCLUDED.benchmark_volatility_pct,
            beats_benchmark = EXCLUDED.beats_benchmark,
            computed_at = NOW()
        """,
        (
            symbol,
            benchmark_key,
            run_date,
            start,
            end,
            Decimal(str(strategy_return_pct)) if strategy_return_pct is not None else None,
            Decimal(str(round(bench_return, 4))),
            Decimal(str(round(excess, 4))) if excess is not None else None,
            Decimal(str(round(benchmark_metrics["max_drawdown_pct"], 4))),
            Decimal(str(round(benchmark_metrics["volatility_pct"], 4))),
            beats,
        ),
    )
    return {
        "benchmark_key": benchmark_key,
        "benchmark_return_pct": bench_return,
        "excess_return_pct": excess,
        "max_drawdown_pct": benchmark_metrics["max_drawdown_pct"],
        "volatility_pct": benchmark_metrics["volatility_pct"],
        "beats_benchmark": beats,
    }


def get_benchmark_comparisons(symbol: str, run_date: dt.date) -> list[dict[str, Any]]:
    """Return benchmark comparisons for a screening row, computing any
    missing entries on the fly and caching them."""
    sym = symbol.upper()
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        window = _load_screening_window(conn, sym, run_date)
        if window is None:
            return []
        start, end, strategy_return = window

        cached_rows = conn.execute(
            """
            SELECT benchmark_key, benchmark_return_pct, excess_return_pct,
                   benchmark_max_drawdown_pct, benchmark_volatility_pct, beats_benchmark
            FROM benchmark_comparisons
            WHERE symbol = %s AND screen_run_date = %s
            """,
            (sym, run_date),
        ).fetchall()
        cached: dict[str, dict[str, Any]] = {}
        for row in cached_rows:
            cached[str(row[0])] = {
                "benchmark_key": str(row[0]),
                "benchmark_return_pct": float(row[1]) if row[1] is not None else None,
                "excess_return_pct": float(row[2]) if row[2] is not None else None,
                "max_drawdown_pct": float(row[3]) if row[3] is not None else None,
                "volatility_pct": float(row[4]) if row[4] is not None else None,
                "beats_benchmark": bool(row[5]),
            }

        results: list[dict[str, Any]] = []
        for benchmark in BENCHMARKS:
            if benchmark.key in cached:
                results.append(cached[benchmark.key])
                continue
            metrics = _compute_benchmark_metrics(conn, benchmark, start, end)
            persisted = _persist_comparison(
                conn,
                symbol=sym,
                benchmark_key=benchmark.key,
                run_date=run_date,
                start=start,
                end=end,
                strategy_return_pct=strategy_return,
                benchmark_metrics=metrics,
            )
            results.append(persisted)

        conn.commit()

    # Decorate with definition metadata so the API caller doesn't need to
    # re-look-up labels and risk tiers.
    decorated: list[dict[str, Any]] = []
    for entry in results:
        defn = BENCHMARKS_BY_KEY.get(entry["benchmark_key"])
        if defn is None:
            continue
        decorated.append({
            **entry,
            "label": defn.label,
            "description": defn.description,
            "risk_tier": defn.risk_tier,
            "kind": defn.kind,
        })
    return decorated
