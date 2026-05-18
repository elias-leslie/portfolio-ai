"""Persistence layer for ``signal_scanner_runs`` + ``signal_scanner_scores``."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from ..logging_config import get_logger
from ..storage.facade import get_storage

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ScoreRow:
    symbol: str
    factors: dict[str, float | None]      # raw values, keyed by FACTOR_NAMES
    percentiles: dict[str, float | None]  # 0-100, keyed by FACTOR_NAMES
    composite_pct: float
    rank: int
    factor_coverage: float                # 0.0-1.0, share of factors present


def create_run(
    *,
    run_date: date,
    gate_zone: str,
    gate_score: float | None,
    universe_size: int,
    skip_reason: str | None = None,
) -> UUID:
    """Insert the scanner-run header. ``completed_at`` is filled later."""
    run_id = uuid4()
    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO signal_scanner_runs (
                run_id, run_date, gate_zone, gate_score,
                universe_size, scored_count, skip_reason
            )
            VALUES (%s, %s, %s, %s, %s, 0, %s)
            """,
            [run_id, run_date, gate_zone, gate_score, universe_size, skip_reason],
        )
        conn.commit()
    return run_id


def finalize_run(run_id: UUID, scored_count: int) -> None:
    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE signal_scanner_runs
            SET scored_count = %s,
                completed_at = now()
            WHERE run_id = %s
            """,
            [scored_count, run_id],
        )
        conn.commit()


def insert_scores(run_id: UUID, scores: Iterable[ScoreRow]) -> int:
    """Bulk-insert per-symbol scores for one run."""
    rows = list(scores)
    if not rows:
        return 0
    storage = get_storage()
    inserted = 0
    with storage.connection() as conn:
        for r in rows:
            conn.execute(
                """
                INSERT INTO signal_scanner_scores (
                    run_id, symbol,
                    mom_xover, vol_surge, rs_vs_spy,
                    high_52w_proximity, short_interest_decline,
                    mom_xover_pct, vol_surge_pct, rs_vs_spy_pct,
                    high_52w_proximity_pct, short_interest_decline_pct,
                    composite_pct, rank, factor_coverage
                )
                VALUES (%s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s)
                """,
                [
                    run_id, r.symbol,
                    r.factors.get("mom_xover"),
                    r.factors.get("vol_surge"),
                    r.factors.get("rs_vs_spy"),
                    r.factors.get("high_52w_proximity"),
                    r.factors.get("short_interest_decline"),
                    r.percentiles.get("mom_xover"),
                    r.percentiles.get("vol_surge"),
                    r.percentiles.get("rs_vs_spy"),
                    r.percentiles.get("high_52w_proximity"),
                    r.percentiles.get("short_interest_decline"),
                    r.composite_pct,
                    r.rank,
                    r.factor_coverage,
                ],
            )
            inserted += 1
        conn.commit()
    return inserted


def get_latest_run() -> dict[str, Any] | None:
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT run_id, run_date, gate_zone, gate_score,
                   universe_size, scored_count, skip_reason,
                   started_at, completed_at
            FROM signal_scanner_runs
            ORDER BY run_date DESC, started_at DESC
            LIMIT 1
            """,
        ).fetchone()
    return _run_row_to_dict(row) if row else None


def get_scores_for_run(run_id: UUID, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT symbol,
               mom_xover, vol_surge, rs_vs_spy,
               high_52w_proximity, short_interest_decline,
               mom_xover_pct, vol_surge_pct, rs_vs_spy_pct,
               high_52w_proximity_pct, short_interest_decline_pct,
               composite_pct, rank, factor_coverage
        FROM signal_scanner_scores
        WHERE run_id = %s
        ORDER BY rank ASC
    """
    params: list[Any] = [run_id]
    if limit is not None:
        sql += " LIMIT %s"
        params.append(int(limit))
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_score_row_to_dict(r) for r in rows]


def get_run_history(days: int = 60) -> list[dict[str, Any]]:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT run_id, run_date, gate_zone, gate_score,
                   universe_size, scored_count, skip_reason,
                   started_at, completed_at
            FROM signal_scanner_runs
            WHERE run_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
            ORDER BY run_date DESC, started_at DESC
            """,
        ).fetchall()
    return [_run_row_to_dict(r) for r in rows]


def get_history_for_symbol(symbol: str, days: int = 90) -> list[dict[str, Any]]:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT r.run_date,
                   r.gate_zone,
                   s.composite_pct,
                   s.rank,
                   s.factor_coverage,
                   s.mom_xover_pct, s.vol_surge_pct, s.rs_vs_spy_pct,
                   s.high_52w_proximity_pct, s.short_interest_decline_pct
            FROM signal_scanner_scores s
            JOIN signal_scanner_runs r USING (run_id)
            WHERE s.symbol = %s
              AND r.run_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
            ORDER BY r.run_date DESC
            """,
            [symbol],
        ).fetchall()
    return [
        {
            "run_date": row[0].isoformat() if isinstance(row[0], date) else row[0],
            "gate_zone": row[1],
            "composite_pct": _maybe_float(row[2]),
            "rank": row[3],
            "factor_coverage": _maybe_float(row[4]),
            "mom_xover_pct": _maybe_float(row[5]),
            "vol_surge_pct": _maybe_float(row[6]),
            "rs_vs_spy_pct": _maybe_float(row[7]),
            "high_52w_proximity_pct": _maybe_float(row[8]),
            "short_interest_decline_pct": _maybe_float(row[9]),
        }
        for row in rows
    ]


def _run_row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "run_id": str(row[0]),
        "run_date": row[1].isoformat() if isinstance(row[1], date) else row[1],
        "gate_zone": row[2],
        "gate_score": _maybe_float(row[3]),
        "universe_size": int(row[4]),
        "scored_count": int(row[5]),
        "skip_reason": row[6],
        "started_at": row[7].isoformat() if isinstance(row[7], datetime) else row[7],
        "completed_at": row[8].isoformat() if isinstance(row[8], datetime) else row[8],
    }


def _score_row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "symbol": row[0],
        "mom_xover": _maybe_float(row[1]),
        "vol_surge": _maybe_float(row[2]),
        "rs_vs_spy": _maybe_float(row[3]),
        "high_52w_proximity": _maybe_float(row[4]),
        "short_interest_decline": _maybe_float(row[5]),
        "mom_xover_pct": _maybe_float(row[6]),
        "vol_surge_pct": _maybe_float(row[7]),
        "rs_vs_spy_pct": _maybe_float(row[8]),
        "high_52w_proximity_pct": _maybe_float(row[9]),
        "short_interest_decline_pct": _maybe_float(row[10]),
        "composite_pct": _maybe_float(row[11]),
        "rank": int(row[12]),
        "factor_coverage": _maybe_float(row[13]),
    }


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
