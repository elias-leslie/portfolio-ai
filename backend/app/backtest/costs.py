"""
Slippage and commission modeling for realistic backtesting.

This module provides:
1. SlippageModel: Models for price impact/slippage
2. CommissionModel: Commission structures (per-share, percentage, per-trade)
3. TradingCosts: Combined cost configuration
4. Cost calculation functions for realistic P&L adjustments

Usage:
    costs = TradingCosts(
        slippage_model=SlippageModel.FIXED_PCT,
        slippage_bps=5,  # 0.05%
        commission_model=CommissionModel.PER_SHARE,
        commission_per_share=Decimal("0.005")
    )
    adjusted_pnl = apply_costs_to_trade(
        entry_price=Decimal("100.00"),
        exit_price=Decimal("105.00"),
        shares=100,
        costs=costs
    )
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Literal


class SlippageModel(str, Enum):
    """Slippage model types for price impact estimation."""

    NONE = "none"  # No slippage (unrealistic)
    FIXED_PCT = "fixed_pct"  # Fixed percentage slippage (e.g., 0.05%)
    DYNAMIC = "dynamic"  # Volume-based slippage (position_size / ADV)


class CommissionModel(str, Enum):
    """Commission model types for trading costs."""

    NONE = "none"  # No commission (unrealistic)
    PER_SHARE = "per_share"  # Fixed cost per share (e.g., $0.005/share)
    PER_TRADE = "per_trade"  # Fixed cost per trade (e.g., $1.00/trade)
    PERCENTAGE = "percentage"  # Percentage of trade value (e.g., 0.1%)


@dataclass
class TradingCosts:
    """Configuration for slippage and commission costs.

    Default values represent realistic retail trading costs:
    - Slippage: 0.05% (5 basis points)
    - Commission: $0.005 per share with $1.00 minimum

    Attributes:
        slippage_model: Type of slippage calculation
        slippage_bps: Slippage in basis points (1 bps = 0.01%)
        slippage_dynamic_factor: For DYNAMIC model, multiplier for (position/ADV)
        commission_model: Type of commission calculation
        commission_per_share: Cost per share for PER_SHARE model
        commission_per_trade: Fixed cost per trade for PER_TRADE model
        commission_pct: Percentage of trade value for PERCENTAGE model
        commission_minimum: Minimum commission per trade (applies to all models)
    """

    slippage_model: SlippageModel = SlippageModel.FIXED_PCT
    slippage_bps: Decimal = Decimal("5.0")  # 0.05% default
    slippage_dynamic_factor: Decimal = Decimal("0.1")  # 10% impact if position = ADV

    commission_model: CommissionModel = CommissionModel.PER_SHARE
    commission_per_share: Decimal = Decimal("0.005")  # $0.005/share
    commission_per_trade: Decimal = Decimal("1.00")  # $1.00/trade for PER_TRADE
    commission_pct: Decimal = Decimal("0.001")  # 0.1% for PERCENTAGE
    commission_minimum: Decimal = Decimal("1.00")  # $1.00 minimum

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")
        if self.slippage_dynamic_factor < 0:
            raise ValueError("slippage_dynamic_factor must be non-negative")
        if self.commission_per_share < 0:
            raise ValueError("commission_per_share must be non-negative")
        if self.commission_per_trade < 0:
            raise ValueError("commission_per_trade must be non-negative")
        if self.commission_pct < 0 or self.commission_pct > 1:
            raise ValueError("commission_pct must be between 0 and 1")
        if self.commission_minimum < 0:
            raise ValueError("commission_minimum must be non-negative")


def calculate_slippage(
    price: Decimal,
    shares: int,
    model: SlippageModel,
    slippage_bps: Decimal = Decimal("5.0"),
    average_daily_volume: int | None = None,
    dynamic_factor: Decimal = Decimal("0.1"),
) -> Decimal:
    """Calculate slippage cost per share.

    Args:
        price: Base price per share
        shares: Number of shares traded
        model: Slippage model to use
        slippage_bps: Basis points for FIXED_PCT model (default 5 = 0.05%)
        average_daily_volume: ADV for DYNAMIC model (required if model=DYNAMIC)
        dynamic_factor: Multiplier for DYNAMIC model (default 0.1 = 10% impact at 100% ADV)

    Returns:
        Slippage cost per share (always non-negative)

    Raises:
        ValueError: If DYNAMIC model used without average_daily_volume

    Examples:
        >>> calculate_slippage(Decimal("100"), 100, SlippageModel.NONE)
        Decimal('0.00')
        >>> calculate_slippage(Decimal("100"), 100, SlippageModel.FIXED_PCT, Decimal("5"))
        Decimal('0.05')  # 0.05% of $100
        >>> calculate_slippage(Decimal("100"), 1000, SlippageModel.DYNAMIC, average_daily_volume=100000)
        Decimal('0.10')  # 1% of ADV -> 0.1% impact
    """
    if model == SlippageModel.NONE:
        return Decimal("0.00")

    if model == SlippageModel.FIXED_PCT:
        # Convert basis points to decimal (5 bps = 0.0005)
        slippage_rate = slippage_bps / Decimal("10000")
        return price * slippage_rate

    if model == SlippageModel.DYNAMIC:
        if average_daily_volume is None or average_daily_volume <= 0:
            raise ValueError("DYNAMIC slippage model requires positive average_daily_volume")

        # Calculate position as percentage of ADV and apply dynamic factor
        # Example: 1% of ADV with 0.1 factor results in 0.1% slippage
        position_pct = Decimal(shares) / Decimal(average_daily_volume)
        slippage_rate = position_pct * dynamic_factor
        return price * slippage_rate

    raise ValueError(f"Unknown slippage model: {model}")


def calculate_commission(
    shares: int,
    price: Decimal,
    model: CommissionModel,
    commission_per_share: Decimal = Decimal("0.005"),
    commission_per_trade: Decimal = Decimal("1.00"),
    commission_pct: Decimal = Decimal("0.001"),
    commission_minimum: Decimal = Decimal("1.00"),
) -> Decimal:
    """Calculate commission cost for a trade.

    Args:
        shares: Number of shares traded
        price: Price per share
        model: Commission model to use
        commission_per_share: Cost per share for PER_SHARE model
        commission_per_trade: Fixed cost for PER_TRADE model
        commission_pct: Percentage of trade value for PERCENTAGE model
        commission_minimum: Minimum commission (applies to all models)

    Returns:
        Total commission cost (always non-negative)

    Examples:
        >>> calculate_commission(100, Decimal("100"), CommissionModel.NONE)
        Decimal('0.00')
        >>> calculate_commission(100, Decimal("100"), CommissionModel.PER_SHARE, Decimal("0.005"))
        Decimal('1.00')  # max(100 * 0.005, 1.00) = 1.00
        >>> calculate_commission(1000, Decimal("100"), CommissionModel.PER_SHARE, Decimal("0.005"))
        Decimal('5.00')  # 1000 * 0.005 = 5.00
        >>> calculate_commission(100, Decimal("100"), CommissionModel.PERCENTAGE, commission_pct=Decimal("0.001"))
        Decimal('1.00')  # max(10000 * 0.001, 1.00) = 1.00
    """
    if model == CommissionModel.NONE:
        return Decimal("0.00")

    if model == CommissionModel.PER_SHARE:
        commission = Decimal(shares) * commission_per_share
        return max(commission, commission_minimum)

    if model == CommissionModel.PER_TRADE:
        return max(commission_per_trade, commission_minimum)

    if model == CommissionModel.PERCENTAGE:
        trade_value = Decimal(shares) * price
        commission = trade_value * commission_pct
        return max(commission, commission_minimum)

    raise ValueError(f"Unknown commission model: {model}")


def calculate_trade_costs(
    shares: int,
    price: Decimal,
    costs: TradingCosts,
    average_daily_volume: int | None = None,
    direction: Literal["buy", "sell"] = "buy",
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate total trading costs (slippage + commission) for a trade.

    Args:
        shares: Number of shares traded
        price: Base price per share
        costs: TradingCosts configuration
        average_daily_volume: Required for DYNAMIC slippage model
        direction: Trade direction ('buy' or 'sell')

    Returns:
        Tuple of (total_cost, slippage_cost, commission_cost)
        - For buys: costs increase effective price
        - For sells: costs decrease effective proceeds

    Examples:
        >>> costs = TradingCosts()
        >>> calculate_trade_costs(100, Decimal("100"), costs)
        (Decimal('6.00'), Decimal('5.00'), Decimal('1.00'))
    """
    # Calculate slippage per share
    slippage_per_share = calculate_slippage(
        price=price,
        shares=shares,
        model=costs.slippage_model,
        slippage_bps=costs.slippage_bps,
        average_daily_volume=average_daily_volume,
        dynamic_factor=costs.slippage_dynamic_factor,
    )

    # Total slippage cost
    slippage_cost = slippage_per_share * Decimal(shares)

    # Calculate commission
    commission_cost = calculate_commission(
        shares=shares,
        price=price,
        model=costs.commission_model,
        commission_per_share=costs.commission_per_share,
        commission_per_trade=costs.commission_per_trade,
        commission_pct=costs.commission_pct,
        commission_minimum=costs.commission_minimum,
    )

    # Total cost
    total_cost = slippage_cost + commission_cost

    return total_cost, slippage_cost, commission_cost


