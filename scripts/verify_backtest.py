#!/usr/bin/env python3
"""Quick backtest verification - runs a short backtest and verifies completion."""
import sys
from datetime import date, timedelta
from decimal import Decimal

from app.storage.facade import PortfolioStorage
from app.backtest.replay import replay_backtest, Strategy
from app.storage.connection import ConnectionManager

def main():
    print("=== Running Quick Backtest Verification ===\n")

    storage = PortfolioStorage()
    conn_mgr = ConnectionManager.get_instance()

    # Run a 30-day backtest
    end = date.today()
    start = end - timedelta(days=30)

    print(f"Running backtest: AAPL from {start} to {end}")
    print("This should complete quickly with the bulk data optimization...\n")

    try:
        # Use the simple Strategy protocol implementation
        class TestStrategy(Strategy):
            def should_enter(self, date, price, indicators):
                # Simple entry: buy if RSI < 40
                rsi = indicators.get("rsi_14")
                return rsi is not None and rsi < 40

            def should_exit(self, date, entry_price, current_price, days_held, indicators):
                # Simple exit: sell if RSI > 60 or 5% profit
                rsi = indicators.get("rsi_14")
                profit_pct = ((current_price - entry_price) / entry_price) * 100
                return (rsi is not None and rsi > 60) or profit_pct > 5

        result = replay_backtest(
            storage=conn_mgr,
            run_id="quick-verify",
            symbol="AAPL",
            start_date=start,
            end_date=end,
            initial_capital=Decimal("100000"),
            strategy=strategy,
            sizing_method="fixed_dollars",
            size_value=Decimal("10000")
        )

        print("\n✅ Backtest completed successfully!")
        print(f"Final equity: ${result.cash:.2f}")
        print(f"Total trades: {len(result.trades)}")
        print(f"Days simulated: {len(result.equity_curve)}")

        return 0

    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
