"""Persistence layer for ``signal_macro_snapshots``."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime

from ..logging_config import get_logger
from ..storage.facade import get_storage
from .scoring import CompositeResult

logger = get_logger(__name__)


def upsert_snapshot(snapshot_date: date, result: CompositeResult) -> None:
    raw_payload = {
        "raw": asdict(result.raw),
        "scores": asdict(result.scores),
        "coverage": result.coverage,
        **result.metadata,
    }
    params = [
        snapshot_date,
        result.raw.vix_close,
        result.raw.term_spread_bps,
        result.raw.breadth_pct,
        result.raw.hy_spread,
        result.raw.put_call_ratio,
        result.raw.factor_crowding_corr,
        result.scores.vix,
        result.scores.term,
        result.scores.breadth,
        result.scores.credit,
        result.scores.putcall,
        result.scores.crowding,
        result.deployment_score,
        result.zone,
        json.dumps(raw_payload),
    ]
    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO signal_macro_snapshots (
                snapshot_date,
                vix_close, term_spread_bps, breadth_pct,
                hy_spread, put_call_ratio, factor_crowding_corr,
                vix_score, term_score, breadth_score,
                credit_score, putcall_score, crowding_score,
                deployment_score, zone, raw_json, computed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
            ON CONFLICT (snapshot_date) DO UPDATE SET
                vix_close = EXCLUDED.vix_close,
                term_spread_bps = EXCLUDED.term_spread_bps,
                breadth_pct = EXCLUDED.breadth_pct,
                hy_spread = EXCLUDED.hy_spread,
                put_call_ratio = EXCLUDED.put_call_ratio,
                factor_crowding_corr = EXCLUDED.factor_crowding_corr,
                vix_score = EXCLUDED.vix_score,
                term_score = EXCLUDED.term_score,
                breadth_score = EXCLUDED.breadth_score,
                credit_score = EXCLUDED.credit_score,
                putcall_score = EXCLUDED.putcall_score,
                crowding_score = EXCLUDED.crowding_score,
                deployment_score = EXCLUDED.deployment_score,
                zone = EXCLUDED.zone,
                raw_json = EXCLUDED.raw_json,
                computed_at = now()
            """,
            params,
        )
        conn.commit()


def get_latest() -> dict | None:
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT snapshot_date, vix_close, term_spread_bps, breadth_pct,
                   hy_spread, put_call_ratio, factor_crowding_corr,
                   vix_score, term_score, breadth_score,
                   credit_score, putcall_score, crowding_score,
                   deployment_score, zone, raw_json, computed_at
            FROM signal_macro_snapshots
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def get_history(days: int = 730) -> list[dict]:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT snapshot_date, vix_close, term_spread_bps, breadth_pct,
                   hy_spread, put_call_ratio, factor_crowding_corr,
                   vix_score, term_score, breadth_score,
                   credit_score, putcall_score, crowding_score,
                   deployment_score, zone, raw_json, computed_at
            FROM signal_macro_snapshots
            WHERE snapshot_date >= CURRENT_DATE - INTERVAL '{int(days)} days'
            ORDER BY snapshot_date ASC
            """,
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_last_known_good_score(before: date) -> float | None:
    """Deployment score of the most recent non-degraded snapshot before ``before``.

    Used to clamp a degraded (stale-input) reading so it can never report a
    greener / more risk-on score than the last fully-trusted gate.
    """
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT deployment_score
            FROM signal_macro_snapshots
            WHERE snapshot_date < %s
              AND deployment_score IS NOT NULL
              AND (raw_json->>'degraded') IS DISTINCT FROM 'true'
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            [before],
        ).fetchone()
    if row is None or row[0] is None:
        return None
    return float(row[0])


def get_latest_crowding() -> dict | None:
    """Return the latest persisted crowding raw value and as-of date."""
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT snapshot_date, factor_crowding_corr, crowding_score, raw_json, computed_at
            FROM signal_macro_snapshots
            WHERE factor_crowding_corr IS NOT NULL
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
        ).fetchone()
    if row is None:
        return None

    raw_json = row[3] if isinstance(row[3], dict) else {}
    quality = raw_json.get("component_quality", {}) if isinstance(raw_json, dict) else {}
    crowding_quality = quality.get("crowding", {}) if isinstance(quality, dict) else {}
    as_of = crowding_quality.get("as_of") if isinstance(crowding_quality, dict) else None
    if as_of is None:
        as_of = row[0].isoformat() if isinstance(row[0], date) else row[0]

    return {
        "snapshot_date": row[0].isoformat() if isinstance(row[0], date) else row[0],
        "factor_crowding_corr": _maybe_float(row[1]),
        "crowding_score": _maybe_float(row[2]),
        "as_of": as_of,
        "computed_at": row[4].isoformat() if isinstance(row[4], datetime) else row[4],
    }


def _row_to_dict(row: tuple) -> dict:
    return {
        "snapshot_date": row[0].isoformat() if isinstance(row[0], date) else row[0],
        "vix_close": _maybe_float(row[1]),
        "term_spread_bps": _maybe_float(row[2]),
        "breadth_pct": _maybe_float(row[3]),
        "hy_spread": _maybe_float(row[4]),
        "put_call_ratio": _maybe_float(row[5]),
        "factor_crowding_corr": _maybe_float(row[6]),
        "vix_score": _maybe_float(row[7]),
        "term_score": _maybe_float(row[8]),
        "breadth_score": _maybe_float(row[9]),
        "credit_score": _maybe_float(row[10]),
        "putcall_score": _maybe_float(row[11]),
        "crowding_score": _maybe_float(row[12]),
        "deployment_score": _maybe_float(row[13]),
        "zone": row[14],
        "raw_json": row[15],
        "computed_at": row[16].isoformat() if isinstance(row[16], datetime) else row[16],
    }


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
