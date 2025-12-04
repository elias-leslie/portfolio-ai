"""Risk-based position sizing (GAP-043).

Position sizing based on fixed risk percentage per trade.
This ensures maximum loss per trade is consistent (1-2% of equity)
regardless of the stop-loss distance.

Formula: shares = (risk_percent * equity) / risk_per_share
         risk_per_share = entry_price - stop_loss

Examples:
- Tight stop (2%): More shares, same risk
- Wide stop (10%): Fewer shares, same risk

Integration with other modules:
- GAP-020 (Covariance): Portfolio volatility calculation
- GAP-042 (ATR stops): Stop-loss distance from calculate_stop_loss()
- GAP-044 (Liquidity): Position cap from apply_liquidity_cap()
- GAP-045 (Kelly): Can combine with Kelly for edge-based sizing
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger
from app.rules import get_rules

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _get_sizing_rules() -> tuple[float, float, float, float, float]:
    """Get position sizing rules from centralized config."""
    rules = get_rules()
    ps = rules.position_sizing
    return (
        ps.default_risk_percent,
        ps.min_risk_percent,
        ps.max_risk_percent,
        ps.min_position_value,
        ps.max_position_percent,
    )


# Legacy constants for backwards compatibility (deprecated - use get_rules() instead)
DEFAULT_RISK_PERCENT = 0.015
MIN_RISK_PERCENT = 0.005
MAX_RISK_PERCENT = 0.05
MIN_POSITION_VALUE = 100.0
MAX_POSITION_PERCENT = 0.25


def calculate_risk_per_share(entry_price: float, stop_loss: float) -> float | None:
    """Calculate risk per share (entry - stop).

    Args:
        entry_price: Entry price per share
        stop_loss: Stop-loss price per share

    Returns:
        Risk per share in dollars, or None if invalid setup
    """
    if stop_loss is None or entry_price <= 0 or stop_loss <= 0:
        return None

    if stop_loss >= entry_price:
        # Stop above entry is invalid for long position
        return None

    return entry_price - stop_loss


def calculate_risk_based_shares(
    equity: float,
    entry_price: float,
    stop_loss: float,
    risk_percent: float = DEFAULT_RISK_PERCENT,
) -> tuple[int, dict[str, float | None]]:
    """Calculate number of shares using risk-based position sizing.

    Formula: shares = (risk_percent * equity) / risk_per_share

    Args:
        equity: Total portfolio equity in dollars
        entry_price: Entry price per share
        stop_loss: Stop-loss price per share
        risk_percent: Risk per trade as fraction (0.01 = 1%)

    Returns:
        Tuple of (shares, details dict)
    """
    details: dict[str, float | None] = {
        "equity": equity,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_percent": risk_percent,
        "risk_amount": None,
        "risk_per_share": None,
        "position_value": None,
        "position_percent": None,
        "shares": 0,
    }

    # Validate inputs
    if equity <= 0:
        logger.warning("position_sizing_invalid_equity", equity=equity)
        return 0, details

    if entry_price <= 0:
        logger.warning("position_sizing_invalid_entry", entry_price=entry_price)
        return 0, details

    # Calculate risk per share
    risk_per_share = calculate_risk_per_share(entry_price, stop_loss)
    if risk_per_share is None or risk_per_share <= 0:
        logger.warning(
            "position_sizing_invalid_stop",
            entry_price=entry_price,
            stop_loss=stop_loss,
        )
        return 0, details

    # Bound risk percent to reasonable range
    bounded_risk = max(MIN_RISK_PERCENT, min(risk_percent, MAX_RISK_PERCENT))

    # Calculate maximum risk amount in dollars
    risk_amount = equity * bounded_risk

    # Calculate shares based on risk
    shares_from_risk = risk_amount / risk_per_share

    # Calculate position value
    position_value = shares_from_risk * entry_price
    position_percent = position_value / equity if equity > 0 else 0

    # Apply position cap (even with tight stops, don't exceed 25%)
    if position_percent > MAX_POSITION_PERCENT:
        capped_value = equity * MAX_POSITION_PERCENT
        shares_from_risk = capped_value / entry_price
        position_value = shares_from_risk * entry_price
        position_percent = position_value / equity
        logger.info(
            "position_sizing_capped",
            reason="max_position_percent",
            original_percent=position_percent,
            capped_percent=MAX_POSITION_PERCENT,
        )

    # Round down to whole shares
    shares = int(shares_from_risk)

    # Ensure minimum position value (avoid tiny positions)
    if shares > 0 and shares * entry_price < MIN_POSITION_VALUE:
        min_shares = int(MIN_POSITION_VALUE / entry_price) + 1
        # But don't exceed risk limit - just return 0 if can't meet minimum
        if min_shares * risk_per_share > risk_amount * 1.5:  # Allow 50% overage
            logger.info(
                "position_sizing_below_minimum",
                shares=shares,
                position_value=shares * entry_price,
                min_value=MIN_POSITION_VALUE,
            )
            return 0, details
        shares = min_shares

    # Update details
    details["risk_amount"] = risk_amount
    details["risk_per_share"] = risk_per_share
    details["position_value"] = shares * entry_price
    details["position_percent"] = (shares * entry_price) / equity if equity > 0 else 0
    details["shares"] = float(shares)

    logger.info(
        "position_sizing_calculated",
        equity=equity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_percent=bounded_risk,
        risk_amount=risk_amount,
        risk_per_share=risk_per_share,
        shares=shares,
        position_percent=details["position_percent"],
    )

    return shares, details


def calculate_stop_distance_percent(entry_price: float, stop_loss: float) -> float | None:
    """Calculate stop-loss distance as percentage of entry price.

    Args:
        entry_price: Entry price per share
        stop_loss: Stop-loss price per share

    Returns:
        Stop distance as percentage (e.g., 0.05 = 5%), or None if invalid
    """
    if entry_price <= 0 or stop_loss <= 0 or stop_loss >= entry_price:
        return None

    return (entry_price - stop_loss) / entry_price


def get_risk_adjusted_position_size(
    storage: PortfolioStorage,
    ticker: str,
    equity: float,
    entry_price: float,
    risk_percent: float = DEFAULT_RISK_PERCENT,
) -> tuple[int, dict[str, float | str | None]]:
    """Get position size using ATR-based stop and risk-based sizing.

    Combines GAP-042 (ATR stops) with GAP-043 (risk-based sizing).

    Args:
        storage: Database storage for ATR lookup
        ticker: Stock ticker symbol
        equity: Total portfolio equity in dollars
        entry_price: Entry price per share
        risk_percent: Risk per trade as fraction (0.015 = 1.5%)

    Returns:
        Tuple of (shares, details dict)
    """
    from app.analytics.trade_calculations import calculate_stop_loss  # noqa: PLC0415

    details: dict[str, float | str | None] = {
        "symbol": ticker,
        "equity": equity,
        "entry_price": entry_price,
        "stop_loss": None,
        "stop_distance_pct": None,
        "risk_percent": risk_percent,
        "shares": 0,
        "position_value": None,
        "reason": None,
    }

    # Get ATR-based stop loss
    stop_loss = calculate_stop_loss(storage, ticker, entry_price)

    if stop_loss is None:
        details["reason"] = "no_atr_data"
        logger.warning(
            "risk_adjusted_sizing_no_stop",
            ticker=ticker,
            reason="ATR not available",
        )
        return 0, details

    details["stop_loss"] = stop_loss
    details["stop_distance_pct"] = calculate_stop_distance_percent(entry_price, stop_loss)

    # Calculate risk-based position size
    shares, size_details = calculate_risk_based_shares(
        equity=equity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_percent=risk_percent,
    )

    # Merge details
    details["risk_amount"] = size_details.get("risk_amount")
    details["risk_per_share"] = size_details.get("risk_per_share")
    details["shares"] = float(shares)
    details["position_value"] = size_details.get("position_value")
    details["position_percent"] = size_details.get("position_percent")

    return shares, details


def validate_position_size(  # noqa: PLR0911
    shares: int,
    entry_price: float,
    equity: float,
    stop_loss: float | None,
    risk_percent: float = DEFAULT_RISK_PERCENT,
) -> tuple[bool, str | None]:
    """Validate a proposed position size against risk rules.

    Args:
        shares: Number of shares proposed
        entry_price: Entry price per share
        equity: Total portfolio equity
        stop_loss: Stop-loss price (None = skip risk validation)
        risk_percent: Maximum allowed risk percent

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic input validation
    if shares <= 0:
        return False, "Shares must be positive"
    if entry_price <= 0:
        return False, "Entry price must be positive"
    if equity <= 0:
        return False, "Equity must be positive"

    position_value = shares * entry_price
    position_percent = position_value / equity

    # Check position size cap
    if position_percent > MAX_POSITION_PERCENT:
        return False, (
            f"Position {position_percent:.1%} exceeds max {MAX_POSITION_PERCENT:.0%} of portfolio"
        )

    # Check risk limit if stop-loss provided
    if stop_loss is not None and stop_loss > 0:
        risk_per_share = calculate_risk_per_share(entry_price, stop_loss)
        if risk_per_share is None:
            return False, "Invalid stop-loss (must be below entry)"

        actual_risk = shares * risk_per_share
        max_risk = equity * MAX_RISK_PERCENT

        if actual_risk > max_risk:
            actual_risk_pct = actual_risk / equity
            return False, (
                f"Trade risk {actual_risk_pct:.1%} exceeds max {MAX_RISK_PERCENT:.0%} of portfolio"
            )

    return True, None
