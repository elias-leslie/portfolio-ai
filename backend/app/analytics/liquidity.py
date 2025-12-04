"""Liquidity checks for position sizing (GAP-044).

This module prevents taking positions that are too large relative to
the stock's trading volume, which would cause market impact and
poor execution.

Rule: Position ≤ 1% of ADV (Average Daily Volume)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Maximum position as percentage of ADV
MAX_POSITION_PERCENT_ADV = 0.01  # 1%

# Minimum days of volume data for reliable ADV
MIN_VOLUME_DAYS = 20


def calculate_adv(
    storage: PortfolioStorage,
    symbol: str,
    lookback_days: int = 20,
) -> float | None:
    """Calculate Average Daily Volume for a symbol.

    Uses 20-day average by default (standard institutional metric).

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        lookback_days: Number of trading days for average

    Returns:
        Average daily volume as float, or None if insufficient data
    """
    query = """
        SELECT AVG(volume) as adv, COUNT(*) as days_count
        FROM (
            SELECT volume
            FROM day_bars
            WHERE symbol = $1
            ORDER BY date DESC
            LIMIT $2
        ) recent_volume
    """

    result = storage.query(query, [symbol, lookback_days])

    if result.is_empty():
        logger.warning(
            "adv_no_data",
            symbol=symbol,
            lookback_days=lookback_days,
        )
        return None

    row = result.to_dicts()[0]
    days_count = row["days_count"]
    adv = row["adv"]

    if days_count < MIN_VOLUME_DAYS:
        logger.warning(
            "adv_insufficient_data",
            symbol=symbol,
            days_count=days_count,
            min_required=MIN_VOLUME_DAYS,
        )
        return None

    if adv is None or adv <= 0:
        logger.warning(
            "adv_invalid",
            symbol=symbol,
            adv=adv,
        )
        return None

    return float(adv)


def get_max_position_shares(
    storage: PortfolioStorage,
    symbol: str,
    entry_price: float,
    max_percent_adv: float = MAX_POSITION_PERCENT_ADV,
) -> tuple[int, float | None]:
    """Calculate maximum position size based on liquidity.

    Rule: Position value ≤ max_percent_adv * ADV * price

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        entry_price: Entry price per share
        max_percent_adv: Maximum position as % of ADV (default: 1%)

    Returns:
        Tuple of (max_shares, adv):
        - max_shares: Maximum shares that can be traded without market impact
        - adv: Average daily volume (None if unavailable)
    """
    adv = calculate_adv(storage, symbol)

    if adv is None:
        logger.warning(
            "liquidity_check_blocked",
            symbol=symbol,
            reason="no_adv_available",
        )
        return 0, None

    # Max shares = max_percent_adv * ADV
    max_shares = int(max_percent_adv * adv)

    # Also cap by dollar value if we want to trade conservatively
    # For now, just use volume-based limit

    logger.debug(
        "max_position_calculated",
        symbol=symbol,
        adv=adv,
        max_percent_adv=max_percent_adv,
        max_shares=max_shares,
        max_value=max_shares * entry_price,
    )

    return max_shares, adv


def check_position_liquidity(
    storage: PortfolioStorage,
    symbol: str,
    proposed_shares: int,
    entry_price: float,
) -> tuple[bool, str, dict[str, float | int | str]]:
    """Check if proposed position size is liquid enough.

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        proposed_shares: Number of shares to trade
        entry_price: Entry price per share

    Returns:
        Tuple of (is_ok, message, details):
        - is_ok: True if position is within liquidity limits
        - message: Human-readable status message
        - details: Dict with adv, max_shares, position_percent_adv
    """
    adv = calculate_adv(storage, symbol)

    if adv is None:
        return (
            False,
            "Insufficient volume data",
            {
                "symbol": symbol,
                "reason": "no_adv_available",
            },
        )

    max_shares = int(MAX_POSITION_PERCENT_ADV * adv)
    position_percent_adv = (proposed_shares / adv) * 100 if adv > 0 else 100

    details: dict[str, float | int | str] = {
        "symbol": symbol,
        "proposed_shares": proposed_shares,
        "proposed_value": proposed_shares * entry_price,
        "adv": adv,
        "adv_value": adv * entry_price,
        "max_shares": max_shares,
        "position_percent_adv": position_percent_adv,
        "max_percent_adv": MAX_POSITION_PERCENT_ADV * 100,
    }

    if proposed_shares > max_shares:
        message = (
            f"Position too large: {proposed_shares:,} shares = "
            f"{position_percent_adv:.2f}% of ADV (max {MAX_POSITION_PERCENT_ADV * 100:.0f}%)"
        )
        logger.warning(
            "liquidity_check_failed",
            **details,
        )
        return False, message, details

    message = f"Position OK: {proposed_shares:,} shares = {position_percent_adv:.2f}% of ADV"
    logger.info(
        "liquidity_check_passed",
        **details,
    )
    return True, message, details


def apply_liquidity_cap(
    storage: PortfolioStorage,
    symbol: str,
    desired_shares: int,
    entry_price: float,
) -> tuple[int, str]:
    """Apply liquidity cap to a desired position size.

    If desired position exceeds liquidity limit, reduces to max allowed.

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        desired_shares: Number of shares originally desired
        entry_price: Entry price per share

    Returns:
        Tuple of (final_shares, message):
        - final_shares: Shares to actually trade (may be reduced)
        - message: Explanation of any reduction
    """
    max_shares, adv = get_max_position_shares(storage, symbol, entry_price)

    if adv is None:
        # No volume data - block the trade entirely
        return 0, f"Trade blocked: No volume data for {symbol}"

    if desired_shares <= max_shares:
        return (
            desired_shares,
            f"Position within liquidity limit ({desired_shares:,} <= {max_shares:,})",
        )

    # Reduce to max allowed
    logger.info(
        "liquidity_cap_applied",
        symbol=symbol,
        desired_shares=desired_shares,
        max_shares=max_shares,
        reduction_percent=((desired_shares - max_shares) / desired_shares) * 100,
    )

    return max_shares, (
        f"Position reduced from {desired_shares:,} to {max_shares:,} shares "
        f"(1% of ADV = {adv:,.0f} shares/day)"
    )
