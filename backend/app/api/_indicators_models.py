"""Pydantic response models for technical indicators API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MACDIndicator(BaseModel):
    """MACD indicator values."""

    macd: float = Field(..., description="MACD line value")
    signal: float = Field(..., description="Signal line value")
    histogram: float = Field(..., description="MACD histogram value")


class BollingerBandsIndicator(BaseModel):
    """Bollinger Bands indicator values."""

    upper: float = Field(..., description="Upper band value")
    middle: float = Field(..., description="Middle band (SMA) value")
    lower: float = Field(..., description="Lower band value")


class StochasticIndicator(BaseModel):
    """Stochastic oscillator indicator values."""

    k: float = Field(..., description="%K line value")
    d: float = Field(..., description="%D line value")


class IndicatorValues(BaseModel):
    """All calculated indicator values."""

    rsi_14: float | None = Field(None, description="14-period RSI")
    macd_12_26_9: MACDIndicator | None = Field(None, description="MACD (12, 26, 9)")
    bbands_20_2: BollingerBandsIndicator | None = Field(
        None, description="Bollinger Bands (20, 2 std dev)"
    )
    sma_20: float | None = Field(None, description="20-period SMA")
    sma_50: float | None = Field(None, description="50-period SMA")
    sma_200: float | None = Field(None, description="200-period SMA")
    ema_20: float | None = Field(None, description="20-period EMA")
    ema_50: float | None = Field(None, description="50-period EMA")
    ema_200: float | None = Field(None, description="200-period EMA")
    atr_14: float | None = Field(None, description="14-period ATR")
    stoch_14_3_3: StochasticIndicator | None = Field(None, description="Stochastic (14, 3, 3)")


class IndicatorInterpretations(BaseModel):
    """Human-readable interpretations of indicator values."""

    rsi: str | None = Field(None, description="RSI interpretation (oversold/neutral/overbought)")
    macd: str | None = Field(
        None, description="MACD interpretation (bullish_cross/bearish_cross/neutral)"
    )
    bbands_position: str | None = Field(
        None, description="Price position relative to Bollinger Bands"
    )
    price_vs_sma_200: str | None = Field(None, description="Price position relative to 200-day SMA")
    stoch: str | None = Field(
        None, description="Stochastic interpretation (oversold/neutral/overbought)"
    )


class IndicatorsResponse(BaseModel):
    """Response model for technical indicators."""

    symbol: str = Field(..., description="Stock symbol")
    date: str = Field(..., description="Date for indicator values (YYYY-MM-DD)")
    close_price: float | None = Field(None, description="Closing price on the date")
    indicators: IndicatorValues = Field(..., description="Calculated indicator values")
    interpretations: IndicatorInterpretations = Field(
        ..., description="Human-readable interpretations"
    )
