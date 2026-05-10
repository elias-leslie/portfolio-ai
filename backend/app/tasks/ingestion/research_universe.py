"""Refresh the research universe (S&P 500 constituents).

Pulls the daily holdings file from the iShares Core S&P 500 ETF (IVV),
which is BlackRock's authoritative tracking of the S&P 500. Diffs against
the local ``research_universe_symbols`` table: new constituents get inserted
and trigger an OHLCV backfill; departed constituents have ``removed_at``
stamped but are kept for historical interpretability.
"""

from __future__ import annotations

import csv
import datetime as dt
import uuid
from typing import Any

import requests

from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.tasks.ingestion.price_ingestion import ingest_historical_ohlcv

logger = get_logger(__name__)

IVV_HOLDINGS_URL = (
    "https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund"
)
IVV_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"
IVV_REQUEST_TIMEOUT = 30
SOURCE_LABEL = "ishares_ivv"
BACKFILL_DAYS = TRADING_DAYS_PER_YEAR * 6  # ~6 years of history per new symbol

# iShares strips the dot-suffix from dual-class tickers; yfinance uses a hyphen.
TICKER_NORMALIZATION = {
    "BRKB": "BRK-B",
    "BFB": "BF-B",
}


def _normalize_ticker(ticker: str) -> str:
    """Translate iShares ticker convention to yfinance convention."""
    return TICKER_NORMALIZATION.get(ticker, ticker)


def _fetch_ivv_holdings() -> list[str]:
    """Download iShares IVV holdings and return current equity tickers.

    Returns:
        Normalised list of ticker symbols (yfinance convention).

    Raises:
        requests.RequestException: Network or HTTP error.
        ValueError: Response is missing the expected header row.
    """
    response = requests.get(
        IVV_HOLDINGS_URL,
        headers={"User-Agent": IVV_USER_AGENT},
        timeout=IVV_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    text = response.content.decode("utf-8-sig")

    lines = text.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("Ticker,")),
        None,
    )
    if header_idx is None:
        raise ValueError("IVV holdings response missing 'Ticker,' header row")

    reader = csv.DictReader(lines[header_idx:])
    seen: set[str] = set()
    tickers: list[str] = []
    for row in reader:
        ticker = (row.get("Ticker") or "").strip()
        asset_class = (row.get("Asset Class") or "").strip()
        if not ticker or ticker == "-" or asset_class != "Equity":
            continue
        normalized = _normalize_ticker(ticker)
        if normalized in seen:
            continue
        seen.add(normalized)
        tickers.append(normalized)
    return tickers


def _diff_against_current(conn: Any, fresh: list[str]) -> tuple[list[str], list[str]]:
    """Compare fetched tickers against currently-active universe rows.

    Returns:
        (additions, departures) where additions are symbols not yet present
        as active rows and departures are active rows missing from fresh.
    """
    fresh_set = set(fresh)
    rows = conn.execute(
        "SELECT symbol FROM research_universe_symbols WHERE removed_at IS NULL"
    ).fetchall()
    current_set = {str(row[0]) for row in rows}
    additions = sorted(fresh_set - current_set)
    departures = sorted(current_set - fresh_set)
    return additions, departures


def refresh_research_universe(
    *,
    backfill_new_symbols: bool = True,
) -> dict[str, Any]:
    """Refresh the research universe from the authoritative IVV holdings.

    Schedule (suggested): weekly via Hatchet, e.g. Sunday 06:00 UTC, before
    the screening sweep runs.

    Args:
        backfill_new_symbols: When True, queue ``ingest_historical_ohlcv`` for
            newly-added symbols so the screening pipeline has data to backtest
            against. Disabled in tests / when the caller wants a pure refresh.

    Returns:
        Summary dict with counts and any errors.
    """
    task_id = str(uuid.uuid4())
    started_at = dt.datetime.now(dt.UTC)
    logger.info("refresh_research_universe_started", task_id=task_id)

    try:
        fresh = _fetch_ivv_holdings()
    except Exception as exc:  # network failure shouldn't crash the worker
        logger.exception("refresh_research_universe_fetch_failed", task_id=task_id)
        return {
            "task_id": task_id,
            "status": "fetch_failed",
            "error": str(exc),
            "duration_seconds": (dt.datetime.now(dt.UTC) - started_at).total_seconds(),
        }

    if not fresh:
        logger.warning("refresh_research_universe_empty_fetch", task_id=task_id)
        return {
            "task_id": task_id,
            "status": "empty_fetch",
            "duration_seconds": (dt.datetime.now(dt.UTC) - started_at).total_seconds(),
        }

    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        additions, departures = _diff_against_current(conn, fresh)

        # New constituents
        for symbol in additions:
            conn.execute(
                """
                INSERT INTO research_universe_symbols (symbol, source, added_at, last_seen_at)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                    source = EXCLUDED.source,
                    removed_at = NULL,
                    last_seen_at = NOW()
                """,
                (symbol, SOURCE_LABEL),
            )

        # Departures
        if departures:
            conn.execute(
                """
                UPDATE research_universe_symbols
                SET removed_at = NOW()
                WHERE removed_at IS NULL AND symbol = ANY(%s)
                """,
                (departures,),
            )

        # Continuing - bump last_seen_at on everything we just observed
        conn.execute(
            """
            UPDATE research_universe_symbols
            SET last_seen_at = NOW()
            WHERE removed_at IS NULL AND symbol = ANY(%s)
            """,
            (fresh,),
        )
        conn.commit()

    backfill_result: dict[str, Any] | None = None
    if backfill_new_symbols and additions:
        try:
            backfill_result = ingest_historical_ohlcv(additions, days=BACKFILL_DAYS)
        except Exception as exc:
            logger.exception(
                "refresh_research_universe_backfill_failed",
                task_id=task_id,
                additions_count=len(additions),
            )
            backfill_result = {"status": "failed", "error": str(exc)}

    duration = (dt.datetime.now(dt.UTC) - started_at).total_seconds()
    summary: dict[str, Any] = {
        "task_id": task_id,
        "status": "completed",
        "fetched_count": len(fresh),
        "additions_count": len(additions),
        "departures_count": len(departures),
        "additions": additions,
        "departures": departures,
        "duration_seconds": duration,
    }
    if backfill_result is not None:
        summary["backfill"] = backfill_result

    logger.info(
        "refresh_research_universe_completed",
        task_id=task_id,
        fetched_count=summary["fetched_count"],
        additions_count=summary["additions_count"],
        departures_count=summary["departures_count"],
        duration_seconds=duration,
    )
    return summary
