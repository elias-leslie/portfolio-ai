#!/usr/bin/env python3
"""Backfill Fear & Greed historical data.

This script populates fear_greed_inputs and fear_greed_daily tables
with historical data going back to the available day_bars data.

Usage:
    cd ~/portfolio-ai/backend
    .venv/bin/python scripts/backfill_fear_greed.py [--days 1500]
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.indicators.fear_greed import (
    _calculate_percentile_breadth,
    _calculate_percentile_credit,
    _calculate_percentile_momentum,
    _calculate_percentile_rsi,
    _calculate_percentile_vix,
    _get_fear_greed_inputs,
    _store_components_and_score,
)
from app.tasks.market_data.fear_greed_pipeline import (
    _calculate_and_upsert_inputs,
    _fetch_market_indicators,
    _fetch_spy_data,
)

logger = get_logger(__name__)


def backfill_inputs(days: int = 1500) -> int:
    """Backfill fear_greed_inputs table with historical data.

    Args:
        days: Number of days to backfill (default 1500 for ~4 years after SMA warmup)

    Returns:
        Number of records updated
    """
    print(f"Backfilling fear_greed_inputs for {days} days...")

    storage = get_storage()
    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days)
    # Need extra 200 days for SMA calculation warmup
    data_start = start_date - dt.timedelta(days=250)

    # Fetch SPY data
    spy_dict = _fetch_spy_data(storage, data_start, end_date)
    print(f"  Fetched {len(spy_dict)} SPY data points")

    if len(spy_dict) < 200:
        print("  ERROR: Insufficient SPY data (need >= 200 days)")
        return 0

    dates = sorted(spy_dict.keys())

    # Fetch market indicators
    vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback = _fetch_market_indicators(
        storage, data_start, end_date
    )
    print(f"  Fetched {len(vix_data)} VIX data points")
    print(f"  Fetched {len(hy_spread_dict)} HY spread data points")

    # Calculate and upsert inputs for each date
    updates_count = _calculate_and_upsert_inputs(
        storage,
        spy_dict,
        dates,
        start_date,
        vix_data,
        hy_spread_dict,
        vix_estimate,
        hy_spread_fallback,
    )

    print(f"  Updated {updates_count} fear_greed_inputs records")
    return updates_count


def backfill_scores() -> int:
    """Backfill fear_greed_daily table by calculating scores for all inputs.

    Returns:
        Number of scores calculated
    """
    print("Backfilling fear_greed_daily scores...")

    storage = get_storage()

    # Get all dates with inputs but no scores
    with storage.connection() as conn:
        result = conn.execute("""
            SELECT i.as_of_date
            FROM fear_greed_inputs i
            LEFT JOIN fear_greed_daily d ON i.as_of_date = d.as_of_date
            WHERE d.as_of_date IS NULL
              AND i.vix_close IS NOT NULL
              AND i.spy_close IS NOT NULL
            ORDER BY i.as_of_date ASC
        """)
        dates_to_process = [row[0] for row in result.fetchall()]

    print(f"  Found {len(dates_to_process)} dates needing score calculation")

    if not dates_to_process:
        print("  No dates to process")
        return 0

    scores_calculated = 0
    window_days = 252

    for i, as_of_date in enumerate(dates_to_process):
        date_str = as_of_date.isoformat() if isinstance(as_of_date, dt.date) else str(as_of_date)

        try:
            with storage.connection() as conn:
                # Get inputs for this date
                _, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct = (
                    _get_fear_greed_inputs(conn, date_str)
                )

                # Calculate percentiles
                vix_pct = _calculate_percentile_vix(conn, date_str, vix_close, window_days)
                momentum_pct = _calculate_percentile_momentum(
                    conn, date_str, spy_close, spy_sma_200, window_days
                )
                rsi_pct = _calculate_percentile_rsi(conn, date_str, rsi_14, window_days)
                credit_pct = _calculate_percentile_credit(conn, date_str, hy_spread, window_days)
                breadth_percentile = _calculate_percentile_breadth(
                    conn, date_str, breadth_pct, window_days
                )

                # Store components and calculate score (return values stored in DB)
                _store_components_and_score(
                    conn,
                    date_str,
                    vix_pct,
                    momentum_pct,
                    rsi_pct,
                    credit_pct,
                    breadth_percentile,
                    window_days,
                )

                conn.commit()
                scores_calculated += 1

                # Progress update every 100 dates
                if (i + 1) % 100 == 0:
                    print(f"  Processed {i + 1}/{len(dates_to_process)} dates...")

        except Exception as e:
            print(f"  Warning: Failed to calculate score for {date_str}: {e}")
            continue

    print(f"  Calculated {scores_calculated} fear_greed_daily scores")
    return scores_calculated


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Fear & Greed historical data")
    parser.add_argument(
        "--days",
        type=int,
        default=1500,
        help="Number of days to backfill (default: 1500 for ~4 years)",
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Only calculate scores (skip input population)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Fear & Greed Backfill")
    print("=" * 60)

    if not args.scores_only:
        inputs_count = backfill_inputs(args.days)
        print()

    scores_count = backfill_scores()

    print()
    print("=" * 60)
    print("Backfill complete!")
    if not args.scores_only:
        print(f"  Inputs populated: {inputs_count}")
    print(f"  Scores calculated: {scores_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
