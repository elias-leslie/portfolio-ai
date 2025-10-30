#!/usr/bin/env python3
"""Populate historical data and technical indicators for watchlist tickers.

This script:
1. Fetches all tickers from the watchlist
2. Ingests 200 days of historical OHLCV data
3. Calculates technical indicators
4. Refreshes watchlist scores
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# ruff: noqa: E402 - Imports must come after path manipulation
from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.agent_tasks import (
    ingest_historical_ohlcv,
    refresh_watchlist_scores_task,
    update_technical_indicators,
)

logger = get_logger(__name__)


def main() -> None:
    """Main execution function."""
    logger.info("populate_watchlist_data_started")

    # Initialize storage
    storage = get_storage()

    # Step 1: Get all watchlist tickers
    logger.info("fetching_watchlist_tickers")
    with storage.connection() as conn:
        result = conn.execute("SELECT DISTINCT ticker FROM watchlist_items").fetchall()
        tickers = [row[0] for row in result]

    if not tickers:
        logger.warning("no_watchlist_tickers_found")
        print("No tickers found in watchlist. Please add tickers first.")
        return

    logger.info("found_tickers", count=len(tickers), tickers=tickers)
    print(f"\nFound {len(tickers)} tickers in watchlist: {', '.join(tickers)}")

    # Step 2: Ingest historical OHLCV data (200 days)
    print(f"\n[1/4] Ingesting 200 days of historical data for {len(tickers)} tickers...")
    logger.info("ingesting_historical_data", tickers=tickers, days=200)

    ingest_result = ingest_historical_ohlcv(tickers=tickers, days=200)

    print(
        f"  ✓ Ingested {ingest_result['rows_inserted']} rows in {ingest_result['duration_seconds']:.2f}s"
    )
    print(f"  ✓ Errors: {ingest_result['errors']}")
    logger.info("ingest_completed", **ingest_result)

    # Step 3: Calculate technical indicators
    print(f"\n[2/4] Calculating technical indicators for {len(tickers)} tickers...")
    logger.info("calculating_technical_indicators", tickers=tickers)

    indicators_result = update_technical_indicators(tickers=tickers)

    print(f"  ✓ Success: {indicators_result['success']}")
    print(f"  ✓ Failed: {indicators_result['failed']}")
    logger.info("indicators_completed", **indicators_result)

    # Step 4: Refresh watchlist scores
    print("\n[3/4] Refreshing watchlist scores...")
    logger.info("refreshing_watchlist_scores")

    refresh_result = refresh_watchlist_scores_task(account_id=None)

    print(f"  ✓ Processed: {refresh_result.get('processed', 0)}")
    print(f"  ✓ Updated: {refresh_result.get('updated', 0)}")
    print(f"  ✓ Errors: {refresh_result.get('errors', 0)}")
    logger.info("refresh_completed", **refresh_result)

    # Step 5: Verify scores were calculated
    print("\n[4/4] Verifying scores...")
    with storage.connection() as conn:
        score_check = conn.execute(
            """
            SELECT
                ticker,
                ROUND(price_score, 2) as price,
                ROUND(technical_score, 2) as technical,
                ROUND(overall_score, 2) as overall
            FROM watchlist_snapshots
            WHERE item_id IN (SELECT id FROM watchlist_items)
            ORDER BY ticker
            """
        ).fetchall()

        if score_check:
            print("\n  Scores calculated successfully:")
            print("  " + "-" * 60)
            print(f"  {'Ticker':<10} {'Price':<10} {'Technical':<12} {'Overall':<10}")
            print("  " + "-" * 60)
            for row in score_check:
                ticker, price, technical, overall = row
                print(f"  {ticker:<10} {price:<10} {technical:<12} {overall:<10}")
            print("  " + "-" * 60)
        else:
            print("  ⚠️  No scores found! Check logs for errors.")

    logger.info("populate_watchlist_data_completed")
    print("\n✓ Data population complete!")


if __name__ == "__main__":
    main()
