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
from app.storage import get_storage

logger = get_logger(__name__)


def _extract_valuation_metrics(payload: dict[str, Any]) -> dict[str, float | None]:
    """Extract valuation metrics from JSON payload.

    Maps JSON fields to database columns:
    - trailingPE -> pe_ratio_trailing
    - forwardPE -> pe_ratio_forward
    - priceToSalesTrailing12Months -> ps_ratio
    - priceToBook -> pb_ratio
    - pegRatio -> peg_ratio
    - dividendYield -> dividend_yield
    - payoutRatio -> payout_ratio

    Args:
        payload: JSON payload dict from reference_cache

    Returns:
        Dict with extracted metrics (values are None if not in payload)
    """
    return {
        "pe_ratio_trailing": payload.get("trailingPE"),
        "pe_ratio_forward": payload.get("forwardPE"),
        "ps_ratio": payload.get("priceToSalesTrailing12Months"),
        "pb_ratio": payload.get("priceToBook"),
        "peg_ratio": payload.get("pegRatio"),
        "dividend_yield": payload.get("dividendYield"),
        "payout_ratio": payload.get("payoutRatio"),
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
