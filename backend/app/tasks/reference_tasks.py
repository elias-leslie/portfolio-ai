"""Celery tasks for reference data maintenance.

This module defines background tasks for maintaining cached reference data,
including extraction of valuation metrics from JSON payloads and enriching
the database with structured metrics for efficient querying.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.alphavantage_source import AlphaVantageSource
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage

logger = get_logger(__name__)


def _extract_valuation_metrics(payload: dict[str, Any]) -> dict[str, float | None]:
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

    # Helper to parse string to float
    def parse_float(value: Any) -> float | None:
        if value is None or value in {"None", ""}:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

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


def _update_valuation_metrics(ticker: str, source: str, payload: dict[str, Any]) -> None:
    """Update valuation metrics for a single ticker/source combination.

    Args:
        ticker: Stock ticker symbol
        source: Data source (e.g., "fundamentals")
        payload: JSON payload dict containing valuation data
    """
    metrics = _extract_valuation_metrics(payload)

    # Only update if we found at least one metric
    if not any(v is not None for v in metrics.values()):
        logger.debug(
            "no_valuation_metrics_found",
            ticker=ticker,
            source=source,
        )
        return

    storage = get_storage()
    with storage.connection() as conn:
        # Find the most recent cache entry for this ticker/source
        result = conn.execute(
            """
            SELECT as_of_date
            FROM reference_cache
            WHERE ticker = %s AND source = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [ticker, source],
        ).fetchone()

        if result is None:
            logger.debug(
                "no_cache_entry_found",
                ticker=ticker,
                source=source,
            )
            return

        as_of_date = result[0]

        # Update the metrics using composite primary key
        conn.execute(
            """
            UPDATE reference_cache
            SET pe_ratio_trailing = %s,
                pe_ratio_forward = %s,
                ps_ratio = %s,
                pb_ratio = %s,
                peg_ratio = %s,
                dividend_yield = %s,
                payout_ratio = %s
            WHERE ticker = %s AND source = %s AND as_of_date = %s
            """,
            [
                metrics["pe_ratio_trailing"],
                metrics["pe_ratio_forward"],
                metrics["ps_ratio"],
                metrics["pb_ratio"],
                metrics["peg_ratio"],
                metrics["dividend_yield"],
                metrics["payout_ratio"],
                ticker,
                source,
                as_of_date,
            ],
        )
        conn.commit()

        logger.info(
            "valuation_metrics_updated",
            ticker=ticker,
            source=source,
            metrics_count=sum(1 for v in metrics.values() if v is not None),
        )


@celery_app.task(name="parse_valuation_metrics", bind=True)  # type: ignore[misc]
def parse_valuation_metrics(self) -> dict[str, int | str]:  # type: ignore[no-untyped-def]
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
        storage = get_storage()
        entries_processed = 0
        entries_updated = 0

        with storage.connection() as conn:
            # Get all cache entries with non-null payloads
            results = conn.execute(
                """
                SELECT ticker, source, payload
                FROM reference_cache
                WHERE payload IS NOT NULL
                ORDER BY ticker, source, as_of_date DESC
                """
            ).fetchall()

            logger.info(
                "valuation_metrics_found_entries",
                total_entries=len(results),
            )

            # Track which ticker/source combinations we've processed
            # (only process most recent for each pair)
            processed_pairs: set[tuple[str, str]] = set()

            for ticker, source, payload_json in results:
                pair = (ticker, source)

                # Skip if we've already processed this ticker/source combo
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
                        ticker=ticker,
                        source=source,
                    )
                    continue

                # Extract and update metrics
                metrics = _extract_valuation_metrics(payload)

                # Only count as "updated" if we found at least one metric
                if any(v is not None for v in metrics.values()):
                    entries_updated += 1
                    _update_valuation_metrics(ticker, source, payload)

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


@celery_app.task(name="refresh_yfinance_reference_data", bind=True)  # type: ignore[misc]
def refresh_yfinance_reference_data(self) -> dict[str, int | str]:  # type: ignore[no-untyped-def]
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
        storage = get_storage()

        # Get all watchlist symbols
        with storage.connection() as conn:
            result = conn.execute("SELECT DISTINCT symbol FROM watchlist_items")
            symbols = [row[0] for row in result.fetchall()]

        if not symbols:
            logger.warning("no_watchlist_symbols_found")
            return {
                "task_id": task_id,
                "symbols_processed": 0,
                "symbols_updated": 0,
                "duration_seconds": 0,
            }

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

        # Store in reference_cache table
        symbols_updated = len(df)

        # DataFrame should have: ticker, as_of_date, payload, source
        # Insert into reference_cache
        with storage.connection() as conn:
            for row in df.iter_rows(named=True):
                conn.execute(
                    """
                    INSERT INTO reference_cache (ticker, as_of_date, payload, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ticker, as_of_date, source)
                    DO UPDATE SET payload = EXCLUDED.payload
                    """,
                    [row["ticker"], row["as_of_date"], row["payload"], "yfinance"],
                )
            conn.commit()

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


@celery_app.task(name="refresh_alphavantage_reference_backup", bind=True)  # type: ignore[misc]
def refresh_alphavantage_reference_backup(self) -> dict[str, int | str]:  # type: ignore[no-untyped-def]
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
        storage = get_storage()

        # Find symbols needing backup (no yfinance data or >7 days old)
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT DISTINCT wi.symbol
                FROM watchlist_items wi
                LEFT JOIN (
                    SELECT ticker, MAX(as_of_date) as latest_date
                    FROM reference_cache
                    WHERE source = 'yfinance'
                    GROUP BY ticker
                ) rc ON wi.symbol = rc.ticker
                WHERE rc.ticker IS NULL
                   OR rc.latest_date < CURRENT_DATE - INTERVAL '7 days'
                """
            )
            symbols = [row[0] for row in result.fetchall()]

        if not symbols:
            logger.info("no_symbols_need_alphavantage_backup")
            return {
                "task_id": task_id,
                "symbols_processed": 0,
                "symbols_updated": 0,
                "duration_seconds": 0,
            }

        logger.info("fetching_alphavantage_backup", num_symbols=len(symbols))

        # Fetch from Alpha Vantage
        source = AlphaVantageSource()
        as_of = dt.date.today()

        df = source.fetch_reference_payload(symbols, as_of)

        if df is None or df.is_empty():
            logger.warning("alphavantage_backup_fetch_failed")
            return {
                "task_id": task_id,
                "symbols_processed": len(symbols),
                "symbols_updated": 0,
                "duration_seconds": (dt.datetime.now(dt.UTC) - start_time).total_seconds(),
            }

        # Store in reference_cache
        symbols_updated = len(df)

        with storage.connection() as conn:
            for row in df.iter_rows(named=True):
                conn.execute(
                    """
                    INSERT INTO reference_cache (ticker, as_of_date, payload, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ticker, as_of_date, source)
                    DO UPDATE SET payload = EXCLUDED.payload
                    """,
                    [row["ticker"], row["as_of_date"], row["payload"], "alphavantage"],
                )
            conn.commit()

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
