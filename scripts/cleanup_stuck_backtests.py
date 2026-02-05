from app.storage.facade import PortfolioStorage
from app.logging_config import get_logger

logger = get_logger(__name__)


def cleanup_stuck_backtests():
    storage = PortfolioStorage()

    with storage.connection() as conn:
        # Find running backtests
        running = conn.execute("""
            SELECT id, symbol, created_at
            FROM backtest_runs
            WHERE status = 'running'
            ORDER BY created_at DESC
        """).fetchall()

        print(f"Found {len(running)} stuck backtests in 'running' state:")
        for row in running:
            print(f"  - {row[0]}: {row[1]} (created {row[2]})")

        if running:
            # Mark all as failed except the most recent one (in case it's legitimately running)
            print(
                f"\nMarking {len(running)} backtests as 'failed' (stuck from testing)..."
            )
            conn.execute("""
                UPDATE backtest_runs
                SET status = 'failed',
                    error_message = 'Marked as failed - stuck during testing',
                    completed_at = NOW()
                WHERE status = 'running'
            """)
            conn.commit()
            print("✅ Cleanup complete")


if __name__ == "__main__":
    cleanup_stuck_backtests()
