from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.portfolio.models import PriceData
from app.watchlist.models import (
    ScoreBreakdown,
    ScoreWeights,
    TechnicalSnapshot,
    WatchlistScoreInputs,
)
from app.watchlist.scoring import (
    PRICE_STALE_TTL_MINUTES,
    TECHNICAL_STALE_TTL_MINUTES,
    calculate_watchlist_scores,
)


def make_price_data(**overrides) -> PriceData:
    defaults = {
        "symbol": "AAPL",
        "price": 182.45,
        "beta": 1.05,
        "volatility": 0.28,
        "sector": "Technology",
        "cached_at": datetime.now(UTC),
        "source": "yfinance",
        "error": None,
    }
    return PriceData(**{**defaults, **overrides})


def test_calculate_scores_happy_path() -> None:
    now = datetime.now(UTC)
    inputs = WatchlistScoreInputs(
        price=make_price_data(cached_at=now - timedelta(minutes=5)),
        price_change_pct=2.5,
        technical=TechnicalSnapshot(
            rsi_14=55.0,
            sma_50=175.0,
            sma_200=170.0,
            price=182.45,
            macd=1.1,
            macd_signal=0.9,
            calculated_at=now - timedelta(minutes=10),
        ),
        weights=ScoreWeights(price=40.0, technical=60.0),
        now=now,
    )

    scores = calculate_watchlist_scores(inputs)

    assert isinstance(scores, ScoreBreakdown)
    assert 0 <= scores.price.score <= 100
    assert 0 <= scores.technical.score <= 100
    assert 0 <= scores.overall <= 100
    # Heavier technical weight should pull overall closer to technical score
    assert scores.overall >= scores.price.score
    assert not scores.price.stale
    assert not scores.technical.stale


def test_missing_change_pct_marks_price_stale() -> None:
    now = datetime.now(UTC)
    inputs = WatchlistScoreInputs(
        price=make_price_data(cached_at=now - timedelta(minutes=PRICE_STALE_TTL_MINUTES + 5)),
        price_change_pct=None,
        technical=TechnicalSnapshot(
            rsi_14=48.0,
            calculated_at=now - timedelta(minutes=10),
        ),
        weights=ScoreWeights(price=50.0, technical=50.0),
        now=now,
    )

    scores = calculate_watchlist_scores(inputs)
    assert scores.price.stale
    assert scores.price.score == 0.0


def test_missing_technical_indicators() -> None:
    now = datetime.now(UTC)
    inputs = WatchlistScoreInputs(
        price=make_price_data(cached_at=now - timedelta(minutes=5)),
        price_change_pct=0.0,
        technical=TechnicalSnapshot(
            calculated_at=None,
        ),
        weights=ScoreWeights(price=70.0, technical=30.0),
        now=now,
    )

    scores = calculate_watchlist_scores(inputs)
    assert scores.technical.stale
    assert scores.technical.score == 0.0
    # Overall should rely on price component due to technical 0 score
    assert pytest.approx(scores.overall, rel=1e-3) == scores.price.score * 0.7


def test_stale_technical_component_flagged() -> None:
    now = datetime.now(UTC)
    inputs = WatchlistScoreInputs(
        price=make_price_data(),
        price_change_pct=1.0,
        technical=TechnicalSnapshot(
            rsi_14=52.0,
            calculated_at=now - timedelta(minutes=TECHNICAL_STALE_TTL_MINUTES + 1),
        ),
        now=now,
    )

    scores = calculate_watchlist_scores(inputs)
    assert scores.technical.stale
