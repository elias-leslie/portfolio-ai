"""Stress testing framework for GAP-027.

Implements scenario-based stress testing to evaluate portfolio resilience
under historical crisis conditions and hypothetical scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


class StressScenario(Enum):
    """Pre-defined stress scenarios based on historical crises."""

    # Historical scenarios with approximate market impacts
    FINANCIAL_CRISIS_2008 = "2008_financial_crisis"  # SPY -57%, VIX 80+
    COVID_CRASH_2020 = "2020_covid_crash"  # SPY -34%, VIX 82
    DOT_COM_BUST_2000 = "2000_dot_com"  # NASDAQ -78%, tech devastation
    FLASH_CRASH_2010 = "2010_flash_crash"  # SPY -9% intraday
    RATE_HIKE_2022 = "2022_rate_hike"  # SPY -25%, tech -35%

    # Hypothetical scenarios
    EXTREME_VOLATILITY = "extreme_vix"  # VIX spikes to 80
    SECTOR_CRASH_TECH = "tech_crash"  # Tech -50%, others -15%
    CORRELATION_SPIKE = "correlation_shock"  # All correlations -> 0.9
    LIQUIDITY_CRISIS = "liquidity_crisis"  # 10% bid-ask spreads


@dataclass
class ScenarioShocks:
    """Defines the shocks applied in a stress scenario."""

    name: str
    description: str
    market_shock: float  # Overall market decline (e.g., -0.50 = 50% drop)
    sector_shocks: dict[str, float] = field(default_factory=dict)  # Per-sector adjustments
    vix_level: float = 30.0  # Implied VIX during scenario
    correlation_override: float | None = None  # Force all correlations to this value
    duration_days: int = 30  # Scenario duration for recovery analysis


# Pre-defined scenario parameters
SCENARIO_DEFINITIONS: dict[StressScenario, ScenarioShocks] = {
    StressScenario.FINANCIAL_CRISIS_2008: ScenarioShocks(
        name="2008 Financial Crisis",
        description="Lehman collapse, credit freeze, global contagion",
        market_shock=-0.57,
        sector_shocks={
            "Financial Services": -0.80,
            "Real Estate": -0.65,
            "Consumer Cyclical": -0.55,
            "Technology": -0.45,
            "Healthcare": -0.35,
            "Utilities": -0.25,
            "Consumer Defensive": -0.30,
        },
        vix_level=80.0,
        correlation_override=0.85,
        duration_days=365,
    ),
    StressScenario.COVID_CRASH_2020: ScenarioShocks(
        name="COVID-19 Market Crash",
        description="Pandemic shutdown, fastest bear market in history",
        market_shock=-0.34,
        sector_shocks={
            "Energy": -0.60,
            "Real Estate": -0.40,
            "Financial Services": -0.35,
            "Consumer Cyclical": -0.40,
            "Industrials": -0.35,
            "Technology": -0.25,
            "Healthcare": -0.20,
            "Consumer Defensive": -0.15,
        },
        vix_level=82.0,
        correlation_override=0.90,
        duration_days=33,  # V-shaped recovery
    ),
    StressScenario.DOT_COM_BUST_2000: ScenarioShocks(
        name="Dot-Com Bust",
        description="Tech bubble collapse, multi-year bear market",
        market_shock=-0.50,
        sector_shocks={
            "Technology": -0.78,
            "Communication Services": -0.70,
            "Consumer Cyclical": -0.45,
            "Financial Services": -0.30,
            "Healthcare": -0.25,
            "Utilities": -0.10,
            "Energy": 0.05,  # Energy actually rallied
        },
        vix_level=45.0,
        duration_days=900,  # Long recovery
    ),
    StressScenario.FLASH_CRASH_2010: ScenarioShocks(
        name="Flash Crash",
        description="Algorithmic trading cascade, intraday liquidity crisis",
        market_shock=-0.09,
        sector_shocks={},  # Broad-based
        vix_level=40.0,
        correlation_override=0.95,  # Everything drops together
        duration_days=1,
    ),
    StressScenario.RATE_HIKE_2022: ScenarioShocks(
        name="2022 Rate Hike Cycle",
        description="Fed tightening, growth stock selloff",
        market_shock=-0.25,
        sector_shocks={
            "Technology": -0.35,
            "Communication Services": -0.40,
            "Consumer Cyclical": -0.30,
            "Real Estate": -0.30,
            "Financial Services": -0.15,
            "Energy": 0.30,  # Energy rallied on inflation
            "Utilities": -0.05,
        },
        vix_level=35.0,
        duration_days=270,
    ),
    StressScenario.EXTREME_VOLATILITY: ScenarioShocks(
        name="Extreme Volatility Scenario",
        description="Hypothetical VIX spike to crisis levels",
        market_shock=-0.20,
        sector_shocks={},
        vix_level=80.0,
        correlation_override=0.80,
        duration_days=14,
    ),
    StressScenario.SECTOR_CRASH_TECH: ScenarioShocks(
        name="Tech Sector Crash",
        description="Hypothetical tech-specific selloff",
        market_shock=-0.15,
        sector_shocks={
            "Technology": -0.50,
            "Communication Services": -0.45,
            "Consumer Cyclical": -0.25,
        },
        vix_level=40.0,
        duration_days=60,
    ),
    StressScenario.CORRELATION_SPIKE: ScenarioShocks(
        name="Correlation Spike",
        description="Diversification failure - all assets move together",
        market_shock=-0.30,
        sector_shocks={},
        vix_level=50.0,
        correlation_override=0.95,
        duration_days=30,
    ),
    StressScenario.LIQUIDITY_CRISIS: ScenarioShocks(
        name="Liquidity Crisis",
        description="Market-wide bid-ask spread blowout",
        market_shock=-0.25,
        sector_shocks={},
        vix_level=60.0,
        duration_days=14,
    ),
}


@dataclass
class PositionStressResult:
    """Stress test results for a single position."""

    ticker: str
    sector: str
    current_value: float
    stressed_value: float
    loss_amount: float
    loss_pct: float


@dataclass
class PortfolioStressResult:
    """Aggregate stress test results for the portfolio."""

    scenario: StressScenario
    scenario_name: str
    description: str
    total_current_value: float
    total_stressed_value: float
    portfolio_loss_pct: float
    vix_level: float
    position_results: list[PositionStressResult]
    worst_positions: list[PositionStressResult]
    resilience_score: int  # 0-100


def run_stress_test(
    positions: list[dict[str, Any]],
    scenario: StressScenario,
) -> PortfolioStressResult:
    """Run a stress test scenario on portfolio positions.

    Args:
        positions: List of position dicts with keys:
            - ticker: str
            - sector: str
            - current_value: float
        scenario: StressScenario to apply

    Returns:
        PortfolioStressResult with detailed breakdown
    """
    shocks = SCENARIO_DEFINITIONS[scenario]
    position_results: list[PositionStressResult] = []
    total_current = 0.0
    total_stressed = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        sector = pos.get("sector", "Unknown")
        current_value = pos["current_value"]

        # Calculate shock for this position
        sector_shock = shocks.sector_shocks.get(sector, shocks.market_shock)

        # Apply shock
        stressed_value = current_value * (1 + sector_shock)
        loss_amount = current_value - stressed_value
        loss_pct = sector_shock

        position_results.append(
            PositionStressResult(
                ticker=ticker,
                sector=sector,
                current_value=current_value,
                stressed_value=stressed_value,
                loss_amount=loss_amount,
                loss_pct=loss_pct,
            )
        )

        total_current += current_value
        total_stressed += stressed_value

    # Calculate portfolio-level metrics
    portfolio_loss_pct = (
        (total_stressed - total_current) / total_current if total_current > 0 else 0
    )

    # Sort to find worst positions
    worst_positions = sorted(position_results, key=lambda x: x.loss_pct)[:5]

    # Calculate resilience score (0-100)
    # Based on: portfolio loss severity vs scenario benchmark
    resilience_score = calculate_resilience_score(portfolio_loss_pct, shocks)

    return PortfolioStressResult(
        scenario=scenario,
        scenario_name=shocks.name,
        description=shocks.description,
        total_current_value=total_current,
        total_stressed_value=total_stressed,
        portfolio_loss_pct=portfolio_loss_pct,
        vix_level=shocks.vix_level,
        position_results=position_results,
        worst_positions=worst_positions,
        resilience_score=resilience_score,
    )


def calculate_resilience_score(portfolio_loss_pct: float, shocks: ScenarioShocks) -> int:
    """Calculate portfolio resilience score (0-100).

    100 = Portfolio losses less than market
    50 = Portfolio losses equal to market
    0 = Portfolio losses 2x market or worse
    """
    market_loss = abs(shocks.market_shock)
    portfolio_loss = abs(portfolio_loss_pct)

    if market_loss == 0:
        return 50

    # Ratio of portfolio loss to market loss
    loss_ratio = portfolio_loss / market_loss

    if loss_ratio <= 0.5:
        return 100  # Half the market loss = excellent
    if loss_ratio <= 1.0:
        # Linear scale from 100 (0.5x) to 50 (1.0x)
        return int(100 - (loss_ratio - 0.5) * 100)
    if loss_ratio <= 2.0:
        # Linear scale from 50 (1.0x) to 0 (2.0x)
        return int(50 - (loss_ratio - 1.0) * 50)
    return 0


def run_all_stress_tests(
    positions: list[dict[str, Any]],
) -> list[PortfolioStressResult]:
    """Run all stress scenarios and return results.

    Args:
        positions: List of position dicts

    Returns:
        List of PortfolioStressResult for each scenario
    """
    results = []
    for scenario in StressScenario:
        result = run_stress_test(positions, scenario)
        results.append(result)
        logger.info(
            "stress_test_complete",
            scenario=scenario.value,
            loss_pct=f"{result.portfolio_loss_pct:.1%}",
            resilience=result.resilience_score,
        )

    return results


def get_stress_test_summary(results: list[PortfolioStressResult]) -> dict[str, Any]:
    """Generate summary of all stress test results.

    Args:
        results: List of PortfolioStressResult

    Returns:
        Summary dict with worst-case, average, and overall resilience
    """
    if not results:
        return {"error": "No stress test results"}

    worst_case = min(results, key=lambda r: r.portfolio_loss_pct)
    avg_loss = sum(r.portfolio_loss_pct for r in results) / len(results)
    avg_resilience = sum(r.resilience_score for r in results) / len(results)

    return {
        "total_scenarios": len(results),
        "worst_case_scenario": worst_case.scenario_name,
        "worst_case_loss_pct": worst_case.portfolio_loss_pct,
        "average_loss_pct": avg_loss,
        "average_resilience_score": avg_resilience,
        "overall_rating": (
            "RESILIENT"
            if avg_resilience >= 70
            else "MODERATE"
            if avg_resilience >= 40
            else "VULNERABLE"
        ),
    }
