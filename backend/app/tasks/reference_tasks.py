"""Tasks for reference data maintenance.

Background tasks for maintaining cached reference data, including extraction
of valuation metrics from JSON payloads and enriching the database with
structured metrics for efficient querying.

Implementation helpers live in reference_helpers.py.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from app.analytics.analyst_revisions import refresh_analyst_revisions_for_symbols
from app.logging_config import get_logger
from app.repositories import ReferenceRepository
from app.utils import safe_subprocess
from app.utils.task_helpers import get_watchlist_symbols_or_early_return

from .reference_helpers import (
    ValuationMetricsDict,
    _backfill_symbol_company_names,
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
    "refresh_financial_health_scores_isolated",
    "refresh_risk_metrics",
    "refresh_yfinance_reference_data",
]

_FINANCIAL_HEALTH_CHILD_TIMEOUT_SECONDS = 3300
_FINANCIAL_HEALTH_CHILD_RESULT_PREFIX = "FINANCIAL_HEALTH_RESULT_JSON="


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
            exc_info=True,
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
    names_updated = _backfill_symbol_company_names()
    logger.info("symbol_company_names_backfilled", names_updated=names_updated)

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


def _tail_text(value: str, *, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def _parse_financial_health_child_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if line.startswith(_FINANCIAL_HEALTH_CHILD_RESULT_PREFIX):
            raw = line.removeprefix(_FINANCIAL_HEALTH_CHILD_RESULT_PREFIX)
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise RuntimeError("financial health child returned non-object JSON")
            return parsed
    raise RuntimeError(
        "financial health child did not emit a result marker. "
        f"stdout_tail={_tail_text(stdout)!r}"
    )


def refresh_financial_health_scores_isolated() -> dict[str, Any]:
    """Run financial-health scoring in a short-lived Python process.

    The Hatchet worker is a long-lived, multi-workflow process that also runs
    frequent yfinance quote/reference jobs. In that environment yfinance
    financial-statement calls can return empty immediately for every symbol,
    while the same task succeeds from a fresh process under the same systemd
    environment. Keep the isolation scoped to this weekly yfinance statement
    refresh so Hatchet still owns scheduling, retries, and audit.
    """
    completed = safe_subprocess.run(
        [sys.executable, "-m", "app.tasks.reference_tasks", "financial-health"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=_FINANCIAL_HEALTH_CHILD_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "financial health child process failed "
            f"rc={completed.returncode} "
            f"stdout_tail={_tail_text(completed.stdout or '')!r} "
            f"stderr_tail={_tail_text(completed.stderr or '')!r}"
        )
    result = _parse_financial_health_child_result(completed.stdout or "")
    result["execution_mode"] = "subprocess"
    logger.info("financial_health_scores_child_completed", **result)
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


def _main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["financial-health"]:
        print("Usage: python -m app.tasks.reference_tasks financial-health", file=sys.stderr)
        return 2
    result = refresh_financial_health_scores()
    print(
        _FINANCIAL_HEALTH_CHILD_RESULT_PREFIX
        + json.dumps(result, sort_keys=True, default=str)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
