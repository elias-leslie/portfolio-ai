"""Portfolio analytics calculations.

This module calculates portfolio metrics including value, beta, volatility,
sector exposure, and concentration risk.

The implementation is split across focused modules:
- analytics_returns: Value and performance calculations
- analytics_risk: Risk and diversification calculations
"""

from __future__ import annotations

from .analytics_returns import (
    calculate_portfolio_beta,
    calculate_portfolio_value,
    calculate_portfolio_volatility,
    calculate_top_performers,
)
from .analytics_risk import (
    calculate_concentration_risk,
    calculate_diversification_score,
    calculate_risk_profile,
    calculate_sector_exposure,
    calculate_sharpe_ratio,
)
from .models import Position, PriceData
from .models import PortfolioAnalytics as PortfolioAnalyticsModel


class PortfolioAnalytics:
    """Calculates portfolio analytics and risk metrics.

    Provides methods for calculating portfolio value, beta, volatility,
    sector exposure, and concentration risk. Delegates to specialized
    calculation modules for returns and risk metrics.
    """

    def calculate_portfolio_value(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> PriceData:
        """Calculate total portfolio value and P&L."""
        return calculate_portfolio_value(positions, price_data)

    def calculate_portfolio_beta(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> float | None:
        """Calculate portfolio beta (weighted average of position betas)."""
        return calculate_portfolio_beta(positions, price_data)

    def calculate_portfolio_volatility(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> float | None:
        """Calculate portfolio volatility (weighted average)."""
        return calculate_portfolio_volatility(positions, price_data)

    def calculate_sector_exposure(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> dict[str, float]:
        """Calculate percentage exposure by sector."""
        return calculate_sector_exposure(positions, price_data)

    def calculate_concentration_risk(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
    ) -> PriceData:
        """Calculate portfolio concentration risk metrics."""
        return calculate_concentration_risk(positions, price_data)

    def calculate_sharpe_ratio(
        self,
        portfolio_value: PriceData,
        portfolio_volatility: float | None,
        risk_free_rate: float = 0.045,
    ) -> float | None:
        """Calculate Sharpe ratio (simplified version)."""
        return calculate_sharpe_ratio(portfolio_value, portfolio_volatility, risk_free_rate)

    def calculate_risk_profile(
        self,
        portfolio_beta: float | None,
        portfolio_volatility: float | None,
        concentration_metrics: PriceData,
    ) -> PriceData | None:
        """Calculate portfolio risk profile."""
        return calculate_risk_profile(portfolio_beta, portfolio_volatility, concentration_metrics)

    def calculate_diversification_score(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
        concentration_metrics: PriceData,
    ) -> PriceData:
        """Calculate diversification score."""
        return calculate_diversification_score(positions, price_data, concentration_metrics)

    def calculate_top_performers(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
        top_n: int = 3,
    ) -> tuple[list[PriceData], list[PriceData]]:
        """Calculate top and bottom performing positions."""
        return calculate_top_performers(positions, price_data, top_n)

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
        portfolio_value = calculate_portfolio_value(positions, price_data)
        portfolio_beta = calculate_portfolio_beta(positions, price_data)
        portfolio_volatility = calculate_portfolio_volatility(positions, price_data)
        sector_exposure = calculate_sector_exposure(positions, price_data)
        concentration_metrics = calculate_concentration_risk(positions, price_data)

        # Calculate new metrics
        sharpe_ratio = calculate_sharpe_ratio(portfolio_value, portfolio_volatility)
        risk_profile = calculate_risk_profile(
            portfolio_beta, portfolio_volatility, concentration_metrics
        )
        diversification_score = calculate_diversification_score(
            positions, price_data, concentration_metrics
        )
        top_performers, bottom_performers = calculate_top_performers(positions, price_data)

        # Count unique symbols
        symbols = {p.symbol for p in positions}

        return PortfolioAnalyticsModel(
            portfolio_value=portfolio_value,
            portfolio_beta=portfolio_beta,
            portfolio_volatility=portfolio_volatility,
            sharpe_ratio=sharpe_ratio,
            sector_exposure=sector_exposure,
            concentration_metrics=concentration_metrics,
            risk_profile=risk_profile,
            diversification_score=diversification_score,
            top_performers=top_performers,
            bottom_performers=bottom_performers,
            num_positions=len(positions),
            num_symbols=len(symbols),
        )
