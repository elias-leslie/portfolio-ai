"""Pattern Day Trader (PDT) rules enforcement.

FINRA Pattern Day Trader Rule:
- 4+ day trades in 5 business days = PDT classification
- PDT accounts require $25,000 minimum equity
- Day trade = same symbol bought and sold same day

This module tracks day trades and warns/blocks when approaching limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# PDT threshold
PDT_DAY_TRADE_LIMIT = 4  # 4+ trades triggers PDT status
PDT_ROLLING_DAYS = 5  # 5 business day window
PDT_EQUITY_THRESHOLD = 25_000.0  # $25k minimum for PDT accounts


def count_day_trades(
    storage: PortfolioStorage,
    account_id: str = "default",
    lookback_days: int = PDT_ROLLING_DAYS,
) -> int:
    """Count day trades in the rolling window.

    A day trade is when a position is opened and closed on the same day.

    Args:
        storage: Database storage instance
        account_id: Trading account ID
        lookback_days: Days to look back (default: 5 business days)

    Returns:
        Number of day trades in the window
    """
    # Query idea_outcomes (paper trades) for same-day opens and closes
    query = """
        SELECT COUNT(*) as day_trade_count
        FROM idea_outcomes
        WHERE account_id = $1
          AND entry_date >= CURRENT_DATE - INTERVAL '1 day' * $2
          AND exit_date IS NOT NULL
          AND DATE(entry_date) = DATE(exit_date)
    """

    result = storage.query(query, [account_id, lookback_days])

    if result.is_empty():
        return 0

    count = result.to_dicts()[0]["day_trade_count"]
    return int(count) if count else 0


def get_account_equity(
    storage: PortfolioStorage,
    account_id: str = "default",
) -> float:
    """Get current account equity.

    Args:
        storage: Database storage instance
        account_id: Trading account ID

    Returns:
        Account equity in dollars
    """
    query = """
        SELECT equity
        FROM portfolio_accounts
        WHERE id = $1
    """

    result = storage.query(query, [account_id])

    if result.is_empty():
        logger.warning(
            "pdt_account_not_found",
            account_id=account_id,
        )
        return 0.0

    equity = result.to_dicts()[0]["equity"]
    return float(equity) if equity else 0.0


def check_pdt_status(
    storage: PortfolioStorage,
    account_id: str = "default",
) -> tuple[bool, str, dict[str, float | int | str | bool]]:
    """Check PDT status and day trade availability.

    Args:
        storage: Database storage instance
        account_id: Trading account ID

    Returns:
        Tuple of (can_day_trade, message, details):
        - can_day_trade: True if another day trade is allowed
        - message: Human-readable status
        - details: Dict with day_trades_used, trades_remaining, etc.
    """
    day_trades = count_day_trades(storage, account_id)
    equity = get_account_equity(storage, account_id)

    trades_remaining = max(0, PDT_DAY_TRADE_LIMIT - 1 - day_trades)
    is_pdt_account = day_trades >= PDT_DAY_TRADE_LIMIT

    details: dict[str, float | int | str | bool] = {
        "account_id": account_id,
        "day_trades_used": day_trades,
        "day_trade_limit": PDT_DAY_TRADE_LIMIT,
        "trades_remaining": trades_remaining,
        "equity": equity,
        "equity_threshold": PDT_EQUITY_THRESHOLD,
        "is_pdt_account": is_pdt_account,
        "meets_equity_requirement": equity >= PDT_EQUITY_THRESHOLD,
    }

    # Check if this is a PDT account (4+ day trades)
    if is_pdt_account:
        if equity >= PDT_EQUITY_THRESHOLD:
            message = f"PDT account (≥$25k equity): {day_trades} day trades, unlimited remaining"
            details["trades_remaining"] = 999  # Unlimited for qualified PDT
            logger.info(
                "pdt_qualified",
                account_id=account_id,
                day_trades=day_trades,
                equity=equity,
            )
            return True, message, details
        message = (
            f"PDT RESTRICTED: Account below $25k (${equity:,.0f}). "
            f"Day trading blocked until equity restored."
        )
        details["trades_remaining"] = 0
        logger.warning(
            "pdt_restricted",
            account_id=account_id,
            day_trades=day_trades,
            equity=equity,
        )
        return False, message, details

    # Not yet PDT - check if approaching limit
    if day_trades >= PDT_DAY_TRADE_LIMIT - 1:
        # At limit - one more would trigger PDT
        if equity >= PDT_EQUITY_THRESHOLD:
            message = (
                f"WARNING: Next day trade triggers PDT status. "
                f"{day_trades}/{PDT_DAY_TRADE_LIMIT - 1} used. Equity OK (${equity:,.0f})"
            )
            return True, message, details
        message = (
            f"BLOCKED: Next day trade triggers PDT but equity "
            f"(${equity:,.0f}) < $25k required. {day_trades}/{PDT_DAY_TRADE_LIMIT - 1} used"
        )
        details["trades_remaining"] = 0
        logger.warning(
            "pdt_would_trigger",
            account_id=account_id,
            day_trades=day_trades,
            equity=equity,
        )
        return False, message, details

    # Normal case - under limit
    message = (
        f"OK: {day_trades}/{PDT_DAY_TRADE_LIMIT - 1} day trades used, {trades_remaining} remaining"
    )
    logger.debug(
        "pdt_check_passed",
        account_id=account_id,
        day_trades=day_trades,
        trades_remaining=trades_remaining,
    )
    return True, message, details


def should_block_day_trade(
    storage: PortfolioStorage,
    account_id: str = "default",
) -> bool:
    """Quick check if a day trade should be blocked.

    Args:
        storage: Database storage instance
        account_id: Trading account ID

    Returns:
        True if day trade should be blocked
    """
    can_trade, _, _ = check_pdt_status(storage, account_id)
    return not can_trade
