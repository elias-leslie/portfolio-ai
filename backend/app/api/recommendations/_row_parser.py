"""Row parsing helpers for trade recommendation DB results."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from app.analytics.trade_calculations import calculate_stop_loss
from app.logging_config import get_logger

from .logic import (
    calculate_position_size,
    calculate_risk_reward,
    calculate_signal_status,
)
from .models import TradeRecommendation

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _extract_required_str(row: Any, index: int) -> str | None:
    """Return row[index] if it is a non-None str, else None."""
    value = row[index]
    return value if isinstance(value, str) else None


def _determine_validation_type(
    thesis_status: Any,
    cross_validation_score: Any,
    expected_sharpe: float | None,
) -> Literal["thesis", "backtest", "both"]:
    """Determine validation type from thesis and backtest data."""
    has_thesis = (
        thesis_status == "active"
        and cross_validation_score is not None
        and float(cross_validation_score) >= 0.7
    )
    has_backtest = expected_sharpe is not None and expected_sharpe >= 1.0

    if has_thesis and has_backtest:
        return "both"
    if has_thesis:
        return "thesis"
    return "backtest"


def _passes_validation_filter(
    validation_type: Literal["thesis", "backtest", "both"],
    validation_filter: Literal["thesis", "backtest", "both", "all"] | None,
) -> bool:
    """Return True if the row passes the validation filter."""
    if not validation_filter or validation_filter == "all":
        return True
    if validation_filter == "both":
        return validation_type == "both"
    return validation_type in (validation_filter, "both")


def _to_date_str(value: Any) -> str:
    """Convert a date/datetime/str to ISO format string."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return ""


def parse_row(
    row: Any,
    current_prices: dict[str, float],
    portfolio_size: float,
    position_pct: float,
    validation_filter: Literal["thesis", "backtest", "both", "all"] | None,
    storage: PortfolioStorage,
) -> TradeRecommendation | None:
    """Parse a single DB row into a TradeRecommendation.

    Returns None if the row should be skipped.
    """
    base_row = _extract_base_row(row)
    if base_row is None:
        return None

    symbol, strategy_id, strategy_name, strategy_type, sig_type, strength = base_row

    reasons_raw = row[6]
    reasons: list[str] = (
        [str(r) for r in reasons_raw if r is not None]
        if isinstance(reasons_raw, list)
        else []
    )

    market_data_raw = row[7]
    market_data: dict[str, Any] = market_data_raw if isinstance(market_data_raw, dict) else {}

    expected_sharpe = float(row[10]) if row[10] else None
    validation_type = _determine_validation_type(row[11], row[12], expected_sharpe)
    expected_return_pct = float(row[13]) if row[13] is not None else None

    price_value = market_data.get("price", 0)
    entry_price = float(price_value) if price_value else 0.0
    if not _is_actionable_row(entry_price, validation_type, validation_filter):
        return None

    current_price = current_prices.get(symbol, entry_price)  # type: ignore[arg-type]
    price_change_pct, signal_status = calculate_signal_status(sig_type, entry_price, current_price)  # type: ignore[arg-type]
    if signal_status == "invalidated":
        logger.info(
            f"Skipping {symbol}: signal invalidated (price change: {price_change_pct:.1f}%)"
        )
        return None

    dollars, shares = calculate_position_size(current_price, portfolio_size, position_pct)
    risk_levels = _build_risk_levels(storage, symbol, current_price, entry_price, expected_return_pct)
    if risk_levels is None:
        logger.info(f"Skipping {symbol}: missing actionable risk levels")
        return None

    stop_loss, target_price = risk_levels
    risk_reward = calculate_risk_reward(current_price, stop_loss, target_price)
    if risk_reward <= 0:
        logger.info(f"Skipping {symbol}: invalid risk reward ratio")
        return None

    return TradeRecommendation(
        symbol=symbol,  # type: ignore[arg-type]
        strategy_id=strategy_id,
        strategy_name=strategy_name,  # type: ignore[arg-type]
        strategy_type=strategy_type,  # type: ignore[arg-type]
        signal_strength=strength,
        signal_type=cast(Literal["BUY", "SELL", "HOLD"], sig_type),
        signal_reasons=reasons,
        entry_price=entry_price,
        current_price=current_price,
        price_change_pct=round(price_change_pct, 2),
        signal_status=signal_status,
        stop_loss=stop_loss,
        target_price=target_price,
        position_size_dollars=dollars,
        position_size_shares=shares,
        risk_reward_ratio=risk_reward,
        expected_sharpe=expected_sharpe,
        signal_date=_to_date_str(row[8]),
        generated_at=_to_date_str(row[9]) or None,
        validation_type=validation_type,
    )


def _build_target_price(entry_price: float, expected_return_pct: float | None) -> float | None:
    """Convert thesis expected return into an actionable target price."""
    if expected_return_pct is None:
        return None
    if expected_return_pct <= 0:
        return None
    return round(entry_price * (1 + (expected_return_pct / 100.0)), 2)


def _extract_base_row(
    row: Any,
) -> tuple[str, str, str, str, str, int] | None:
    """Extract the required row fields or return None when the row is malformed."""
    symbol = _extract_required_str(row, 0)
    strategy_name = _extract_required_str(row, 2)
    strategy_type = _extract_required_str(row, 3)
    sig_type = _extract_required_str(row, 4)
    strength_raw = row[5]

    required_values = (symbol, strategy_name, strategy_type, sig_type)
    if not all(required_values) or not isinstance(strength_raw, int):
        return None

    return (
        cast(str, symbol),
        str(row[1]),
        cast(str, strategy_name),
        cast(str, strategy_type),
        cast(str, sig_type),
        strength_raw,
    )


def _is_actionable_row(
    entry_price: float,
    validation_type: Literal["thesis", "backtest", "both"],
    validation_filter: Literal["thesis", "backtest", "both", "all"] | None,
) -> bool:
    """Return True when the row has enough data to continue parsing."""
    return entry_price > 0 and _passes_validation_filter(validation_type, validation_filter)


def _build_risk_levels(
    storage: PortfolioStorage,
    symbol: str,
    current_price: float,
    entry_price: float,
    expected_return_pct: float | None,
) -> tuple[float, float] | None:
    """Build stop loss and target price, or None when either level is missing."""
    stop_loss = calculate_stop_loss(storage, symbol, current_price)
    target_price = _build_target_price(entry_price, expected_return_pct)
    if stop_loss is None or target_price is None:
        return None
    return stop_loss, target_price
