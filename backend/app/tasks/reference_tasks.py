"""Celery tasks for reference data maintenance.

This module defines background tasks for maintaining cached reference data,
including extraction of valuation metrics from JSON payloads and enriching
the database with structured metrics for efficient querying.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from celery import Task

from psycopg.errors import OperationalError
from requests.exceptions import RequestException

from app.analytics.analyst_revisions import refresh_analyst_revisions_for_symbols
from app.analytics.financial_health_scores import get_financial_health_scores
from app.analytics.risk_metrics import calculate_symbol_beta, calculate_symbol_var
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage
from app.utils.formatters import parse_float
from app.utils.watchlist_cache import get_watchlist_symbols_cached

logger = get_logger(__name__)


def _dual_write_metrics(
    conn: Any,
    symbol: str,
    as_of_date: Any,
    base_table_update_sql: str,
    base_table_params: list[Any],
    metrics_table: str,
    metrics_columns: list[str],
    metrics_values: list[Any],
    conflict_keys: list[str],
) -> None:
    """Write metrics to both reference_cache and a dedicated metrics table.

    This pattern is used for valuation metrics, financial health scores, etc.
    where we want both the cached payload + structured metrics columns AND
    a dedicated historical table for efficient queries.

    Args:
        conn: Database connection
        symbol: Stock symbol
        as_of_date: Date for the metrics record
        base_table_update_sql: SQL to update reference_cache
        base_table_params: Parameters for base table update
        metrics_table: Name of dedicated metrics table
        metrics_columns: Column names for metrics table (excluding symbol, as_of_date)
        metrics_values: Values for metrics columns
        conflict_keys: Columns for ON CONFLICT clause
    """
    # Update reference_cache (base table)
    conn.execute(base_table_update_sql, base_table_params)

    # Build metrics table INSERT with ON CONFLICT
    all_columns = ["symbol", "as_of_date", *metrics_columns]
    placeholders = ", ".join(["%s"] * len(all_columns))
    update_set = ", ".join(f"{col} = EXCLUDED.{col}" for col in metrics_columns)
    update_set += ", updated_at = NOW()"
    conflict_clause = ", ".join(conflict_keys)

    insert_sql = f"""
        INSERT INTO {metrics_table} ({", ".join(all_columns)})
        VALUES ({placeholders})
        ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_set}
    """
    conn.execute(insert_sql, [symbol, as_of_date, *metrics_values])


def _get_watchlist_symbols_or_early_return(
    task_id: str | None,
    log_event: str,
    secondary_metric_name: str = "symbols_updated",
) -> tuple[list[str], Any, dict[str, int | str] | None]:
    """Get watchlist symbols or return early response if none found.

    Common boilerplate pattern used by Celery tasks that process watchlist symbols.

    Args:
        task_id: Celery task ID for response
        log_event: Log event name for empty list (e.g., "no_watchlist_symbols_for_health_scores")
        secondary_metric_name: Name of secondary metric in response (default: "symbols_updated")

    Returns:
        Tuple of (symbols_list, storage, early_return_response_or_none)
        If symbols is empty, early_return_response contains the response dict.
        Otherwise, early_return_response is None.
    """
    storage = get_storage()
    symbols = get_watchlist_symbols_cached(storage, account_id=None, ttl_seconds=60)

    if not symbols:
        logger.info(log_event)
        return (
            [],
            storage,
            {
                "task_id": task_id,
                "symbols_processed": 0,
                secondary_metric_name: 0,
                "duration_seconds": 0,
            },
        )

    return symbols, storage, None


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
    with storage.connection() as conn:
        # Find the most recent cache entry for this symbol/source
        result = conn.execute(
            """
            SELECT as_of_date
            FROM reference_cache
            WHERE symbol = %s AND source = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [symbol, source],
        ).fetchone()

        if result is None:
            logger.debug(
                "no_cache_entry_found",
                symbol=symbol,
                source=source,
            )
            return

        as_of_date = result[0]

        # Dual-write using shared helper
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

        _dual_write_metrics(
            conn=conn,
            symbol=symbol,
            as_of_date=as_of_date,
            base_table_update_sql=base_update_sql,
            base_table_params=base_params,
            metrics_table="valuation_metrics",
            metrics_columns=metrics_columns,
            metrics_values=metrics_values,
            conflict_keys=["symbol", "as_of_date"],
        )

        conn.commit()

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
    entries_processed = 0
    entries_updated = 0

    with storage.connection() as conn:
        # Get all cache entries with non-null payloads
        results = conn.execute(
            """
            SELECT symbol, source, payload
            FROM reference_cache
            WHERE payload IS NOT NULL
            ORDER BY symbol, source, as_of_date DESC
            """
        ).fetchall()

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
                # Type guard at line 336 ensures symbol and source are strings
                _update_valuation_metrics(symbol, source, payload)

    return entries_processed, entries_updated


@celery_app.task(name="parse_valuation_metrics", bind=True)
def parse_valuation_metrics(self: Task) -> dict[str, int | str]:
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
    task_id = self.request.id
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


def _upsert_reference_cache(
    storage: Any,
    df: Any,
    source: str,
) -> int:
    """Store reference data in reference_cache table.

    Args:
        storage: PortfolioStorage instance
        df: Polars DataFrame with columns: symbol, as_of_date, payload
        source: Data source identifier (e.g., "yfinance", "alphavantage")

    Returns:
        Number of rows upserted
    """
    rows_upserted = 0
    with storage.connection() as conn:
        for row in df.iter_rows(named=True):
            conn.execute(
                """
                INSERT INTO reference_cache (symbol, as_of_date, payload, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, as_of_date, source)
                DO UPDATE SET payload = EXCLUDED.payload
                """,
                [row["symbol"], row["as_of_date"], row["payload"], source],
            )
            rows_upserted += 1
        conn.commit()
    return rows_upserted


