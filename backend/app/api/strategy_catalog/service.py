"""Strategy catalog service.

Reads ranked screening results and manages user-followed strategies. Following
a screening result creates a strategy_definitions row marked active so the
existing daily_signals_wf picks it up; unfollowing archives it.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.benchmark_service import get_benchmark_comparisons

from .labels import (
    beat_count,
    benchmark_verdict,
    risk_tier_from_drawdown,
    verdict_for_strategy,
)
from .models import (
    BenchmarkComparison,
    CatalogDetail,
    CatalogDetailResponse,
    CatalogItem,
    CatalogResponse,
    FollowResponse,
)

logger = get_logger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
FOLLOW_NAME_PREFIX = "Universe Follow"


def _row_to_item(row: Any, followed_set: set[str]) -> CatalogItem:
    edge = float(row[3]) if row[3] is not None else None
    pct_beat = float(row[8]) if row[8] is not None else None
    sig = bool(row[10])
    max_dd = float(row[6]) if row[6] is not None else None
    return CatalogItem(
        symbol=str(row[0]),
        strategy_type=str(row[1]),
        run_date=row[2],
        edge_score=edge,
        mean_sharpe=float(row[4]) if row[4] is not None else None,
        mean_win_rate=float(row[5]) if row[5] is not None else None,
        max_drawdown_pct=max_dd,
        mean_excess_vs_bh=float(row[7]) if row[7] is not None else None,
        pct_folds_beat_bh=pct_beat,
        wilcoxon_p_value=float(row[9]) if row[9] is not None else None,
        statistically_significant=sig,
        significance_level=str(row[11]) if row[11] is not None else None,
        num_folds=int(row[12]),
        total_trades=int(row[13]),
        backtest_start_date=row[14],
        backtest_end_date=row[15],
        is_followed=str(row[0]) in followed_set,
        risk_tier=risk_tier_from_drawdown(max_dd),
        verdict=verdict_for_strategy(edge, pct_beat, sig),
    )


def _load_followed_symbols(conn: Any) -> set[str]:
    """Symbols with an active strategy_definitions row whose name marks it as
    a catalog follow."""
    rows = conn.execute(
        """
        SELECT DISTINCT symbol
        FROM strategy_definitions
        WHERE status = 'active'
          AND name LIKE %s
        """,
        (f"{FOLLOW_NAME_PREFIX}%",),
    ).fetchall()
    return {str(row[0]) for row in rows}


def list_catalog(
    *,
    limit: int = DEFAULT_LIMIT,
    only_significant: bool = False,
    min_total_trades: int = 0,
) -> CatalogResponse:
    """Return the top-N screened strategies for the latest run.

    Args:
        limit: Max items to return (capped at MAX_LIMIT).
        only_significant: When True, filter to statistically significant rows.
        min_total_trades: Drop rows below this trade count threshold.
    """
    capped = max(1, min(limit, MAX_LIMIT))
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        latest_row = conn.execute(
            "SELECT MAX(run_date) FROM strategy_screening_results"
        ).fetchone()
        latest_run = latest_row[0] if latest_row else None
        if latest_run is None:
            return CatalogResponse(items=[], total_count=0, latest_run_date=None)

        followed = _load_followed_symbols(conn)

        filters = ["run_date = %s", "edge_score IS NOT NULL"]
        params: list[Any] = [latest_run]
        if only_significant:
            filters.append("statistically_significant = TRUE")
        if min_total_trades > 0:
            filters.append("total_trades >= %s")
            params.append(min_total_trades)
        where_clause = " AND ".join(filters)

        count_row = conn.execute(
            f"SELECT COUNT(*) FROM strategy_screening_results WHERE {where_clause}",
            tuple(params),
        ).fetchone()
        total_count = int(count_row[0]) if count_row else 0

        rows = conn.execute(
            f"""
            SELECT symbol, strategy_type, run_date,
                   edge_score, mean_sharpe, mean_win_rate, max_drawdown_pct,
                   mean_excess_vs_bh, pct_folds_beat_bh, wilcoxon_p_value,
                   statistically_significant, significance_level,
                   num_folds, total_trades,
                   backtest_start_date, backtest_end_date
            FROM strategy_screening_results
            WHERE {where_clause}
            ORDER BY edge_score DESC NULLS LAST, mean_sharpe DESC NULLS LAST
            LIMIT %s
            """,
            (*tuple(params), capped),
        ).fetchall()

    items = [_row_to_item(row, followed) for row in rows]
    return CatalogResponse(
        items=items,
        total_count=total_count,
        latest_run_date=latest_run,
    )


def _load_latest_screening(conn: Any, symbol: str) -> Any:
    return conn.execute(
        """
        SELECT symbol, strategy_type, run_date, mean_sharpe, mean_win_rate,
               max_drawdown_pct, folds_json, edge_score
        FROM strategy_screening_results
        WHERE symbol = %s
        ORDER BY run_date DESC
        LIMIT 1
        """,
        (symbol.upper(),),
    ).fetchone()


def follow_symbol(symbol: str) -> FollowResponse:
    """Promote a screened symbol to an active strategy_definitions row.

    The active row plugs into the existing daily_signals_wf. If the user has
    already followed this symbol, this is a no-op that returns the existing
    strategy ID.
    """
    sym = symbol.upper()
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM strategy_definitions
            WHERE symbol = %s
              AND status = 'active'
              AND name LIKE %s
            LIMIT 1
            """,
            (sym, f"{FOLLOW_NAME_PREFIX}%"),
        ).fetchone()
        if existing:
            return FollowResponse(symbol=sym, is_followed=True, strategy_id=str(existing[0]))

        screening = _load_latest_screening(conn, sym)
        if screening is None:
            raise HTTPException(
                status_code=404,
                detail=f"No screening result available for {sym}. Run the universe screen first.",
            )

        strategy_id = str(uuid.uuid4())
        name = f"{FOLLOW_NAME_PREFIX} {sym}"
        now = datetime.now(UTC)
        mean_sharpe = screening[3]
        mean_win_rate = screening[4]
        max_dd = screening[5]
        folds_json = screening[6] or []
        # Trim per-fold metrics to a flat list shaped like backtest_metrics
        backtest_metrics: list[dict[str, Any]] = []
        if isinstance(folds_json, list):
            for fold in folds_json:
                if not isinstance(fold, dict):
                    continue
                backtest_metrics.append(
                    {
                        "fold_number": fold.get("fold_number"),
                        "sharpe_ratio": fold.get("sharpe_ratio"),
                        "win_rate": fold.get("win_rate"),
                        "max_drawdown": fold.get("max_drawdown_pct"),
                        "num_trades": fold.get("num_trades"),
                        "total_return": fold.get("total_return_pct"),
                        "test_start": fold.get("test_start"),
                        "test_end": fold.get("test_end"),
                    }
                )

        conn.execute(
            """
            INSERT INTO strategy_definitions (
                id, name, symbol, strategy_type,
                parameters, research_summary, generation_reasoning,
                backtest_metrics, expected_sharpe, expected_win_rate, expected_max_drawdown,
                created_by, created_at, version,
                status, activation_date
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            """,
            (
                strategy_id,
                name,
                sym,
                "enhanced",
                json.dumps({}),
                json.dumps({"source": "universe_screen"}),
                "Followed from universe screen catalog.",
                json.dumps(backtest_metrics),
                Decimal(str(mean_sharpe)) if mean_sharpe is not None else None,
                Decimal(str(mean_win_rate)) if mean_win_rate is not None else None,
                Decimal(str(max_dd)) if max_dd is not None else None,
                "catalog_follow",
                now,
                1,
                "active",
                now,
            ),
        )
        conn.commit()

    logger.info("catalog_follow", symbol=sym, strategy_id=strategy_id)
    return FollowResponse(symbol=sym, is_followed=True, strategy_id=strategy_id)


