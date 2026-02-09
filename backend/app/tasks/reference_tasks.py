"""Celery tasks for reference data maintenance.

This module defines background tasks for maintaining cached reference data,
including extraction of valuation metrics from JSON payloads and enriching
the database with structured metrics for efficient querying.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any, TypedDict

from psycopg2 import OperationalError
from requests.exceptions import RequestException

from app.analytics.analyst_revisions import refresh_analyst_revisions_for_symbols
from app.analytics.financial_health_scores import get_financial_health_scores
from app.analytics.risk_metrics import calculate_symbol_beta, calculate_symbol_var
from app.logging_config import get_logger
from app.repositories import ReferenceRepository
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage
from app.utils.formatters import parse_float
from app.utils.task_helpers import get_watchlist_symbols_or_early_return

logger = get_logger(__name__)


class ValuationMetricsDict(TypedDict, total=False):
    """Valuation metrics extracted from reference data payloads."""

    pe_ratio_trailing: float | None
    pe_ratio_forward: float | None
    ps_ratio: float | None
    pb_ratio: float | None
    peg_ratio: float | None
    dividend_yield: float | None
    payout_ratio: float | None


def _extract_valuation_metrics(payload: dict[str, Any]) -> ValuationMetricsDict:
    """Extract valuation metrics from JSON payload.

    Supports both yfinance and Alpha Vantage payloads.

    yfinance field mapping:
    - trailingPE -> pe_ratio_trailing
    - forwardPE -> pe_ratio_forward
    - priceToSalesTrailing12Months -> ps_ratio
    - priceToBook -> pb_ratio
    - pegRatio -> peg_ratio
    - dividendYield -> dividend_yield
    - payoutRatio -> payout_ratio

    Alpha Vantage field mapping:
    - PERatio/TrailingPE -> pe_ratio_trailing
    - ForwardPE -> pe_ratio_forward
    - PriceToSalesRatioTTM -> ps_ratio
    - PriceToBookRatio -> pb_ratio
    - PEGRatio -> peg_ratio
    - DividendYield -> dividend_yield
    - (calculated from DividendPerShare / EPS) -> payout_ratio

    Args:
        payload: JSON payload dict from reference_cache

    Returns:
        Dict with extracted metrics (values are None if not in payload)
    """
    # Check if yfinance format (has 'trailingPE') or Alpha Vantage (has 'PERatio')
    if "trailingPE" in payload or "forwardPE" in payload:
        # yfinance format
        return {
            "pe_ratio_trailing": payload.get("trailingPE"),
            "pe_ratio_forward": payload.get("forwardPE"),
            "ps_ratio": payload.get("priceToSalesTrailing12Months"),
            "pb_ratio": payload.get("priceToBook"),
            "peg_ratio": payload.get("pegRatio") or payload.get("trailingPegRatio"),
            "dividend_yield": payload.get("dividendYield"),
            "payout_ratio": payload.get("payoutRatio"),
        }

    if "PERatio" in payload or "PriceToBookRatio" in payload:
        # Alpha Vantage format (all strings, need parsing)
        pe_ratio = parse_float(payload.get("PERatio") or payload.get("TrailingPE"))
        forward_pe = parse_float(payload.get("ForwardPE"))
        pb_ratio = parse_float(payload.get("PriceToBookRatio"))
        ps_ratio = parse_float(payload.get("PriceToSalesRatioTTM"))
        peg_ratio = parse_float(payload.get("PEGRatio"))
        div_yield = parse_float(payload.get("DividendYield"))
        div_per_share = parse_float(payload.get("DividendPerShare"))
        eps = parse_float(payload.get("EPS"))

        # Calculate payout ratio if possible
        payout_ratio = None
        if div_per_share and eps and eps > 0:
            payout_ratio = div_per_share / eps

        return {
            "pe_ratio_trailing": pe_ratio,
            "pe_ratio_forward": forward_pe,
            "ps_ratio": ps_ratio,
            "pb_ratio": pb_ratio,
            "peg_ratio": peg_ratio,
            "dividend_yield": div_yield,
            "payout_ratio": payout_ratio,
        }
    # Unknown format or no valuation data
    return {
        "pe_ratio_trailing": None,
        "pe_ratio_forward": None,
        "ps_ratio": None,
        "pb_ratio": None,
        "peg_ratio": None,
        "dividend_yield": None,
        "payout_ratio": None,
    }


def _update_valuation_metrics(symbol: str, source: str, payload: dict[str, Any]) -> None:
    """Update valuation metrics for a single symbol/source combination.

    Args:
        symbol: Stock symbol
        source: Data source (e.g., "fundamentals")
        payload: JSON payload dict containing valuation data
    """
    metrics = _extract_valuation_metrics(payload)

    # Only update if we found at least one metric
    if not any(v is not None for v in metrics.values()):
        logger.debug(
            "no_valuation_metrics_found",
            symbol=symbol,
            source=source,
        )
        return

    storage = get_storage()
    repo = ReferenceRepository(storage)

    # Find the most recent cache entry for this symbol/source
    as_of_date = repo.get_latest_cache_entry_date(symbol, source)

    if as_of_date is None:
        logger.debug(
            "no_cache_entry_found",
            symbol=symbol,
            source=source,
        )
        return

    # Dual-write using repository method
    metrics_columns = [
        "pe_ratio_trailing",
        "pe_ratio_forward",
        "ps_ratio",
        "pb_ratio",
        "peg_ratio",
        "dividend_yield",
        "payout_ratio",
    ]
    metrics_values = [
        metrics.get("pe_ratio_trailing"),
        metrics.get("pe_ratio_forward"),
        metrics.get("ps_ratio"),
        metrics.get("pb_ratio"),
        metrics.get("peg_ratio"),
        metrics.get("dividend_yield"),
        metrics.get("payout_ratio"),
    ]

    base_update_sql = """
        UPDATE reference_cache
        SET pe_ratio_trailing = %s, pe_ratio_forward = %s, ps_ratio = %s,
            pb_ratio = %s, peg_ratio = %s, dividend_yield = %s, payout_ratio = %s
        WHERE symbol = %s AND source = %s AND as_of_date = %s
    """
    base_params = [*metrics_values, symbol, source, as_of_date]

    repo.upsert_dual_write_metrics(
        symbol=symbol,
        as_of_date=as_of_date,
        base_table_update_sql=base_update_sql,
        base_table_params=base_params,
        metrics_table="valuation_metrics",
        metrics_columns=metrics_columns,
        metrics_values=metrics_values,
        conflict_keys=["symbol", "as_of_date"],
    )

    logger.info(
        "valuation_metrics_updated",
        symbol=symbol,
        source=source,
        metrics_count=sum(1 for v in metrics.values() if v is not None),
    )


def _process_cache_entries() -> tuple[int, int]:
    """Process all cache entries and extract valuation metrics.

    Queries all reference_cache entries with payloads, parses JSON,
    extracts metrics, and updates database.

    Returns:
        Tuple of (entries_processed, entries_updated)
    """
    storage = get_storage()
    repo = ReferenceRepository(storage)
    entries_processed = 0
    entries_updated = 0

    # Get all cache entries with non-null payloads
    results = repo.get_cache_entries_with_payloads()

    logger.info(
        "valuation_metrics_found_entries",
        total_entries=len(results),
    )

    # Track which symbol/source combinations we've processed
    # (only process most recent for each pair)
    processed_pairs: set[tuple[str, str]] = set()

    for symbol, source, payload_json in results:
        # Type guard: ensure symbol and source are strings
        if not isinstance(symbol, str) or not isinstance(source, str):
            continue

        pair = (symbol, source)

        # Skip if we've already processed this symbol/source combo
        if pair in processed_pairs:
            continue

        entries_processed += 1
        processed_pairs.add(pair)

        # Parse payload
        try:
            if isinstance(payload_json, str):
                payload = json.loads(payload_json)
            else:
                payload = payload_json
        except json.JSONDecodeError:
            logger.warning(
                "invalid_json_payload",
                symbol=symbol,
                source=source,
            )
            continue

        # Type guard: ensure payload is a dict
        if not isinstance(payload, dict):
            logger.debug(
                "skipping_non_dict_payload",
                symbol=symbol,
                source=source,
                payload_type=type(payload).__name__,
            )
            continue

        # Extract and update metrics
        metrics = _extract_valuation_metrics(payload)

        # Only count as "updated" if we found at least one metric
        if any(v is not None for v in metrics.values()):
            entries_updated += 1
            # Type guard ensures symbol and source are strings
            _update_valuation_metrics(symbol, source, payload)

    return entries_processed, entries_updated


def parse_valuation_metrics() -> dict[str, int | str | float]:
    """Parse valuation metrics from cached JSON payloads.

    This task extracts valuation metrics (P/E, P/B, P/S, etc.) from JSON payloads
    in the reference_cache table and populates the structured valuation columns.

    Safe to run repeatedly (idempotent):
    - Processes all cache entries without source constraint
    - Updates valuation columns based on current payload data
    - Non-destructive (adds data, doesn't remove)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - entries_processed: Number of cache entries processed
        - entries_updated: Number of entries with metrics found and updated
        - duration_seconds: Total execution time

    Example:
        >>> # Manual trigger for testing
        >>> celery -A app.celery_app call app.tasks.reference_tasks.parse_valuation_metrics
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info(
        "valuation_metrics_parsing_started",
        task_id=task_id,
    )

    try:
        entries_processed, entries_updated = _process_cache_entries()
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.info(
            "valuation_metrics_parsing_completed",
            task_id=task_id,
            entries_processed=entries_processed,
            entries_updated=entries_updated,
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "entries_processed": entries_processed,
            "entries_updated": entries_updated,
            "duration_seconds": int(duration),
        }

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.error(
            "valuation_metrics_parsing_failed",
            task_id=task_id,
            error=str(e),
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "duration_seconds": int(duration),
        }


def refresh_yfinance_reference_data() -> dict[str, int | str | float | None]:
    """Fetch reference data (including valuation metrics) from yfinance for watchlist symbols.

    Runs daily at 04:00 UTC to refresh fundamental and valuation data.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_processed: Number of symbols attempted
        - symbols_updated: Number of symbols successfully updated
        - duration_seconds: Total execution time
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("yfinance_reference_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = get_watchlist_symbols_or_early_return(
            task_id, "no_watchlist_symbols_found"
        )
        if early_return:
            return early_return

        logger.info("fetching_yfinance_reference", num_symbols=len(symbols))

        # Fetch reference data from yfinance
        source = YFinanceSource()
        as_of = dt.date.today()

        df = source.fetch_reference_payload(symbols, as_of)

        if df is None or df.is_empty():
            logger.warning("yfinance_reference_fetch_failed")
            return {
                "task_id": task_id,
                "symbols_processed": len(symbols),
                "symbols_updated": 0,
                "duration_seconds": (dt.datetime.now(dt.UTC) - start_time).total_seconds(),
            }

        # Store in reference_cache table using repository method
        repo = ReferenceRepository(storage)
        symbols_updated = 0
        for row in df.iter_rows(named=True):
            repo.upsert_reference_cache(
                symbol=row["symbol"],
                as_of_date=row["as_of_date"],
                payload=row["payload"],
                source="yfinance",
            )
            symbols_updated += 1

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.info(
            "yfinance_reference_refresh_completed",
            task_id=task_id,
            symbols_processed=len(symbols),
            symbols_updated=symbols_updated,
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "symbols_processed": len(symbols),
            "symbols_updated": symbols_updated,
            "duration_seconds": int(duration),
        }

    except Exception as e:
        logger.error(
            "yfinance_reference_refresh_error",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def _fetch_stale_symbols() -> list[str]:
    """Fetch symbols needing Alpha Vantage backup data.

    Identifies symbols from watchlist with:
    - No yfinance data in cache, OR
    - yfinance data older than 7 days

    Returns:
        List of symbols needing backup data
    """
    storage = get_storage()
    repo = ReferenceRepository(storage)
    return repo.get_stale_symbols(days_threshold=7)


def _store_alphavantage_payload(symbols: list[str]) -> int:
    """Store Alpha Vantage reference data in database.

    Fetches reference data from Alpha Vantage API and inserts/updates
    cache entries.

    Args:
        symbols: List of symbols to fetch

    Returns:
        Number of symbols successfully stored
    """
    source = AlphaVantageSource()
    as_of = dt.date.today()

    df = source.fetch_reference_payload(symbols, as_of)

    if df is None or df.is_empty():
        logger.warning("alphavantage_backup_fetch_failed")
        return 0

    storage = get_storage()
    repo = ReferenceRepository(storage)
    rows_upserted = 0
    for row in df.iter_rows(named=True):
        repo.upsert_reference_cache(
            symbol=row["symbol"],
            as_of_date=row["as_of_date"],
            payload=row["payload"],
            source="alphavantage",
        )
        rows_upserted += 1
    return rows_upserted


def refresh_alphavantage_reference_backup(
    self: Task[..., Any],
) -> dict[str, int | str | float | None]:
    """Fetch Alpha Vantage reference data for symbols with missing/stale yfinance data.

    Runs daily at 04:45 UTC, after yfinance refresh.
    Only fetches symbols where yfinance data is missing or >7 days old.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_processed: Number of symbols attempted
        - symbols_updated: Number of symbols successfully updated
        - duration_seconds: Total execution time
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("alphavantage_backup_refresh_started", task_id=task_id)

    try:
        symbols = _fetch_stale_symbols()

        if not symbols:
            logger.info("no_symbols_need_alphavantage_backup")
            return {
                "task_id": task_id,
                "symbols_processed": 0,
                "symbols_updated": 0,
                "duration_seconds": 0,
            }

        logger.info("fetching_alphavantage_backup", num_symbols=len(symbols))

        symbols_updated = _store_alphavantage_payload(symbols)
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.info(
            "alphavantage_backup_refresh_completed",
            task_id=task_id,
            symbols_processed=len(symbols),
            symbols_updated=symbols_updated,
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "symbols_processed": len(symbols),
            "symbols_updated": symbols_updated,
            "duration_seconds": int(duration),
        }

    except Exception as e:
        logger.error(
            "alphavantage_backup_refresh_error",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def refresh_analyst_revisions() -> dict[str, int | str | float | None]:
    """Fetch analyst estimate revisions for watchlist symbols (GAP-005).

    Runs daily at 07:00 UTC (after market close).
    Fetches EPS and revenue estimate revisions from FMP API.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_processed: Number of symbols attempted
        - records_saved: Number of revision records saved
        - duration_seconds: Total execution time
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("analyst_revisions_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = get_watchlist_symbols_or_early_return(
            task_id, "no_watchlist_symbols_for_analyst_revisions", "records_saved"
        )
        if early_return:
            return early_return

        logger.info("refreshing_analyst_revisions", num_symbols=len(symbols))

        results = refresh_analyst_revisions_for_symbols(storage, symbols)
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.info(
            "analyst_revisions_refresh_completed",
            task_id=task_id,
            symbols_processed=len(symbols),
            success=results["success"],
            failed=results["failed"],
            records_saved=results["records_saved"],
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "symbols_processed": len(symbols),
            "success": results["success"],
            "failed": results["failed"],
            "records_saved": results["records_saved"],
            "duration_seconds": int(duration),
        }

    except Exception as e:
        logger.error(
            "analyst_revisions_refresh_error",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def refresh_financial_health_scores() -> dict[str, int | str | float | None]:
    """Calculate Piotroski F-Score and Altman Z-Score for watchlist symbols.

    GAP-008: Piotroski F-Score (9-point fundamental quality score)
    GAP-009: Altman Z-Score (bankruptcy prediction model)

    Runs weekly on Sundays at 05:00 UTC (after market close).
    Uses yfinance to fetch balance sheet and income statement data.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_processed: Number of symbols attempted
        - symbols_updated: Number of symbols with scores calculated
        - duration_seconds: Total execution time
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("financial_health_scores_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = get_watchlist_symbols_or_early_return(
            task_id, "no_watchlist_symbols_for_health_scores"
        )
        if early_return:
            return early_return

        logger.info("calculating_financial_health_scores", num_symbols=len(symbols))

        symbols_updated = 0
        repo = ReferenceRepository(storage)

        for symbol in symbols:
            try:
                scores = get_financial_health_scores(symbol)

                if scores.f_score is not None or scores.z_score is not None:
                    # Prepare score values
                    f_components_json = (
                        json.dumps(scores.f_score_components) if scores.f_score_components else None
                    )
                    score_values = [
                        scores.f_score,
                        f_components_json,
                        scores.z_score,
                        scores.z_score_zone,
                    ]

                    # Dual-write using repository method
                    base_update_sql = """
                        UPDATE reference_cache
                        SET f_score = %s, f_score_components = %s,
                            z_score = %s, z_score_zone = %s
                        WHERE symbol = %s
                          AND as_of_date = (
                              SELECT MAX(as_of_date) FROM reference_cache WHERE symbol = %s
                          )
                    """
                    repo.upsert_dual_write_metrics(
                        symbol=symbol,
                        as_of_date=dt.date.today(),  # Use today for metrics table
                        base_table_update_sql=base_update_sql,
                        base_table_params=[*score_values, symbol, symbol],
                        metrics_table="financial_health_scores",
                        metrics_columns=[
                            "f_score",
                            "f_score_components",
                            "z_score",
                            "z_score_zone",
                        ],
                        metrics_values=score_values,
                        conflict_keys=["symbol", "as_of_date"],
                    )

                    symbols_updated += 1
                    logger.debug(
                        "financial_health_scores_calculated",
                        symbol=symbol,
                        f_score=scores.f_score,
                        z_score=scores.z_score,
                    )
            except Exception as e:
                logger.warning(
                    "financial_health_scores_symbol_error",
                    symbol=symbol,
                    error=str(e),
                )
                continue

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.info(
            "financial_health_scores_refresh_completed",
            task_id=task_id,
            symbols_processed=len(symbols),
            symbols_updated=symbols_updated,
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "symbols_processed": len(symbols),
            "symbols_updated": symbols_updated,
            "duration_seconds": int(duration),
        }

    except Exception as e:
        logger.error(
            "financial_health_scores_refresh_error",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def refresh_risk_metrics() -> dict[str, int | str | float | None]:
    """Calculate VaR, CVaR, and extended betas for watchlist symbols.

    GAP-027: VaR/CVaR (Value at Risk, Conditional VaR)
    GAP-022: Long-window beta estimation (90d, 1y, 2y)

    Runs daily at 05:30 UTC (after market close and day_bars update).
    Uses historical simulation for VaR, OLS regression for beta.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_processed: Number of symbols attempted
        - symbols_updated: Number of symbols with metrics calculated
        - duration_seconds: Total execution time
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("risk_metrics_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = get_watchlist_symbols_or_early_return(
            task_id, "no_watchlist_symbols_for_risk_metrics"
        )
        if early_return:
            return early_return

        logger.info("calculating_risk_metrics", num_symbols=len(symbols))

        repo = ReferenceRepository(storage)
        symbols_updated = 0
        as_of_date = dt.date.today()

        for symbol in symbols:
            try:
                # Calculate VaR/CVaR
                var_result = calculate_symbol_var(storage, symbol)

                # Calculate multi-window betas
                beta_result = calculate_symbol_beta(storage, symbol)

                # Skip if no valid metrics
                if var_result.var_95 is None and beta_result.beta_90d is None:
                    continue

                # Upsert into symbol_risk_metrics using repository
                repo.upsert_risk_metrics(
                    symbol=symbol,
                    as_of_date=as_of_date,
                    var_95=var_result.var_95,
                    var_99=var_result.var_99,
                    cvar_95=var_result.cvar_95,
                    cvar_99=var_result.cvar_99,
                    beta_90d=beta_result.beta_90d,
                    beta_1y=beta_result.beta_1y,
                    beta_2y=beta_result.beta_2y,
                    r_squared_1y=beta_result.r_squared_1y,
                    observations=var_result.observations,
                )
                symbols_updated += 1

                logger.debug(
                    "risk_metrics_calculated",
                    symbol=symbol,
                    var_95=var_result.var_95,
                    beta_1y=beta_result.beta_1y,
                )

            except Exception as e:
                logger.warning(
                    "risk_metrics_symbol_error",
                    symbol=symbol,
                    error=str(e),
                )
                continue

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        logger.info(
            "risk_metrics_refresh_completed",
            task_id=task_id,
            symbols_processed=len(symbols),
            symbols_updated=symbols_updated,
            duration_seconds=duration,
        )

        return {
            "task_id": task_id,
            "symbols_processed": len(symbols),
            "symbols_updated": symbols_updated,
            "duration_seconds": int(duration),
        }

    except Exception as e:
        logger.error(
            "risk_metrics_refresh_error",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
