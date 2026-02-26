"""Tasks for reference data maintenance.

Background tasks for maintaining cached reference data, including extraction
of valuation metrics from JSON payloads and enriching the database with
structured metrics for efficient querying.

Implementation helpers live in reference_helpers.py.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.analytics.analyst_revisions import refresh_analyst_revisions_for_symbols
from app.logging_config import get_logger
from app.repositories import ReferenceRepository
from app.utils.task_helpers import get_watchlist_symbols_or_early_return

from .reference_helpers import (
    ValuationMetricsDict,
    _extract_valuation_metrics,
    _fetch_stale_symbols,
    _process_cache_entries,
    _process_health_score_for_symbol,
    _process_risk_metrics_for_symbol,
    _store_alphavantage_payload,
    _store_yfinance_payload,
    _update_valuation_metrics,
)

logger = get_logger(__name__)

__all__ = [
    "ValuationMetricsDict",
    "_extract_valuation_metrics",
    "_update_valuation_metrics",
    "parse_valuation_metrics",
    "refresh_alphavantage_reference_backup",
    "refresh_analyst_revisions",
    "refresh_financial_health_scores",
    "refresh_risk_metrics",
    "refresh_yfinance_reference_data",
]


def _task_result(task_id: str, start_time: dt.datetime, **extra: Any) -> dict[str, Any]:
    """Build a standard task result dict."""
    duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
    return {"task_id": task_id, "duration_seconds": int(duration), **extra}


def parse_valuation_metrics() -> dict[str, int | str | float]:
    """Parse valuation metrics from cached JSON payloads.

    Extracts valuation metrics (P/E, P/B, P/S, etc.) from JSON payloads
    in the reference_cache table and populates the structured valuation columns.

    Safe to run repeatedly (idempotent).

    Returns:
        Dict with task_id, entries_processed, entries_updated, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info("valuation_metrics_parsing_started", task_id=task_id)

    try:
        entries_processed, entries_updated = _process_cache_entries()
        result = _task_result(
            task_id,
            start_time,
            entries_processed=entries_processed,
            entries_updated=entries_updated,
        )
        logger.info("valuation_metrics_parsing_completed", **result)
        return result
    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "valuation_metrics_parsing_failed",
            task_id=task_id,
            error=str(e),
            duration_seconds=duration,
        )
        return {"task_id": task_id, "status": "failed", "error": str(e), "duration_seconds": int(duration)}


def refresh_yfinance_reference_data() -> dict[str, int | str | float | None]:
    """Fetch reference data from yfinance for watchlist symbols.

    Runs daily at 04:00 UTC.

    Returns:
        Dict with task_id, symbols_processed, symbols_updated, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info("yfinance_reference_refresh_started", task_id=task_id)

    symbols, _storage, early_return = get_watchlist_symbols_or_early_return(
        task_id, "no_watchlist_symbols_found"
    )
    if early_return:
        return early_return

    logger.info("fetching_yfinance_reference", num_symbols=len(symbols))
    symbols_updated = _store_yfinance_payload(symbols)

    result = _task_result(
        task_id, start_time, symbols_processed=len(symbols), symbols_updated=symbols_updated
    )
    logger.info("yfinance_reference_refresh_completed", **result)
    return result


def refresh_alphavantage_reference_backup() -> dict[str, int | str | float | None]:
    """Fetch Alpha Vantage reference data for symbols with missing/stale yfinance data.

    Runs daily at 04:45 UTC, after yfinance refresh.

    Returns:
        Dict with task_id, symbols_processed, symbols_updated, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info("alphavantage_backup_refresh_started", task_id=task_id)

    symbols = _fetch_stale_symbols()
    if not symbols:
        logger.info("no_symbols_need_alphavantage_backup")
        return _task_result(task_id, start_time, symbols_processed=0, symbols_updated=0)

    logger.info("fetching_alphavantage_backup", num_symbols=len(symbols))
    symbols_updated = _store_alphavantage_payload(symbols)
    result = _task_result(
        task_id, start_time, symbols_processed=len(symbols), symbols_updated=symbols_updated
    )
    logger.info("alphavantage_backup_refresh_completed", **result)
    return result


