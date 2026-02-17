#!/usr/bin/env python3
"""Populate historical data and technical indicators for watchlist symbols.

This script:
1. Fetches all symbols from the watchlist
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
from app.tasks import (
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

    # Step 1: Get all watchlist symbols
    logger.info("fetching_watchlist_symbols")
    with storage.connection() as conn:
        result = conn.execute("SELECT DISTINCT symbol FROM watchlist_items").fetchall()
        symbols = [str(row[0]) for row in result]

    if not symbols:
        logger.warning("no_watchlist_symbols_found")
        print("No symbols found in watchlist. Please add symbols first.")
        return

    logger.info("found_symbols", count=len(symbols), symbols=symbols)
    print(f"\nFound {len(symbols)} symbols in watchlist: {', '.join(symbols)}")

    # Step 2: Ingest historical OHLCV data (200 days)
    print(f"\n[1/4] Ingesting 200 days of historical data for {len(symbols)} symbols...")
    logger.info("ingesting_historical_data", symbols=symbols, days=200)

    ingest_result = ingest_historical_ohlcv(symbols=symbols, days=200)

    print(
        f"  ✓ Ingested {ingest_result['rows_inserted']} rows in {ingest_result['duration_seconds']:.2f}s"
    )
    print(f"  ✓ Errors: {ingest_result['errors']}")
    logger.info("ingest_completed", **ingest_result)

    # Step 3: Calculate technical indicators
    print(f"\n[2/4] Calculating technical indicators for {len(symbols)} symbols...")
    logger.info("calculating_technical_indicators", symbols=symbols)

    indicators_result = update_technical_indicators(symbols=symbols)

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
                wi.symbol,
                ROUND(ws.price_score, 2) as price,
                ROUND(ws.technical_score, 2) as technical,
                ROUND(ws.overall_score, 2) as overall
            FROM watchlist_snapshots ws
            JOIN watchlist_items wi ON ws.item_id = wi.id
            ORDER BY wi.symbol
            """
        ).fetchall()

        if score_check:
            print("\n  Scores calculated successfully:")
            print("  " + "-" * 60)
            print(f"  {'Symbol':<10} {'Price':<10} {'Technical':<12} {'Overall':<10}")
            print("  " + "-" * 60)
            for row in score_check:
                symbol, price, technical, overall = row
                print(f"  {symbol:<10} {price:<10} {technical:<12} {overall:<10}")
            print("  " + "-" * 60)
        else:
            print("  ⚠️  No scores found! Check logs for errors.")

    logger.info("populate_watchlist_data_completed")
    print("\n✓ Data population complete!")


if __name__ == "__main__":
    main()
