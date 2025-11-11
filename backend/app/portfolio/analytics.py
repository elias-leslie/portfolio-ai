"""Portfolio analytics calculations.

This module calculates portfolio metrics including value, beta, volatility,
sector exposure, and concentration risk.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from ..logging_config import get_logger
from .models import (
    ConcentrationMetrics,
    DiversificationScore,
    PortfolioValue,
    Position,
    PositionPerformance,
    PriceData,
    RiskProfile,
)
from .models import (
    PortfolioAnalytics as PortfolioAnalyticsModel,
)

logger = get_logger(__name__)


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

            # Skip positions with price errors
            if price.error:
                logger.warning(
                    f"Price error for {position.symbol}: {price.error}, skipping from value calculation"
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
        total_gain_pct = (total_gain / total_cost_basis * 100) if total_cost_basis != 0 else 0.0

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
            if not price or price.beta is None or price.error:
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
            if not price or price.volatility is None or price.error:
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
            if not price or price.error:
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
            if not price or price.error:
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
        herfindahl_index = sum(((value / total_value * 100) ** 2) for _, value in position_values)

        return ConcentrationMetrics(
            top_holding_pct=top_holding_pct,
            top_3_pct=top_3_pct,
            top_10_pct=top_10_pct,
            herfindahl_index=herfindahl_index,
        )

    def calculate_sharpe_ratio(
        self,
        portfolio_value: PortfolioValue,
        portfolio_volatility: float | None,
        risk_free_rate: float = 0.045,
    ) -> float | None:
        """Calculate Sharpe ratio (simplified version).

        Args:
            portfolio_value: Portfolio value with gain percentage
            portfolio_volatility: Portfolio volatility (annualized)
            risk_free_rate: Risk-free rate (default: 4.5% current T-bill rate)

        Returns:
            Sharpe ratio, or None if insufficient data
        """
        if portfolio_volatility is None or portfolio_volatility == 0:
            return None

        # Convert gain_pct to annualized return (assuming gain_pct is total return)
        # For simplicity, using the gain_pct as-is (could enhance with time-weighted returns)
        portfolio_return = portfolio_value.total_gain_pct / 100.0
        excess_return = portfolio_return - risk_free_rate

        return excess_return / portfolio_volatility

    def calculate_risk_profile(
        self,
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
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
        concentration_metrics: ConcentrationMetrics,
    ) -> DiversificationScore:
        """Calculate diversification score.

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData
            concentration_metrics: Concentration metrics

        Returns:
            DiversificationScore assessment
        """
        # Count unique sectors
        sectors = set()
        for position in positions:
            price = price_data.get(position.symbol)
            if price and not price.error:
                sectors.add(price.sector or "Unknown")

        num_holdings = len(positions)
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
        )

    def calculate_top_performers(
        self,
        positions: list[Position],
        price_data: dict[str, PriceData],
        top_n: int = 3,
    ) -> tuple[list[PositionPerformance], list[PositionPerformance]]:
        """Calculate top and bottom performing positions.

        Args:
            positions: List of portfolio positions
            price_data: Dictionary mapping symbol to PriceData
            top_n: Number of top/bottom performers to return

        Returns:
            Tuple of (top_performers, bottom_performers)
        """
        performances: list[PositionPerformance] = []
        total_value = 0.0

        # Calculate performance for each position
        for position in positions:
            price = price_data.get(position.symbol)
            if not price or price.error:
                continue

            current_value = position.shares * price.price
            cost = position.shares * position.cost_basis
            gain_amount = current_value - cost
            gain_pct = (gain_amount / cost * 100) if cost != 0 else 0.0

            total_value += current_value

            performances.append(
                PositionPerformance(
                    symbol=position.symbol,
                    gain_pct=gain_pct,
                    gain_amount=gain_amount,
                    current_value=current_value,
                    weight_pct=0.0,  # Will be calculated after
                )
            )

        # Calculate weight percentages
        if total_value > 0:
            for perf in performances:
                perf.weight_pct = (perf.current_value / total_value) * 100

        # Sort by gain percentage
        performances.sort(key=lambda x: x.gain_pct, reverse=True)

        top_performers = performances[:top_n]
        bottom_performers = performances[-top_n:][::-1]  # Reverse to show worst first

        return top_performers, bottom_performers

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

        # Calculate new metrics
        sharpe_ratio = self.calculate_sharpe_ratio(portfolio_value, portfolio_volatility)
        risk_profile = self.calculate_risk_profile(
            portfolio_beta, portfolio_volatility, concentration_metrics
        )
        diversification_score = self.calculate_diversification_score(
            positions, price_data, concentration_metrics
        )
        top_performers, bottom_performers = self.calculate_top_performers(positions, price_data)

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