def refresh_analyst_revisions() -> dict[str, int | str | float | None]:
    """Fetch analyst estimate revisions for watchlist symbols (GAP-005).

    Runs daily at 07:00 UTC (after market close).

    Returns:
        Dict with task_id, symbols_processed, records_saved, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info("analyst_revisions_refresh_started", task_id=task_id)

    symbols, storage, early_return = get_watchlist_symbols_or_early_return(
        task_id, "no_watchlist_symbols_for_analyst_revisions", "records_saved"
    )
    if early_return:
        return early_return

    logger.info("refreshing_analyst_revisions", num_symbols=len(symbols))
    results = refresh_analyst_revisions_for_symbols(storage, symbols)
    result = _task_result(
        task_id,
        start_time,
        symbols_processed=len(symbols),
        success=results["success"],
        failed=results["failed"],
        records_saved=results["records_saved"],
    )
    logger.info("analyst_revisions_refresh_completed", **result)
    return result


def _run_for_symbols(
    task_id: str,
    symbols: list[str],
    repo: ReferenceRepository,
    processor: Any,
    log_event: str,
) -> int:
    """Run a per-symbol processor, logging warnings on errors. Returns updated count."""
    updated = 0
    for symbol in symbols:
        try:
            if processor(symbol, repo):
                updated += 1
        except Exception as e:
            logger.warning(log_event, symbol=symbol, error=str(e))
    return updated


def refresh_financial_health_scores() -> dict[str, int | str | float | None]:
    """Calculate Piotroski F-Score and Altman Z-Score for watchlist symbols.

    GAP-008/GAP-009. Runs weekly on Sundays at 05:00 UTC.

    Returns:
        Dict with task_id, symbols_processed, symbols_updated, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info("financial_health_scores_refresh_started", task_id=task_id)

    symbols, storage, early_return = get_watchlist_symbols_or_early_return(
        task_id, "no_watchlist_symbols_for_health_scores"
    )
    if early_return:
        return early_return

    logger.info("calculating_financial_health_scores", num_symbols=len(symbols))
    repo = ReferenceRepository(storage)
    symbols_updated = _run_for_symbols(
        task_id, symbols, repo, _process_health_score_for_symbol, "financial_health_scores_symbol_error"
    )
    result = _task_result(
        task_id, start_time, symbols_processed=len(symbols), symbols_updated=symbols_updated
    )
    logger.info("financial_health_scores_refresh_completed", **result)
    return result


def _process_risk_for_symbol_today(symbol: str, repo: ReferenceRepository) -> bool:
    """Adapter: call _process_risk_metrics_for_symbol with today's date."""
    return _process_risk_metrics_for_symbol(symbol, repo, dt.date.today())


def refresh_risk_metrics() -> dict[str, int | str | float | None]:
    """Calculate VaR, CVaR, and extended betas for watchlist symbols.

    GAP-027/GAP-022. Runs daily at 05:30 UTC.

    Returns:
        Dict with task_id, symbols_processed, symbols_updated, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info("risk_metrics_refresh_started", task_id=task_id)

    symbols, storage, early_return = get_watchlist_symbols_or_early_return(
        task_id, "no_watchlist_symbols_for_risk_metrics"
    )
    if early_return:
        return early_return

    logger.info("calculating_risk_metrics", num_symbols=len(symbols))
    repo = ReferenceRepository(storage)
    symbols_updated = _run_for_symbols(
        task_id, symbols, repo, _process_risk_for_symbol_today, "risk_metrics_symbol_error"
    )
    result = _task_result(
        task_id, start_time, symbols_processed=len(symbols), symbols_updated=symbols_updated
    )
    logger.info("risk_metrics_refresh_completed", **result)
    return result
