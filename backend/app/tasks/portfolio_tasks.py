"""Portfolio monitoring and drawdown tracking tasks.

GAP-023: Daily portfolio snapshot task for drawdown tracking.
Runs daily at 21:30 UTC (4:30 PM ET, 30 min after market close).
"""

from __future__ import annotations

from typing import Any

from celery import Task, shared_task

from app.logging_config import get_logger
from app.portfolio.drawdown import (
    calculate_drawdown_metrics,
    save_portfolio_snapshot,
)
from app.storage import PortfolioStorage

logger = get_logger(__name__)


@shared_task(
    name="save_portfolio_snapshots",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def save_portfolio_snapshots_task(self: Task[[], dict[str, Any]]) -> dict[str, Any]:
    """Save daily equity snapshots for all portfolio accounts.

    This task:
    1. Gets all portfolio accounts
    2. For each account, calculates current equity
    3. Saves snapshot with drawdown from peak
    4. Logs warnings for accounts with high drawdown

    Returns:
        dict with accounts_processed, snapshots_saved, warnings
    """
    storage = PortfolioStorage()

    try:
        # Get all portfolio accounts
        accounts_query = """
            SELECT id, name FROM portfolio_accounts
            WHERE is_active = true OR is_active IS NULL
        """
        accounts_result = storage.query(accounts_query, [])

        if accounts_result.is_empty():
            logger.info("portfolio_snapshots_no_accounts")
            return {
                "accounts_processed": 0,
                "snapshots_saved": 0,
                "warnings": [],
            }

        accounts_processed = 0
        snapshots_saved = 0
        warnings = []

        for row in accounts_result.iter_rows(named=True):
            account_id = row["id"]
            account_name = row["name"] or account_id

            try:
                # Save snapshot
                save_portfolio_snapshot(storage, account_id)
                snapshots_saved += 1

                # Check drawdown for warnings
                metrics = calculate_drawdown_metrics(storage, account_id)
                if metrics.current_drawdown_pct >= 7.5:
                    warning_msg = (
                        f"Account '{account_name}' ({account_id}): "
                        f"{metrics.current_drawdown_pct:.1f}% drawdown"
                    )
                    warnings.append(warning_msg)
                    logger.warning(
                        "portfolio_high_drawdown",
                        account_id=account_id,
                        account_name=account_name,
                        drawdown_pct=f"{metrics.current_drawdown_pct:.2f}",
                        underwater_days=metrics.underwater_days,
                    )

                accounts_processed += 1

            except Exception as e:
                logger.error(
                    "portfolio_snapshot_error",
                    account_id=account_id,
                    error=str(e),
                )
                # Continue with other accounts
                continue

        logger.info(
            "portfolio_snapshots_complete",
            accounts_processed=accounts_processed,
            snapshots_saved=snapshots_saved,
            warnings_count=len(warnings),
        )

        return {
            "accounts_processed": accounts_processed,
            "snapshots_saved": snapshots_saved,
            "warnings": warnings,
        }

    except Exception as e:
        logger.error("portfolio_snapshots_task_failed", error=str(e))
        raise self.retry(exc=e)