@celery_app.task(
    bind=True,
    name="refresh_yfinance_reference_data",
    max_retries=3,
    autoretry_for=(RequestException, TimeoutError, OperationalError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def refresh_yfinance_reference_data(self: Task) -> dict[str, int | str]:
    """Fetch reference data (including valuation metrics) from yfinance for watchlist symbols.

    Runs daily at 04:00 UTC to refresh fundamental and valuation data.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_processed: Number of symbols attempted
        - symbols_updated: Number of symbols successfully updated
        - duration_seconds: Total execution time
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("yfinance_reference_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = _get_watchlist_symbols_or_early_return(
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

        # Store in reference_cache table using shared helper
        symbols_updated = _upsert_reference_cache(storage, df, "yfinance")

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

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT DISTINCT wi.symbol
            FROM watchlist_items wi
            LEFT JOIN (
                SELECT symbol, MAX(as_of_date) as latest_date
                FROM reference_cache
                WHERE source = 'yfinance'
                GROUP BY symbol
            ) rc ON wi.symbol = rc.symbol
            WHERE rc.symbol IS NULL
               OR rc.latest_date < CURRENT_DATE - INTERVAL '7 days'
            """
        )
        return [str(row[0]) for row in result.fetchall()]


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
    return _upsert_reference_cache(storage, df, "alphavantage")


@celery_app.task(name="refresh_alphavantage_reference_backup", bind=True)
def refresh_alphavantage_reference_backup(self: Task) -> dict[str, int | str]:
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
    task_id = self.request.id
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


@celery_app.task(name="refresh_analyst_revisions", bind=True)
def refresh_analyst_revisions(self: Task) -> dict[str, int | str]:
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
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("analyst_revisions_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = _get_watchlist_symbols_or_early_return(
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


@celery_app.task(name="refresh_financial_health_scores", bind=True)
def refresh_financial_health_scores(self: Task) -> dict[str, int | str]:
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
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("financial_health_scores_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = _get_watchlist_symbols_or_early_return(
            task_id, "no_watchlist_symbols_for_health_scores"
        )
        if early_return:
            return early_return

        logger.info("calculating_financial_health_scores", num_symbols=len(symbols))

        symbols_updated = 0

        with storage.connection() as conn:
            for symbol in symbols:
                try:
                    scores = get_financial_health_scores(symbol)

                    if scores.f_score is not None or scores.z_score is not None:
                        # Prepare score values
                        f_components_json = (
                            json.dumps(scores.f_score_components)
                            if scores.f_score_components
                            else None
                        )
                        score_values = [
                            scores.f_score,
                            f_components_json,
                            scores.z_score,
                            scores.z_score_zone,
                        ]

                        # Dual-write using shared helper
                        base_update_sql = """
                            UPDATE reference_cache
                            SET f_score = %s, f_score_components = %s,
                                z_score = %s, z_score_zone = %s
                            WHERE symbol = %s
                              AND as_of_date = (
                                  SELECT MAX(as_of_date) FROM reference_cache WHERE symbol = %s
                              )
                        """
                        _dual_write_metrics(
                            conn=conn,
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

            conn.commit()

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


@celery_app.task(name="refresh_risk_metrics", bind=True)
def refresh_risk_metrics(self: Task) -> dict[str, int | str]:
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
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("risk_metrics_refresh_started", task_id=task_id)

    try:
        # Get watchlist symbols with early return if none found
        symbols, storage, early_return = _get_watchlist_symbols_or_early_return(
            task_id, "no_watchlist_symbols_for_risk_metrics"
        )
        if early_return:
            return early_return

        logger.info("calculating_risk_metrics", num_symbols=len(symbols))

        symbols_updated = 0
        as_of_date = dt.date.today()

        with storage.connection() as conn:
            for symbol in symbols:
                try:
                    # Calculate VaR/CVaR
                    var_result = calculate_symbol_var(storage, symbol)

                    # Calculate multi-window betas
                    beta_result = calculate_symbol_beta(storage, symbol)

                    # Skip if no valid metrics
                    if var_result.var_95 is None and beta_result.beta_90d is None:
                        continue

                    # Upsert into symbol_risk_metrics
                    conn.execute(
                        """
                        INSERT INTO symbol_risk_metrics (
                            symbol, as_of_date,
                            var_95, var_99, cvar_95, cvar_99,
                            beta_90d, beta_1y, beta_2y, r_squared_1y,
                            observations
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, as_of_date)
                        DO UPDATE SET
                            var_95 = EXCLUDED.var_95,
                            var_99 = EXCLUDED.var_99,
                            cvar_95 = EXCLUDED.cvar_95,
                            cvar_99 = EXCLUDED.cvar_99,
                            beta_90d = EXCLUDED.beta_90d,
                            beta_1y = EXCLUDED.beta_1y,
                            beta_2y = EXCLUDED.beta_2y,
                            r_squared_1y = EXCLUDED.r_squared_1y,
                            observations = EXCLUDED.observations
                        """,
                        [
                            symbol,
                            as_of_date.isoformat(),
                            var_result.var_95,
                            var_result.var_99,
                            var_result.cvar_95,
                            var_result.cvar_99,
                            beta_result.beta_90d,
                            beta_result.beta_1y,
                            beta_result.beta_2y,
                            beta_result.r_squared_1y,
                            var_result.observations,
                        ],
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

            conn.commit()

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
