"""Portfolio risk and diversification calculations.

This module handles calculations related to portfolio risk metrics,
concentration, diversification, and exposure analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from app.analytics.calculation_engine import calculate_portfolio_sharpe

from .current_facts import calculate_current_position_fact
from .fund_lookthrough import ExposureItem, build_exposure_breakdown
from .models import (
    ConcentrationMetrics,
    DiversificationScore,
    PortfolioValue,
    Position,
    PriceData,
    RiskProfile,
)

if TYPE_CHECKING:
    from ..storage import PortfolioStorage


def calculate_sector_exposure(
    positions: list[Position],
    price_data: dict[str, PriceData],
    storage: PortfolioStorage | None = None,
) -> dict[str, float]:
    """Calculate percentage exposure by sector.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData

    Returns:
        Dictionary mapping sector to percentage exposure
    """
    items: list[ExposureItem] = []
    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.error:
            continue

        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue

        items.append(
            ExposureItem(
                symbol=position.symbol,
                current_value=abs(current_fact.current_value),
                sector=price.sector,
            )
        )

    breakdown = build_exposure_breakdown(items, storage)
    sector_values = breakdown.sector_values
    total_value = breakdown.total_value

    if total_value == 0:
        return {}

    # Convert to percentages
    sector_pct = {sector: (value / total_value * 100) for sector, value in sector_values.items()}

    return sector_pct


def calculate_concentration_risk(
    positions: list[Position],
    price_data: dict[str, PriceData],
    storage: PortfolioStorage | None = None,
) -> ConcentrationMetrics:
    """Calculate portfolio concentration risk metrics.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData

    Returns:
        ConcentrationMetrics with top holdings percentages and Herfindahl index
    """
    items: list[ExposureItem] = []
    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.error:
            continue

        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue

        items.append(
            ExposureItem(
                symbol=position.symbol,
                current_value=abs(current_fact.current_value),
                sector=price.sector,
            )
        )

    breakdown = build_exposure_breakdown(items, storage)
    total_value = breakdown.total_value
    vehicle_values = breakdown.vehicle_values

    if total_value == 0:
        return ConcentrationMetrics(
            top_holding_pct=0.0,
            top_3_pct=0.0,
            top_10_pct=0.0,
            herfindahl_index=0.0,
        )

    def summarize_bucket_values(
        bucket_values: dict[str, float],
    ) -> tuple[str | None, float, float, float, float]:
        position_values = sorted(
            bucket_values.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if not position_values:
            return None, 0.0, 0.0, 0.0, 0.0

        top_name = position_values[0][0]
        top_holding_pct = (position_values[0][1] / total_value) * 100
        top_3_pct = (sum(value for _, value in position_values[:3]) / total_value) * 100
        top_10_pct = (sum(value for _, value in position_values[:10]) / total_value) * 100
        herfindahl_index = sum(
            ((value / total_value) * 100) ** 2 for _, value in position_values
        )
        return top_name, top_holding_pct, top_3_pct, top_10_pct, herfindahl_index

    (
        vehicle_top_name,
        vehicle_top_holding_pct,
        vehicle_top_3_pct,
        vehicle_top_10_pct,
        vehicle_herfindahl_index,
    ) = summarize_bucket_values(vehicle_values)

    lookthrough_available = breakdown.lookthrough_covered_value > 0 and bool(
        breakdown.single_name_values
    )
    if lookthrough_available:
        (
            top_holding_name,
            top_holding_pct,
            top_3_pct,
            top_10_pct,
            _,
        ) = summarize_bucket_values(breakdown.single_name_values)
        _, _, _, _, herfindahl_index = summarize_bucket_values(
            breakdown.risk_bucket_values
        )
    else:
        top_holding_name = vehicle_top_name
        top_holding_pct = vehicle_top_holding_pct
        top_3_pct = vehicle_top_3_pct
        top_10_pct = vehicle_top_10_pct
        herfindahl_index = vehicle_herfindahl_index

    return ConcentrationMetrics(
        top_holding_pct=top_holding_pct,
        top_3_pct=top_3_pct,
        top_10_pct=top_10_pct,
        herfindahl_index=herfindahl_index,
        method="lookthrough" if lookthrough_available else "line_item",
        top_holding_name=top_holding_name,
        vehicle_top_holding_pct=vehicle_top_holding_pct,
        vehicle_top_3_pct=vehicle_top_3_pct,
        vehicle_top_10_pct=vehicle_top_10_pct,
        vehicle_herfindahl_index=vehicle_herfindahl_index,
        vehicle_top_holding_name=vehicle_top_name,
        lookthrough_coverage_pct=(
            (breakdown.lookthrough_covered_value / total_value) * 100
            if total_value > 0
            else 0.0
        ),
    )


def calculate_sharpe_ratio(
    portfolio_value: PortfolioValue,
    portfolio_volatility: float | None,
    risk_free_rate: float = 0.045,
    storage: PortfolioStorage | None = None,
    account_ids: list[str] | None = None,
) -> float | None:
    """Calculate Sharpe ratio from historical portfolio equity snapshots.

    Args:
        portfolio_value: Portfolio value with gain percentage
        portfolio_volatility: Portfolio volatility (annualized)
        risk_free_rate: Risk-free rate (default: 4.5% current T-bill rate)
        storage: Optional storage for retrieving historical equity snapshots
        account_ids: Optional account IDs included in the portfolio view

    Returns:
        Sharpe ratio, or None if insufficient historical data
    """
    if portfolio_volatility is None or portfolio_volatility == 0:
        return None

    if storage is None or not account_ids:
        return None
    return calculate_portfolio_sharpe(storage, account_ids, risk_free_rate)


def calculate_risk_profile(
    portfolio_beta: float | None,
    portfolio_volatility: float | None,
    concentration_metrics: ConcentrationMetrics,
) -> RiskProfile | None:
    """Calculate portfolio risk profile.

    Args:
        portfolio_beta: Portfolio beta
        portfolio_volatility: Portfolio volatility
        concentration_metrics: Concentration metrics

    Returns:
        RiskProfile assessment, or None if insufficient data
    """
    if portfolio_beta is None or portfolio_volatility is None:
        return None

    # Calculate risk score (0-100)
    # Beta weight: 40%, Volatility weight: 40%, Concentration weight: 20%
    beta_score = min(100, (portfolio_beta / 2.0) * 100)  # Beta > 2.0 = 100
    vol_score = min(100, (portfolio_volatility / 0.5) * 100)  # Vol > 50% = 100
    conc_score = min(100, concentration_metrics.herfindahl_index / 25.0)  # HHI > 2500 = 100

    risk_score = (beta_score * 0.4) + (vol_score * 0.4) + (conc_score * 0.2)

    # Determine risk level
    level: Literal["Conservative", "Moderate", "Aggressive", "Very Aggressive"]
    if risk_score < 25:
        level = "Conservative"
    elif risk_score < 50:
        level = "Moderate"
    elif risk_score < 75:
        level = "Aggressive"
    else:
        level = "Very Aggressive"

    # Build factors explanation
    factors = {}
    if portfolio_beta < 0.8:
        factors["beta"] = "Low market sensitivity"
    elif portfolio_beta > 1.2:
        factors["beta"] = "High market sensitivity"
    else:
        factors["beta"] = "Moderate market sensitivity"

    if portfolio_volatility < 0.15:
        factors["volatility"] = "Low volatility"
    elif portfolio_volatility > 0.30:
        factors["volatility"] = "High volatility"
    else:
        factors["volatility"] = "Moderate volatility"

    if concentration_metrics.herfindahl_index > 2500:
        factors["concentration"] = "Highly concentrated"
    elif concentration_metrics.herfindahl_index < 1000:
        factors["concentration"] = "Well diversified"
    else:
        factors["concentration"] = "Moderately diversified"

    return RiskProfile(level=level, score=risk_score, factors=factors)


def calculate_diversification_score(
    positions: list[Position],
    price_data: dict[str, PriceData],
    concentration_metrics: ConcentrationMetrics,
    storage: PortfolioStorage | None = None,
) -> DiversificationScore:
    """Calculate diversification score.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData
        concentration_metrics: Concentration metrics

    Returns:
        DiversificationScore assessment
    """
    items: list[ExposureItem] = []
    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.error:
            continue
        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue
        items.append(
            ExposureItem(
                symbol=position.symbol,
                current_value=abs(current_fact.current_value),
                sector=price.sector,
            )
        )

    breakdown = build_exposure_breakdown(items, storage)
    if concentration_metrics.method == "lookthrough" and breakdown.total_value > 0:
        num_holdings = len(breakdown.risk_bucket_values)
        num_sectors = len(breakdown.sector_values)
    else:
        holdings = set()
        sectors = set()
        for position in positions:
            price = price_data.get(position.symbol)
            if price and not price.error:
                holdings.add(position.symbol.upper())
                sectors.add(price.sector or "Unknown")
        num_holdings = len(holdings)
        num_sectors = len(sectors)

    # Calculate score based on:
    # 1. Number of holdings (40%)
    # 2. Sector diversity (30%)
    # 3. Herfindahl Index (30%)

    # Holdings score: diminishing returns after 20 holdings
    holdings_score = min(100, (num_holdings / 20.0) * 100)

    # Sector score: diminishing returns after 8 sectors
    sector_score = min(100, (num_sectors / 8.0) * 100)

    # HHI score: lower is better (inverted)
    # HHI < 1000 = excellent, > 2500 = poor
    hhi_score = max(0, 100 - (concentration_metrics.herfindahl_index / 25.0))

    score = (holdings_score * 0.4) + (sector_score * 0.3) + (hhi_score * 0.3)

    # Determine level
    level: Literal["Poor", "Fair", "Good", "Excellent"]
    if score >= 75:
        level = "Excellent"
    elif score >= 50:
        level = "Good"
    elif score >= 25:
        level = "Fair"
    else:
        level = "Poor"

    return DiversificationScore(
        score=score,
        level=level,
        num_holdings=num_holdings,
        num_sectors=num_sectors,
        method=concentration_metrics.method,
        lookthrough_coverage_pct=concentration_metrics.lookthrough_coverage_pct,
    )
