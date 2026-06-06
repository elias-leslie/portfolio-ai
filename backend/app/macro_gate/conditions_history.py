"""Append-only log of the Today headline numbers (``macro_conditions_history``).

``signal_macro_snapshots`` stores only the macro composite. The headline the
user reacts to — ``overall_caution = max(macro_stress, tape_pressure)`` — was
recomputed per request and discarded. This module logs it over time so the
single headline trend line can show what the number was and *when* it changed.

Writes are change-detected: a row is inserted only when a headline value (or the
trading day, or tape availability) differs from the last logged row. Flat
periods add nothing, so the table stays a clean step-change log and a read
endpoint can't bloat it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..logging_config import get_logger
from ..storage.facade import get_storage

logger = get_logger(__name__)


def _iso(value: object) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

# Headline fields whose change triggers a new logged row.
_TRACKED_KEYS = (
    "overall_caution",
    "tape_pressure",
    "macro_stress",
    "overall_read",
    "tape_available",
)


def _latest_row() -> dict[str, Any] | None:
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT snapshot_date, macro_stress, tape_pressure, overall_caution,
                   overall_read, tape_available
            FROM macro_conditions_history
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
        ).fetchone()
    if row is None:
        return None
    return {
        "snapshot_date": _iso(row[0]),
        "macro_stress": row[1],
        "tape_pressure": row[2],
        "overall_caution": row[3],
        "overall_read": row[4],
        "tape_available": row[5],
    }


def _headline_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_date": payload.get("snapshot_date"),
        "deployment_score": payload.get("deployment_score"),
        "macro_stress": payload.get("macro_stress_score"),
        "tape_pressure": payload.get("tape_pressure_score"),
        "overall_caution": payload.get("overall_caution_score"),
        "overall_read": payload.get("overall_read"),
        "primary_driver": payload.get("primary_driver"),
        "state": payload.get("state"),
        "tape_available": bool(payload.get("tape_available", False)),
        "market_session": payload.get("market_session"),
    }


def _changed(previous: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    if previous is None:
        return True
    if previous.get("snapshot_date") != current.get("snapshot_date"):
        return True
    return any(previous.get(key) != current.get(key) for key in _TRACKED_KEYS)


def record(payload: dict[str, Any]) -> None:
    """Log the headline numbers if they changed since the last row.

    Best-effort: a logging failure must never break the Today read, so callers
    run this in a threadpool and we swallow/announce errors here.
    """
    current = _headline_from_payload(payload)
    if current["overall_caution"] is None and current["macro_stress"] is None:
        return
    try:
        previous = _latest_row()
        if not _changed(previous, current):
            return
        storage = get_storage()
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO macro_conditions_history (
                    snapshot_date, deployment_score, macro_stress, tape_pressure,
                    overall_caution, overall_read, primary_driver, state,
                    tape_available, market_session
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    current["snapshot_date"],
                    current["deployment_score"],
                    current["macro_stress"],
                    current["tape_pressure"],
                    current["overall_caution"],
                    current["overall_read"],
                    current["primary_driver"],
                    current["state"],
                    current["tape_available"],
                    current["market_session"],
                ],
            )
            conn.commit()
    except Exception as exc:
        # Logging must never break the Today read.
        logger.warning("macro_conditions_history_log_failed", error=str(exc))


def get_history(days: int = 90) -> list[dict[str, Any]]:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            f"""
            SELECT recorded_at, snapshot_date, deployment_score, macro_stress,
                   tape_pressure, overall_caution, overall_read, primary_driver,
                   state, tape_available, market_session
            FROM macro_conditions_history
            WHERE recorded_at >= now() - INTERVAL '{int(days)} days'
            ORDER BY recorded_at ASC
            """,
        ).fetchall()
    return [
        {
            "recorded_at": _iso(row[0]),
            "snapshot_date": _iso(row[1]),
            "deployment_score": None if row[2] is None else float(row[2]),
            "macro_stress": None if row[3] is None else int(row[3]),
            "tape_pressure": None if row[4] is None else int(row[4]),
            "overall_caution": None if row[5] is None else int(row[5]),
            "overall_read": row[6],
            "primary_driver": row[7],
            "state": row[8],
            "tape_available": bool(row[9]),
            "market_session": row[10],
        }
        for row in rows
    ]
