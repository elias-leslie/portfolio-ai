"""Slippage calculation for order execution.

Extracted from order_executor.py to improve modularity.
Handles slippage model selection and calculation using costs.py infrastructure.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

from app.analytics.liquidity import calculate_adv
from app.backtest.costs import SlippageModel, calculate_slippage, get_default_costs
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


class SlippageResult(NamedTuple):
    """Result of slippage calculation."""

    slippage_per_share: Decimal
    slippage_bps: float
    adv: float | None
    model_used: str


def calculate_order_slippage(
    storage: PortfolioStorage,
    symbol: str,
    expected_price: float,
    shares: int,
    apply_slippage: bool = True,
) -> SlippageResult:
    """Calculate slippage for an order.

    Uses DYNAMIC model when ADV is available, otherwise falls back to FIXED_PCT.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        expected_price: Price before slippage
        shares: Number of shares
        apply_slippage: Whether to apply slippage (default True)

    Returns:
        SlippageResult with slippage details
    """
    if not apply_slippage:
        return SlippageResult(
            slippage_per_share=Decimal("0"),
            slippage_bps=0.0,
            adv=None,
            model_used="NONE",
        )

    # Try DYNAMIC slippage first (uses ADV)
    adv = calculate_adv(storage, symbol)
    costs = get_default_costs()

    if adv is not None and adv > 0:
        # Use DYNAMIC model when ADV is available
        slippage_per_share = calculate_slippage(
            price=Decimal(str(expected_price)),
            shares=shares,
            model=SlippageModel.DYNAMIC,
            average_daily_volume=int(adv),
            dynamic_factor=costs.slippage_dynamic_factor,
        )
        model_used = "DYNAMIC"
    else:
        # Fall back to FIXED_PCT (5 bps)
        slippage_per_share = calculate_slippage(
            price=Decimal(str(expected_price)),
            shares=shares,
            model=SlippageModel.FIXED_PCT,
            slippage_bps=costs.slippage_bps,
        )
        model_used = "FIXED_PCT"

    # Calculate bps
    slippage_bps = 0.0
    if expected_price > 0:
        slippage_bps = float(slippage_per_share / Decimal(str(expected_price)) * 10000)

    return SlippageResult(
        slippage_per_share=slippage_per_share,
        slippage_bps=slippage_bps,
        adv=adv,
        model_used=model_used,
    )
