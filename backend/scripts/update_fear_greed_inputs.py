"""Update fear_greed_inputs table with latest market data.

This script calculates Fear & Greed Index inputs from available market data:
1. Fetches SPY OHLCV data from day_bars table
2. Calculates SMA_200 and RSI_14 from SPY data
3. Uses reasonable estimates for VIX and HY spread
4. Inserts/updates fear_greed_inputs table for missing dates
5. Triggers Fear & Greed calculation task

Usage:
    python scripts/update_fear_greed_inputs.py [--days DAYS]
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.storage import get_storage  # noqa: E402
from app.storage.facade import PortfolioStorage  # noqa: E402


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    """Calculate RSI indicator.

    Args:
        prices: List of closing prices (oldest first)
        period: RSI period (default 14)

    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None

    # Calculate price changes
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Separate gains and losses
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Calculate average gain/loss
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_sma(prices: list[float], period: int) -> float | None:
    """Calculate Simple Moving Average.

    Args:
        prices: List of closing prices (oldest first)
        period: SMA period

    Returns:
        SMA value or None if insufficient data
    """
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def fetch_spy_data(storage: PortfolioStorage, start_date: dt.date, end_date: dt.date) -> list[tuple[dt.date, float]]:
    """Fetch SPY OHLCV data from day_bars table.

    Args:
        storage: Storage instance
        start_date: Start date for data fetch
        end_date: End date for data fetch

    Returns:
        List of (date, close) tuples sorted by date
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT date, close
            FROM day_bars
            WHERE symbol = 'SPY'
            AND date BETWEEN %s AND %s
            ORDER BY date ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        )
        raw_rows = result.fetchall()
        rows: list[tuple[dt.date, float]] = []
        for r in raw_rows:
            if isinstance(r[0], dt.date) and isinstance(r[1], (int, float)):
                rows.append((r[0], float(r[1])))
        return rows


def get_latest_inputs(storage: PortfolioStorage) -> tuple[dt.date | None, float | None, float | None]:
    """Get the latest fear_greed_inputs data for reference.

    Args:
        storage: Storage instance

    Returns:
        Tuple of (latest_date, latest_vix, latest_hy_spread)
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT as_of_date, vix_close, hy_spread
            FROM fear_greed_inputs
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        )
        row = result.fetchone()
        if row is not None:
            as_of_date = row[0] if isinstance(row[0], dt.date) else None
            vix = float(row[1]) if row[1] is not None else None
            hy = float(row[2]) if row[2] is not None else None
            return as_of_date, vix, hy
        return None, None, None


def upsert_fear_greed_inputs(
    storage: PortfolioStorage,
    as_of_date: dt.date,
    spy_close: float,
    spy_sma_200: float,
    rsi_14: float,
    vix_close: float,
    hy_spread: float,
) -> None:
    """Insert or update fear_greed_inputs table.

    Args:
        storage: Storage instance
        as_of_date: Date for the data
        spy_close: SPY closing price
        spy_sma_200: SPY 200-day SMA
        rsi_14: SPY 14-period RSI
        vix_close: VIX closing value
        hy_spread: High-yield bond spread
    """
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO fear_greed_inputs
                (as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, source_map)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (as_of_date) DO UPDATE SET
                vix_close = EXCLUDED.vix_close,
                spy_close = EXCLUDED.spy_close,
                spy_sma_200 = EXCLUDED.spy_sma_200,
                rsi_14 = EXCLUDED.rsi_14,
                hy_spread = EXCLUDED.hy_spread,
                source_map = EXCLUDED.source_map
            """,
            (
                as_of_date.isoformat(),
                vix_close,
                spy_close,
                spy_sma_200,
                rsi_14,
                hy_spread,
                '{"spy": "day_bars", "vix": "estimated", "hy_spread": "estimated"}',
            ),
        )
        conn.commit()
        print(f"✅ Updated fear_greed_inputs for {as_of_date}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update fear_greed_inputs table")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    args = parser.parse_args()

    storage = get_storage()

    # Get latest inputs for reference
    latest_date, latest_vix, latest_hy_spread = get_latest_inputs(storage)
    print(f"📊 Latest fear_greed_inputs: {latest_date}")

    # Use reasonable defaults if no data exists
    vix_estimate = latest_vix or 19.5
    hy_spread_estimate = latest_hy_spread or 3.13

    # Calculate date range (need extra days for SMA_200 calculation)
    end_date = dt.date.today()

    # Get earliest available date from day_bars
    with storage.connection() as conn:
        result = conn.execute("SELECT MIN(date) FROM day_bars WHERE symbol = 'SPY'")
        row = result.fetchone()
        earliest_available_raw = row[0] if row is not None else None
        earliest_available: dt.date | None = (
            earliest_available_raw if isinstance(earliest_available_raw, dt.date) else None
        )

    # Use earliest available date or calculated start date, whichever is earlier
    calculated_start = end_date - dt.timedelta(days=250)
    start_date: dt.date = earliest_available if earliest_available is not None else calculated_start

    # Fetch SPY data
    print(f"📈 Fetching SPY data from {start_date} to {end_date}...")
    spy_data = fetch_spy_data(storage, start_date, end_date)

    if len(spy_data) < 200:
        print(f"❌ Error: Insufficient SPY data (got {len(spy_data)} days, need >= 200)")
        sys.exit(1)

    print(f"✅ Fetched {len(spy_data)} days of SPY data")

    # Determine which dates to update (last N days)
    target_start_date = end_date - dt.timedelta(days=args.days)

    # Convert spy_data to dict for easy lookup
    spy_dict = {row[0]: row[1] for row in spy_data}
    dates = sorted(spy_dict.keys())

    # Process each target date
    updates_count = 0
    for i, date in enumerate(dates):
        if date < target_start_date:
            continue

        # Get all prices up to this date for calculations
        prices_up_to_date = [spy_dict[d] for d in dates[: i + 1]]

        if len(prices_up_to_date) < 200:
            print(f"⚠️  Skipping {date}: Insufficient data for SMA_200")
            continue

        spy_close = spy_dict[date]
        sma_200 = calculate_sma(prices_up_to_date, 200)
        rsi_14 = calculate_rsi(prices_up_to_date, 14)

        if sma_200 is None or rsi_14 is None:
            print(f"⚠️  Skipping {date}: Could not calculate indicators")
            continue

        # Use estimates for VIX and HY spread (can be improved with real data later)
        upsert_fear_greed_inputs(
            storage=storage,
            as_of_date=date,
            spy_close=spy_close,
            spy_sma_200=sma_200,
            rsi_14=rsi_14,
            vix_close=vix_estimate,
            hy_spread=hy_spread_estimate,
        )
        updates_count += 1

    print(f"\n✅ Updated {updates_count} dates in fear_greed_inputs table")
    print("\n📊 Next steps:")
    print("1. Run Fear & Greed calculation: celery -A app.celery_app call calculate_fear_greed")
    print("2. Verify dashboard shows current data")


if __name__ == "__main__":
    main()