def apply_costs_to_trade(
    entry_price: Decimal,
    exit_price: Decimal,
    shares: int,
    costs: TradingCosts,
    entry_adv: int | None = None,
    exit_adv: int | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Apply trading costs to calculate adjusted P&L.

    Costs are applied twice:
    1. Entry: Slippage increases buy price, commission reduces capital
    2. Exit: Slippage decreases sell price, commission reduces proceeds

    Args:
        entry_price: Entry price per share (before costs)
        exit_price: Exit price per share (before costs)
        shares: Number of shares traded
        costs: TradingCosts configuration
        entry_adv: Average daily volume at entry (for DYNAMIC slippage)
        exit_adv: Average daily volume at exit (for DYNAMIC slippage)

    Returns:
        Tuple of (adjusted_pnl, gross_pnl, total_costs, effective_entry_price)
        - adjusted_pnl: Net P&L after all costs
        - gross_pnl: P&L before costs
        - total_costs: Sum of entry and exit costs
        - effective_entry_price: Entry price including slippage

    Examples:
        >>> costs = TradingCosts()
        >>> apply_costs_to_trade(
        ...     entry_price=Decimal("100"),
        ...     exit_price=Decimal("105"),
        ...     shares=100,
        ...     costs=costs
        ... )
        (Decimal('488.00'), Decimal('500.00'), Decimal('12.00'), Decimal('100.05'))

        Breakdown:
        - Gross P&L: (105 - 100) * 100 = $500
        - Entry costs: $5 slippage + $1 commission = $6
        - Exit costs: $5.25 slippage + $1 commission = $6.25
        - Net P&L: $500 - $12.25 = $487.75
    """
    # Calculate entry costs (buying)
    entry_total_cost, entry_slippage, entry_commission = calculate_trade_costs(
        shares=shares,
        price=entry_price,
        costs=costs,
        average_daily_volume=entry_adv,
        direction="buy",
    )

    # Calculate exit costs (selling)
    exit_total_cost, exit_slippage, exit_commission = calculate_trade_costs(
        shares=shares,
        price=exit_price,
        costs=costs,
        average_daily_volume=exit_adv,
        direction="sell",
    )

    # Calculate effective prices (price + slippage per share)
    entry_slippage_per_share = entry_slippage / Decimal(shares) if shares > 0 else Decimal("0")
    exit_slippage_per_share = exit_slippage / Decimal(shares) if shares > 0 else Decimal("0")

    effective_entry_price = entry_price + entry_slippage_per_share
    effective_exit_price = exit_price - exit_slippage_per_share

    # Calculate P&L
    gross_pnl = (exit_price - entry_price) * Decimal(shares)
    slippage_adjusted_pnl = (effective_exit_price - effective_entry_price) * Decimal(shares)
    total_costs = entry_total_cost + exit_total_cost
    adjusted_pnl = slippage_adjusted_pnl - (entry_commission + exit_commission)

    return adjusted_pnl, gross_pnl, total_costs, effective_entry_price


def get_default_costs() -> TradingCosts:
    """Get default trading costs for realistic backtesting.

    Returns realistic retail trading costs:
    - Slippage: 0.05% (5 basis points) fixed
    - Commission: $0.005/share with $1.00 minimum

    Returns:
        TradingCosts with default configuration
    """
    return TradingCosts(
        slippage_model=SlippageModel.FIXED_PCT,
        slippage_bps=Decimal("5.0"),
        commission_model=CommissionModel.PER_SHARE,
        commission_per_share=Decimal("0.005"),
        commission_minimum=Decimal("1.00"),
    )


def get_zero_costs() -> TradingCosts:
    """Get zero-cost configuration for theoretical backtesting.

    Useful for strategy development without cost considerations.

    Returns:
        TradingCosts with all costs disabled
    """
    return TradingCosts(
        slippage_model=SlippageModel.NONE,
        commission_model=CommissionModel.NONE,
    )


def get_institutional_costs() -> TradingCosts:
    """Get institutional trading costs (lower than retail).

    Returns institutional-grade costs:
    - Slippage: 0.02% (2 basis points) fixed
    - Commission: $0.001/share with $0.50 minimum

    Returns:
        TradingCosts with institutional configuration
    """
    return TradingCosts(
        slippage_model=SlippageModel.FIXED_PCT,
        slippage_bps=Decimal("2.0"),
        commission_model=CommissionModel.PER_SHARE,
        commission_per_share=Decimal("0.001"),
        commission_minimum=Decimal("0.50"),
    )