def get_catalog_detail(symbol: str) -> CatalogDetailResponse:
    """Single-symbol detail with full benchmark grid attached."""
    sym = symbol.upper()
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        followed = _load_followed_symbols(conn)
        row = conn.execute(
            """
            SELECT symbol, strategy_type, run_date,
                   edge_score, mean_sharpe, mean_win_rate, max_drawdown_pct,
                   mean_excess_vs_bh, pct_folds_beat_bh, wilcoxon_p_value,
                   statistically_significant, significance_level,
                   num_folds, total_trades,
                   backtest_start_date, backtest_end_date
            FROM strategy_screening_results
            WHERE symbol = %s
            ORDER BY run_date DESC
            LIMIT 1
            """,
            (sym,),
        ).fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No screening result available for {sym}.",
        )

    base_item = _row_to_item(row, followed)
    raw_benchmarks = get_benchmark_comparisons(sym, base_item.run_date)
    benchmarks = [
        BenchmarkComparison(
            benchmark_key=str(b["benchmark_key"]),
            label=str(b["label"]),
            description=str(b["description"]),
            kind=str(b["kind"]),
            risk_tier=str(b["risk_tier"]),
            benchmark_return_pct=b.get("benchmark_return_pct"),
            excess_return_pct=b.get("excess_return_pct"),
            max_drawdown_pct=b.get("max_drawdown_pct"),
            volatility_pct=b.get("volatility_pct"),
            beats_benchmark=bool(b.get("beats_benchmark", False)),
            verdict=benchmark_verdict(b.get("excess_return_pct")),
        )
        for b in raw_benchmarks
    ]
    beats, total = beat_count(raw_benchmarks)

    detail = CatalogDetail(
        **base_item.model_dump(),
        benchmarks=benchmarks,
    )
    detail.benchmarks_beat_count = beats
    detail.benchmarks_total_count = total
    return CatalogDetailResponse(item=detail)


def unfollow_symbol(symbol: str) -> FollowResponse:
    """Archive any active catalog-follow strategy for this symbol."""
    sym = symbol.upper()
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        rows = conn.execute(
            """
            UPDATE strategy_definitions
            SET status = 'archived',
                archive_date = NOW(),
                archive_reason = 'Unfollowed from catalog'
            WHERE symbol = %s
              AND status = 'active'
              AND name LIKE %s
            RETURNING id
            """,
            (sym, f"{FOLLOW_NAME_PREFIX}%"),
        ).fetchall()
        conn.commit()

    logger.info("catalog_unfollow", symbol=sym, archived=len(rows))
    return FollowResponse(symbol=sym, is_followed=False, strategy_id=None)
