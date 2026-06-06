"""Response models for market API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.market.sentiment import MarketHealthScore
from app.utils.market_hours import MarketStatus


# Market conditions endpoint
class MarketConditionsResponse(BaseModel):
    """Response model for market conditions."""

    sp500: dict[str, float | None | str] = Field(..., description="S&P 500 data")
    vix: dict[str, float | None | str] = Field(..., description="VIX volatility index")
    tnx: dict[str, float | None | str] = Field(..., description="10-Year Treasury yield")
    dxy: dict[str, float | None | str] = Field(..., description="US Dollar Index")
    health: MarketHealthScore = Field(..., description="Market health scoring")


# Prices endpoint
class PriceResponse(BaseModel):
    """Response model for price data."""

    symbol: str
    price: float
    beta: float | None
    volatility: float | None
    sector: str | None


class PricesResponse(BaseModel):
    """Response model for multiple prices."""

    prices: dict[str, PriceResponse]
    count: int


# Market status endpoint
class MarketStatusResponse(BaseModel):
    """Response model for market status endpoint."""

    status: MarketStatus = Field(..., description="Current market status")
    is_open: bool = Field(..., description="Whether market is currently open for regular trading")
    last_trading_day: str = Field(..., description="Most recent trading day (ISO format)")
    next_trading_day: str = Field(..., description="Next trading day (ISO format)")
    current_time_et: str = Field(..., description="Current time in Eastern Time")
    expected_data_date: str = Field(
        ..., description="Date that market data SHOULD be available for (ISO format)"
    )
    is_holiday: bool = Field(False, description="Whether today is a market holiday")
    holiday_name: str | None = Field(None, description="Holiday name if today is a holiday")
    is_early_close: bool = Field(False, description="Whether today is an early close day")
    early_close_name: str | None = Field(None, description="Early close day name if applicable")


# Fear & Greed history endpoint
class FearGreedHistoryResponse(BaseModel):
    """Response model for Fear & Greed history."""

    dates: list[str] = Field(..., description="ISO date strings")
    scores: list[float] = Field(..., description="Fear & Greed scores (0-100)")
    labels: list[str] = Field(..., description="Labels (Extreme Fear, Fear, etc.)")
    sources: list[str] = Field(
        default_factory=list,
        description="Per-point source: daily_close or live_proxy",
    )
    latest_source: str = Field(
        "daily_close",
        description="Source for the latest point",
    )
    latest_as_of: str | None = Field(None, description="Timestamp for the latest point")
    put_call_ratios: list[float | None] = Field(
        default_factory=list,
        description="Put/Call ratios (null if not available for that date)",
    )


class NewsSentimentHistoryResponse(BaseModel):
    """Response model for news sentiment history."""

    dates: list[str] = Field(..., description="ISO date strings")
    scores: list[float] = Field(..., description="Sentiment scores (-1 to +1)")
    positive_counts: list[int] = Field(..., description="Positive article counts per day")
    negative_counts: list[int] = Field(..., description="Negative article counts per day")
    article_counts: list[int] = Field(..., description="Total article counts per day")


# Indicator history endpoint
class IndicatorDataPoint(BaseModel):
    """Single data point for an indicator."""

    date: str
    close: float
    pct_change: float = Field(..., description="% change from period start")


class IndicatorHistoryResponse(BaseModel):
    """Response model for indicator history."""

    sp500: list[IndicatorDataPoint] = Field(default_factory=list)
    vix: list[IndicatorDataPoint] = Field(default_factory=list)
    tnx: list[IndicatorDataPoint] = Field(default_factory=list)
    dxy: list[IndicatorDataPoint] = Field(default_factory=list)
    period_start: str
    period_end: str


class OvernightHistoryResponse(BaseModel):
    """Response model for the overnight-lean instrument history.

    The forward / off-hours risk set: equity-index futures, crude, gold, the 10Y
    note future and Bitcoin — the instruments that keep trading when U.S. cash
    markets are shut.
    """

    stocks_sp: list[IndicatorDataPoint] = Field(default_factory=list)
    stocks_nq: list[IndicatorDataPoint] = Field(default_factory=list)
    oil: list[IndicatorDataPoint] = Field(default_factory=list)
    gold: list[IndicatorDataPoint] = Field(default_factory=list)
    rates: list[IndicatorDataPoint] = Field(default_factory=list)
    crypto: list[IndicatorDataPoint] = Field(default_factory=list)
    period_start: str
    period_end: str


# Sector history endpoint
class SectorDataPoint(BaseModel):
    """Single data point for a sector."""

    date: str
    close: float
    pct_change: float = Field(..., description="% change from period start")


class SectorHistory(BaseModel):
    """History data for a single sector."""

    name: str
    symbol: str
    data: list[SectorDataPoint]
    current_pct: float = Field(..., description="Current % change from period start")


class SectorHistoryResponse(BaseModel):
    """Response model for sector history."""

    sectors: list[SectorHistory]
    period_start: str
    period_end: str


# Market movers endpoint
class MarketMoverItem(BaseModel):
    """Single market mover entry."""

    symbol: str = Field(..., description="Stock symbol")
    name: str | None = Field(None, description="Company name")
    price: float = Field(..., description="Current price")
    change_pct: float = Field(..., description="Percent change")
    volume: int | None = Field(None, description="Trading volume")
    market_cap: int | None = Field(None, description="Market capitalization")
    avg_volume: int | None = Field(None, description="Average daily volume (3 month)")
    rvol: float | None = Field(None, description="Relative volume (volume / avg_volume)")
    sector: str | None = Field(None, description="Sector (e.g., Technology, Healthcare)")


class MarketMoversResponse(BaseModel):
    """Response model for market movers (gainers/losers/volume/rvol)."""

    gainers: list[MarketMoverItem] = Field(..., description="Top gaining stocks")
    losers: list[MarketMoverItem] = Field(..., description="Top losing stocks")
    most_active: list[MarketMoverItem] = Field(
        default_factory=list, description="Most active by volume"
    )
    top_rvol: list[MarketMoverItem] = Field(
        default_factory=list, description="Highest relative volume"
    )
    source: str = Field(..., description="Data source (yahooquery or alpaca)")
    last_updated: str | None = Field(None, description="Last update timestamp")
