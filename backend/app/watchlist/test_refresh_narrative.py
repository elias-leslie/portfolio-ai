from __future__ import annotations

import pytest

from app.portfolio.models import PriceData
from app.watchlist.fundamentals import FundamentalData
from app.watchlist.models import TechnicalSnapshot
from app.watchlist.refresh_narrative import build_signal_inputs


def test_build_signal_inputs_preserves_existing_fields_and_adds_fundamentals() -> None:
    inputs = build_signal_inputs(
        price_data=PriceData(symbol="NVDA", price=125.0),
        technical_snapshot=TechnicalSnapshot(
            sma_5=121.0,
            sma_20=118.0,
            sma_50=110.0,
            sma_200=90.0,
            ema_20=119.0,
            rsi_14=68.0,
            macd=1.4,
        ),
        current_volume=10_000_000,
        avg_volume_20d=8_000_000,
        sma_5_prev=120.0,
        company_health_str="GOOD",
        news_sentiment_value=0.35,
        earnings_days_away_val=12,
        fundamentals_data=FundamentalData(
            symbol="NVDA",
            profit_margin=0.53,
            revenue_growth=1.22,
            debt_to_equity=0.45,
            recommendation_mean=1.6,
        ),
    )

    assert inputs["price"] == 125.0
    assert inputs["rsi_14"] == 68.0
    assert inputs["news_sentiment"] == 0.35
    assert inputs["profit_margin"] == 0.53
    assert inputs["revenue_growth"] == 1.22
    assert inputs["debt_to_equity"] == 0.45
    assert inputs["recommendation_mean"] == 1.6
    assert inputs["analyst_buy_pct"] == pytest.approx(0.85)


def test_build_signal_inputs_handles_missing_fundamentals() -> None:
    inputs = build_signal_inputs(
        price_data=PriceData(symbol="MSFT", price=400.0),
        technical_snapshot=TechnicalSnapshot(
            sma_5=None,
            sma_20=None,
            sma_50=None,
            sma_200=None,
            ema_20=None,
            rsi_14=None,
            macd=None,
        ),
        current_volume=None,
        avg_volume_20d=None,
        sma_5_prev=None,
        company_health_str=None,
        news_sentiment_value=None,
        earnings_days_away_val=None,
        fundamentals_data=None,
    )

    assert inputs["price"] == 400.0
    assert inputs["profit_margin"] is None
    assert inputs["revenue_growth"] is None
    assert inputs["debt_to_equity"] is None
    assert inputs["recommendation_mean"] is None
    assert inputs["analyst_buy_pct"] is None
