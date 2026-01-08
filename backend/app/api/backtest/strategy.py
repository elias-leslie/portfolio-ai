"""
Strategy metadata endpoints.

Provides detailed strategy information for UI and AI agent consumption.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.backtest.models import StrategyDetailsResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtest"])


# Strategy details - matching frontend STRATEGIES constant
STRATEGY_DETAILS = {
    "enhanced": StrategyDetailsResponse(
        id="enhanced",
        name="Enhanced Signal",
        short_description="Multi-confirmation technical strategy with configurable parameters",
        when_to_use="Default choice for most backtests. Use when you want balanced risk/reward with tunable parameters.",
        market_conditions="Works in trending and range-bound markets. Requires 5+ of 8 technical confirmations (price > EMA, healthy RSI, positive MACD, volume, momentum alignment).",
        holding_period="5-30 days typical, configurable up to 120 days",
        risk_level="Medium",
        best_for="Stocks with clear technical patterns, moderate volatility (ATR 2-4%), good liquidity (>1M daily volume)",
        avoid_when="Choppy sideways markets, low-volume stocks, earnings week, extreme VIX (>30)",
    ),
    "signal_classifier": StrategyDetailsResponse(
        id="signal_classifier",
        name="Signal Classifier",
        short_description="Original rule-based classifier requiring 10+ confirmations including fundamentals",
        when_to_use="Use when you have fundamental data available and want stricter entry criteria.",
        market_conditions="Requires fundamental/analyst data for full scoring. Technical-only mode generates fewer signals. Best in stable uptrends.",
        holding_period="30-60 days typical",
        risk_level="Low",
        best_for="Blue-chip stocks with analyst coverage, stocks with recent earnings beats, sectors showing institutional accumulation",
        avoid_when="Small-caps without analyst coverage, pre-earnings periods, sectors under regulatory scrutiny",
    ),
    "momentum": StrategyDetailsResponse(
        id="momentum",
        name="Momentum",
        short_description="Rides intermediate-term momentum with multi-horizon confirmation",
        when_to_use="Use in strong bull markets or when a stock is breaking out of consolidation with volume.",
        market_conditions="Best when: SPY > 200 SMA, sector showing relative strength, stock RSI 50-70 (bullish but not overbought). Uses 20/60/252-day momentum scoring.",
        holding_period="30-60 days, exits on momentum fade (RSI < 40)",
        risk_level="High",
        best_for="Growth stocks in uptrends, sector leaders, stocks with institutional buying, post-earnings momentum plays",
        avoid_when="Bear markets, mean-reverting sectors (utilities), stocks with declining volume, late-cycle rallies",
    ),
    "mean_reversion": StrategyDetailsResponse(
        id="mean_reversion",
        name="Mean Reversion",
        short_description="Catches oversold bounces in fundamentally strong stocks",
        when_to_use="Use when quality stocks are temporarily oversold (RSI < 30) but still in long-term uptrend (price > 200 SMA).",
        market_conditions="Best in: range-bound markets, after sector pullbacks, when VIX spikes then reverses. Requires uptrend context to avoid catching falling knives.",
        holding_period="3-10 days (quick trades), tight stops",
        risk_level="Medium",
        best_for="Large-caps with temporary weakness, dividend stocks after ex-date drops, quality names hit by sector rotation",
        avoid_when="Downtrending stocks (price < 200 SMA), fundamental deterioration, high-beta names in bear markets",
    ),
    "trend_following": StrategyDetailsResponse(
        id="trend_following",
        name="Trend Following",
        short_description="Follows strong trends with trailing ATR stops, lets winners run",
        when_to_use="Use for long-term trend capture when all moving averages are aligned (price > 20 SMA > 50 SMA > 200 SMA).",
        market_conditions="Best in: strong bull markets, sector rotations with clear leaders, breakouts from long bases. Requires perfect SMA alignment for entry.",
        holding_period="60-120+ days, no fixed profit target",
        risk_level="Medium",
        best_for="Trending sectors (tech in bull markets), stocks making new highs, ETFs with clear directional bias",
        avoid_when="Choppy/sideways markets, stocks in trading ranges, high-volatility periods (earnings, FOMC), mean-reverting assets",
    ),
}


@router.get("/strategies", response_model=list[StrategyDetailsResponse])
async def get_available_strategies() -> list[StrategyDetailsResponse]:
    """Get list of available backtest strategies with detailed information.

    Returns detailed information about each strategy including:
    - When to use the strategy
    - Ideal market conditions
    - Typical holding period
    - Risk level
    - Best use cases and situations to avoid

    This endpoint is designed for both UI display and AI agent consumption.
    AI agents can use this data to recommend appropriate strategies based on
    current market conditions and user goals.

    Returns:
        List of strategy details
    """
    return list(STRATEGY_DETAILS.values())


@router.get("/strategies/{strategy_id}", response_model=StrategyDetailsResponse)
async def get_strategy_details(strategy_id: str) -> StrategyDetailsResponse:
    """Get detailed information about a specific strategy.

    Args:
        strategy_id: Strategy identifier (enhanced, signal_classifier, momentum, etc.)

    Returns:
        Strategy details

    Raises:
        HTTPException 404: Strategy not found
    """
    if strategy_id not in STRATEGY_DETAILS:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy_id}' not found. Available: {list(STRATEGY_DETAILS.keys())}",
        )
    return STRATEGY_DETAILS[strategy_id]
