"""Portfolio analytics calculations.

This module calculates portfolio metrics including value, beta, volatility,
sector exposure, and concentration risk.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from .models import (
    ConcentrationMetrics,
    PortfolioValue,
    Position,
    PriceData,
)
from .models import (
    PortfolioAnalytics as PortfolioAnalyticsModel,
)

logger = logging.getLogger(__name__)


class PortfolioAnalytics:
    """Calculates portfolio analytics and risk metrics.

    Provides methods for calculating portfolio value, beta, volatility,
    sector exposure, and concentration risk.
    """

    def calculate_portfolio_value(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> PortfolioValue:
        """Calculate total portfolio value and P&L.

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData

        Returns:
            PortfolioValue with total value, cost basis, and gains
        """
        total_value = 0.0
        total_cost_basis = 0.0

        for position in positions:
            price = price_data.get(position.symbol)
            if not price:
                logger.warning(
                    f"No price data for {position.symbol}, skipping from value calculation"
                )
                continue

            # Calculate position value
            position_value = position.shares * price.price
            position_cost = position.shares * position.cost_basis

            # Handle long/short positions
            if position.position_type == "short":
                position_value = -position_value
                position_cost = -position_cost

            total_value += position_value
            total_cost_basis += position_cost

        total_gain = total_value - total_cost_basis
        total_gain_pct = (
            (total_gain / total_cost_basis * 100) if total_cost_basis != 0 else 0.0
        )

        return PortfolioValue(
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            total_gain=total_gain,
            total_gain_pct=total_gain_pct,
        )

    def calculate_portfolio_beta(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> float | None:
        """Calculate portfolio beta (weighted average of position betas).

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData

        Returns:
            Portfolio beta, or None if insufficient data
        """
        total_value = 0.0
        weighted_beta_sum = 0.0

        for position in positions:
            price = price_data.get(position.symbol)
            if not price or price.beta is None:
                continue

            position_value = position.shares * price.price
            total_value += position_value
            weighted_beta_sum += position_value * price.beta

        if total_value == 0:
            return None

        return weighted_beta_sum / total_value

    def calculate_portfolio_volatility(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> float | None:
        """Calculate portfolio volatility (weighted average).

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData

        Returns:
            Portfolio volatility, or None if insufficient data
        """
        total_value = 0.0
        weighted_vol_sum = 0.0

        for position in positions:
            price = price_data.get(position.symbol)
            if not price or price.volatility is None:
                continue

            position_value = position.shares * price.price
            total_value += position_value
            weighted_vol_sum += position_value * price.volatility

        if total_value == 0:
            return None

        return weighted_vol_sum / total_value

    def calculate_sector_exposure(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> dict[str, float]:
        """Calculate percentage exposure by sector.

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData

        Returns:
            Dictionary mapping sector to percentage exposure
        """
        sector_values: dict[str, float] = defaultdict(float)
        total_value = 0.0

        for position in positions:
            price = price_data.get(position.symbol)
            if not price:
                continue

            position_value = position.shares * price.price
            sector = price.sector or "Unknown"

            sector_values[sector] += position_value
            total_value += position_value

        if total_value == 0:
            return {}

        # Convert to percentages
        sector_pct = {
            sector: (value / total_value * 100) for sector, value in sector_values.items()
        }

        return sector_pct

    def calculate_concentration_risk(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> ConcentrationMetrics:
        """Calculate portfolio concentration risk metrics.

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData

        Returns:
            ConcentrationMetrics with top holdings percentages and Herfindahl index
        """
        # Calculate position values
        position_values: list[tuple[str, float]] = []
        total_value = 0.0

        for position in positions:
            price = price_data.get(position.symbol)
            if not price:
                continue

            position_value = position.shares * price.price
            position_values.append((position.symbol, position_value))
            total_value += position_value

        if total_value == 0:
            return ConcentrationMetrics(
                top_holding_pct=0.0,
                top_3_pct=0.0,
                top_10_pct=0.0,
                herfindahl_index=0.0,
            )

        # Sort by value descending
        position_values.sort(key=lambda x: x[1], reverse=True)

        # Calculate top holdings percentages
        top_holding_pct = (position_values[0][1] / total_value * 100) if position_values else 0.0
        top_3_pct = (
            sum(v for _, v in position_values[:3]) / total_value * 100
            if len(position_values) >= 3
            else sum(v for _, v in position_values) / total_value * 100
        )
        top_10_pct = (
            sum(v for _, v in position_values[:10]) / total_value * 100
            if len(position_values) >= 10
            else sum(v for _, v in position_values) / total_value * 100
        )

        # Calculate Herfindahl-Hirschman Index (HHI)
        # Sum of squared market shares (0-10000 scale)
        herfindahl_index = sum(
            ((value / total_value * 100) ** 2) for _, value in position_values
        )

        return ConcentrationMetrics(
            top_holding_pct=top_holding_pct,
            top_3_pct=top_3_pct,
            top_10_pct=top_10_pct,
            herfindahl_index=herfindahl_index,
        )

    def calculate_full_analytics(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> PortfolioAnalyticsModel:
        """Calculate complete portfolio analytics.

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData

        Returns:
            PortfolioAnalyticsModel with all analytics
        """
        portfolio_value = self.calculate_portfolio_value(positions, price_data)
        portfolio_beta = self.calculate_portfolio_beta(positions, price_data)
        portfolio_volatility = self.calculate_portfolio_volatility(positions, price_data)
        sector_exposure = self.calculate_sector_exposure(positions, price_data)
        concentration_metrics = self.calculate_concentration_risk(positions, price_data)

        # Count unique symbols
        symbols = {p.symbol for p in positions}

        return PortfolioAnalyticsModel(
            portfolio_value=portfolio_value,
            portfolio_beta=portfolio_beta,
            portfolio_volatility=portfolio_volatility,
            sector_exposure=sector_exposure,
            concentration_metrics=concentration_metrics,
            num_positions=len(positions),
            num_symbols=len(symbols),
        )
