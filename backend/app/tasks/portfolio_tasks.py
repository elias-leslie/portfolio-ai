"""Portfolio monitoring and drawdown tracking tasks.

GAP-023: Daily portfolio snapshot task for drawdown tracking.
Runs daily at 21:30 UTC (4:30 PM ET, 30 min after market close).
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.portfolio.drawdown import (
    calculate_drawdown_metrics,
    save_portfolio_snapshot,
)
from app.storage import PortfolioStorage

logger = get_logger(__name__)

_HIGH_DRAWDOWN_THRESHOLD = 7.5


def _collect_drawdown_warning(
    storage: PortfolioStorage,
    account_id: str,
    account_name: str,
) -> str | None:
    """Check drawdown metrics and return a warning message if threshold exceeded.

    Returns:
        Warning message string if drawdown >= threshold, else None.
    """
    metrics = calculate_drawdown_metrics(storage, account_id)
    if metrics.current_drawdown_pct < _HIGH_DRAWDOWN_THRESHOLD:
        return None

    warning_msg = (
        f"Account '{account_name}' ({account_id}): "
        f"{metrics.current_drawdown_pct:.1f}% drawdown"
    )
    logger.warning(
        "portfolio_high_drawdown",
        account_id=account_id,
        account_name=account_name,
        drawdown_pct=f"{metrics.current_drawdown_pct:.2f}",
        underwater_days=metrics.underwater_days,
    )
    return warning_msg


def _process_account_snapshot(
    storage: PortfolioStorage,
    account_id: str,
    account_name: str,
) -> str | None:
    """Save a snapshot for one account and return any high-drawdown warning.

    Returns:
        Warning message string if drawdown is high, else None.
        Raises on unrecoverable error.
    """
    save_portfolio_snapshot(storage, account_id)
    return _collect_drawdown_warning(storage, account_id, account_name)


def _process_all_accounts(
    storage: PortfolioStorage,
    accounts_result: Any,
) -> dict[str, Any]:
    """Iterate accounts, save snapshots, and collect warnings.

    Returns:
        dict with accounts_processed, snapshots_saved, warnings.
    """
    accounts_processed = 0
    snapshots_saved = 0
    warnings = []

    for row in accounts_result.iter_rows(named=True):
        account_id = row["id"]
        account_name = row["name"] or account_id

        try:
            warning = _process_account_snapshot(storage, account_id, account_name)
            snapshots_saved += 1
            accounts_processed += 1
            if warning is not None:
                warnings.append(warning)
        except Exception as e:
            logger.error(
                "portfolio_snapshot_error",
                account_id=account_id,
                error=str(e),
            )

    return {
        "accounts_processed": accounts_processed,
        "snapshots_saved": snapshots_saved,
        "warnings": warnings,
    }


def save_portfolio_snapshots_task() -> dict[str, Any]:
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
        accounts_query = """
            SELECT id, name FROM portfolio_accounts
        """
        accounts_result = storage.query(accounts_query, [])

        if accounts_result.is_empty():
            logger.info("portfolio_snapshots_no_accounts")
            return {"accounts_processed": 0, "snapshots_saved": 0, "warnings": []}

        result = _process_all_accounts(storage, accounts_result)

        logger.info(
            "portfolio_snapshots_complete",
            accounts_processed=result["accounts_processed"],
            snapshots_saved=result["snapshots_saved"],
            warnings_count=len(result["warnings"]),
        )

        return result

    except Exception as e:
        logger.error("portfolio_snapshots_task_failed", error=str(e), exc_info=True)
        raise
