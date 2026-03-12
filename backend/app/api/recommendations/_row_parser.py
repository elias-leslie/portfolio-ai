"""Row parsing helpers for trade recommendation DB results."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from app.analytics.calculation_engine import build_trade_setup
from app.logging_config import get_logger
from app.portfolio.models import PriceData
from app.rules import get_rules

from .logic import calculate_signal_status
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
    current_prices: dict[str, float | PriceData],
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

    current_price = _get_fresh_current_price(current_prices, symbol)
    if current_price is None:
        logger.info("Skipping %s: missing fresh live price", symbol)
        return None

    price_change_pct, signal_status = calculate_signal_status(sig_type, entry_price, current_price)
    if signal_status == "invalidated":
        logger.info(
            "Skipping %s: signal invalidated (price change: %.1f%%)", symbol, price_change_pct
        )
        return None

    trade_setup = build_trade_setup(
        storage=storage,
        symbol=symbol,
        entry_price=entry_price,
        expected_return_pct=expected_return_pct,
        risk_budget=portfolio_size * 0.015,
        portfolio_value=portfolio_size,
        current_price=current_price,
        position_cap_pct=position_pct,
    )
    if trade_setup is None:
        logger.info("Skipping %s: missing actionable risk levels", symbol)
        return None

    return TradeRecommendation(
        symbol=symbol,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        strategy_type=strategy_type,
        signal_strength=strength,
        signal_type=cast(Literal["BUY", "SELL", "HOLD"], sig_type),
        signal_reasons=reasons,
        entry_price=entry_price,
        current_price=current_price,
        price_change_pct=round(price_change_pct, 2),
        signal_status=signal_status,
        stop_loss=trade_setup.stop_loss,
        target_price=trade_setup.target_price,
        position_size_dollars=trade_setup.sample_dollar_size,
        position_size_shares=trade_setup.sample_share_count,
        risk_reward_ratio=trade_setup.risk_reward_ratio,
        expected_sharpe=expected_sharpe,
        signal_date=_to_date_str(row[8]),
        generated_at=_to_date_str(row[9]) or None,
        validation_type=validation_type,
    )
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


def _get_fresh_current_price(
    current_prices: dict[str, float | PriceData],
    symbol: str,
) -> float | None:
    """Return a fresh current price, or None when the snapshot is missing or stale."""
    snapshot = current_prices.get(symbol)
    if snapshot is None:
        return None

    if isinstance(snapshot, (int, float)):
        return float(snapshot) if snapshot > 0 else None

    if snapshot.error or snapshot.price <= 0:
        return None

    cached_at = snapshot.cached_at
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)

    stale_minutes = get_rules().scoring.price_stale_ttl_minutes
    age = datetime.now(cached_at.tzinfo) - cached_at
    if age.total_seconds() > stale_minutes * 60:
        return None

    return snapshot.price
