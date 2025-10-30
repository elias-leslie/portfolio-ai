#!/usr/bin/env python3
"""Manually trigger watchlist data refresh.

This script:
1. Gets all watchlist tickers from the database
2. Triggers historical OHLCV data ingestion
3. Calculates technical indicators
4. Refreshes watchlist scores

Usage:
    python scripts/trigger_watchlist_refresh.py [--initial]

Options:
    --initial  - Fetch 200 days of data (first run), default is 5 days (refresh)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add backend directory to path and change to backend directory
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Change working directory to backend (required for relative db_path to work)
import os

os.chdir(backend_dir)

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
    parser = argparse.ArgumentParser(description="Trigger watchlist data refresh")
    parser.add_argument(
        "--initial",
        action="store_true",
        help="Fetch 200 days of data (initial run), default is 5 days (refresh)",
    )
    args = parser.parse_args()

    days = 200 if args.initial else 5
    mode = "INITIAL" if args.initial else "REFRESH"

    print(f"\n{'='*60}")
    print(f"  Watchlist Data {mode} ({days} days)")
    print(f"{'='*60}\n")

    # Initialize storage
    storage = get_storage()

    # Step 1: Get all watchlist tickers
    print("[1/5] Fetching watchlist tickers...")
    result = storage.query("SELECT DISTINCT symbol FROM watchlist_items")

    # Handle Polars DataFrame result
    if result.is_empty():
        print("❌ No tickers found in watchlist. Please add tickers first.")
        print("   You can add tickers via:")
        print("   - The watchlist UI at http://localhost:3000/watchlist")
        print("   - The API endpoint: POST /api/watchlist")
        sys.exit(1)

    tickers = result.get_column("symbol").to_list()

    print(f"✓ Found {len(tickers)} tickers: {', '.join(tickers)}\n")

    # Step 2: Trigger historical OHLCV ingestion
    print(f"[2/5] Triggering historical data ingestion ({days} days)...")
    try:
        task_result = ingest_historical_ohlcv.delay(tickers=tickers, days=days)
        print(f"✓ Task queued: {task_result.id}")
        print("  Waiting 30s for ingestion to complete...")
        time.sleep(30)
    except Exception as e:
        print(f"❌ Failed to queue ingestion task: {e}")
        print("  Make sure Redis and Celery worker are running!")
        sys.exit(1)

    # Step 3: Trigger technical indicators calculation
    print("\n[3/5] Triggering technical indicators calculation...")
    try:
        task_result = update_technical_indicators.delay(tickers=tickers)
        print(f"✓ Task queued: {task_result.id}")
        print("  Waiting 20s for calculations to complete...")
        time.sleep(20)
    except Exception as e:
        print(f"❌ Failed to queue indicators task: {e}")
        sys.exit(1)

    # Step 4: Trigger watchlist score refresh
    print("\n[4/5] Triggering watchlist score refresh...")
    try:
        task_result = refresh_watchlist_scores_task.delay(account_id=None)
        print(f"✓ Task queued: {task_result.id}")
        print("  Waiting 10s for scores to refresh...")
        time.sleep(10)
    except Exception as e:
        print(f"❌ Failed to queue refresh task: {e}")
        sys.exit(1)

    # Step 5: Verify results
    print("\n[5/5] Verifying results...")

    # Check day_bars
    bars_result = storage.query("SELECT COUNT(*) as count FROM day_bars")
    bars_count = bars_result[0][0]
    print(f"  Historical bars in database: {bars_count}")

    # Check technical_indicators
    indicators_result = storage.query("SELECT COUNT(*) as count FROM technical_indicators")
    indicators_count = indicators_result[0][0]
    print(f"  Technical indicators calculated: {indicators_count}")

    # Check watchlist scores
    scores_result = storage.query(
        """
        SELECT
            wi.symbol,
            COALESCE(ROUND(ws.fundamental_score, 2), 0) as price,
            COALESCE(ROUND(ws.technical_score, 2), 0) as technical,
            COALESCE(ROUND(ws.overall_score, 2), 0) as overall
        FROM watchlist_items wi
        LEFT JOIN (
            SELECT DISTINCT ON (item_id) *
            FROM watchlist_snapshots
            ORDER BY item_id, fetched_at DESC
        ) ws ON wi.id = ws.item_id
        ORDER BY wi.symbol
        """
    )

    print("\n  Watchlist Scores:")
    print("  " + "-" * 56)
    print(f"  {'Ticker':<10} {'Price':<12} {'Technical':<14} {'Overall':<10}")
    print("  " + "-" * 56)
    for row in scores_result:
        symbol, price, technical, overall = row
        print(f"  {symbol:<10} {price:<12.2f} {technical:<14.2f} {overall:<10.2f}")
    print("  " + "-" * 56)

    print(f"\n{'='*60}")
    print(f"  ✓ Watchlist data {mode.lower()} complete!")
    print(f"{'='*60}\n")

    if all(row[3] == 0 for row in scores_result):
        print("⚠️  All scores are 0. Check Celery worker logs for errors.")
        print("   Make sure Redis and Celery worker are running:")
        print("   - redis-server")
        print("   - celery -A app.celery_app worker --loglevel=info\n")


if __name__ == "__main__":
    main()
