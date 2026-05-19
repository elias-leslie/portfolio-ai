"""On-demand fundamentals fetch for L3 scanner candidates.

The L2 scanner ranks ~500 S&P 500 symbols on daily quant factors and
hands a Tier-1 shortlist (default 8) to the committee. The original
3-tier spec calls for each shortlisted symbol's last four quarters of
financials to be pulled from yfinance at fan-out time and fed to the
non-deterministic analyst layer — *not* read from a pre-cached
watchlist-scoped table that only covers the user's curated symbols.

This module is the entry point for that on-demand pull. It returns the
computed dict the analyst payload uses and persists it to
``candidate_fundamentals_snapshots`` so retries within the same fan-out
hit the cache and the audit trail keeps exactly what the analyst saw.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any
from uuid import UUID

from app.logging_config import get_logger
from app.sources.yfinance_source import YFinanceSource
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

# How recently a persisted snapshot can stand in for a fresh fetch. yfinance
# updates quarterly statements only when companies file; same-fan-out reuse
# avoids burning a redundant network call when a candidate is re-scored.
_SNAPSHOT_REUSE_HOURS = 12


def fetch_candidate_fundamentals(
    symbol: str,
    *,
    source_run_id: UUID | str | None = None,
    yf_source: YFinanceSource | None = None,
    now: dt.datetime | None = None,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    """Return the L3 fundamentals dict for ``symbol``.

    Returns the dict on success (yfinance pull + parse), ``None`` on
    upstream failure (in which case a row with ``yfinance_ok=false`` is
    still persisted so the audit trail records the attempt).

    Reuses a snapshot less than ``_SNAPSHOT_REUSE_HOURS`` old unless
    ``force_refresh=True``.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None
    current = now or dt.datetime.now(dt.UTC)
    if not force_refresh:
        cached = _load_recent_snapshot(upper_symbol, current=current)
        if cached is not None:
            return cached

    source = yf_source or YFinanceSource()
    payload = source.fetch_quarterly_fundamentals(upper_symbol)
    if payload is None:
        _persist_snapshot(
            symbol=upper_symbol,
            payload={},
            source_run_id=source_run_id,
            yfinance_ok=False,
            error="yfinance returned no quarterly fundamentals",
        )
        return None

    _persist_snapshot(
        symbol=upper_symbol,
        payload=payload,
        source_run_id=source_run_id,
        yfinance_ok=True,
        error=None,
    )
    return payload


def latest_snapshot(symbol: str) -> dict[str, Any] | None:
    """Return the most recent persisted payload for ``symbol``, regardless of age.

    Used by the readiness gate to check freshness and by the payload
    fetcher to surface the exact dict the L3 analyst is meant to cite.
    Returns ``None`` if the table is unreachable (e.g. before the
    migration has been applied) so callers degrade gracefully.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None
    try:
        cm = get_connection_manager()
        with cm.connection() as conn:
            row = conn.execute(
                """
                SELECT payload, fetched_at, yfinance_ok
                FROM candidate_fundamentals_snapshots
                WHERE upper(symbol) = upper(%s)
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (upper_symbol,),
            ).fetchone()
    except Exception:
        logger.exception(
            "candidate_fundamentals_latest_snapshot_query_failed",
            symbol=upper_symbol,
        )
        return None
    if row is None:
        return None
    payload, fetched_at, ok = row
    if not ok:
        return None
    payload_dict = _coerce_payload(payload)
    if payload_dict is None:
        return None
    payload_dict["_persisted_fetched_at"] = (
        fetched_at.isoformat() if isinstance(fetched_at, dt.datetime) else fetched_at
    )
    return payload_dict


def snapshot_age_hours(symbol: str, *, now: dt.datetime | None = None) -> float | None:
    """Hours since the most recent ``yfinance_ok=true`` snapshot, or ``None``."""
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        return None
    current = now or dt.datetime.now(dt.UTC)
    try:
        cm = get_connection_manager()
        with cm.connection() as conn:
            row = conn.execute(
                """
                SELECT fetched_at
                FROM candidate_fundamentals_snapshots
                WHERE upper(symbol) = upper(%s)
                  AND yfinance_ok = true
                ORDER BY fetched_at DESC
                LIMIT 1
                """,
                (upper_symbol,),
            ).fetchone()
    except Exception:
        logger.exception(
            "candidate_fundamentals_age_query_failed", symbol=upper_symbol
        )
        return None
    if row is None or row[0] is None:
        return None
    fetched_at = row[0]
    if not isinstance(fetched_at, dt.datetime):
        return None
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=dt.UTC)
    return (current - fetched_at).total_seconds() / 3600


def _load_recent_snapshot(
    symbol: str, *, current: dt.datetime
) -> dict[str, Any] | None:
    age = snapshot_age_hours(symbol, now=current)
    if age is None or age > _SNAPSHOT_REUSE_HOURS:
        return None
    return latest_snapshot(symbol)


def _persist_snapshot(
    *,
    symbol: str,
    payload: dict[str, Any],
    source_run_id: UUID | str | None,
    yfinance_ok: bool,
    error: str | None,
) -> None:
    payload_json = json.dumps(payload, default=str)
    cm = get_connection_manager()
    try:
        with cm.connection() as conn:
            conn.execute(
                """
                INSERT INTO candidate_fundamentals_snapshots
                    (symbol, source_run_id, payload, yfinance_ok, error)
                VALUES (%s, %s, %s::jsonb, %s, %s)
                """,
                (symbol, str(source_run_id) if source_run_id else None,
                 payload_json, yfinance_ok, error),
            )
            conn.commit()
    except Exception:
        logger.exception(
            "candidate_fundamentals_persist_failed",
            symbol=symbol,
            yfinance_ok=yfinance_ok,
        )


def _coerce_payload(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (str, bytes, bytearray)):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return dict(decoded) if isinstance(decoded, dict) else None
    return None
