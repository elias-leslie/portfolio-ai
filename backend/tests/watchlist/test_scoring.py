from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

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


def make_price_data(**overrides: Any) -> PriceData:
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
    assert abs(scores.overall - scores.technical.score) < abs(
        scores.overall - scores.price.score
    )
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


def test_price_change_down_15_percent_retains_differentiation() -> None:
    """Test that a -15% price move doesn't get clamped to 0."""
    now = datetime.now(UTC)
    inputs = WatchlistScoreInputs(
        price=make_price_data(cached_at=now - timedelta(minutes=5)),
        price_change_pct=-15.0,  # Stock down 15%
        technical=TechnicalSnapshot(
            rsi_14=50.0,
            calculated_at=now - timedelta(minutes=10),
        ),
        weights=ScoreWeights(price=100.0, technical=0.0),  # Pure price score
        now=now,
    )

    scores = calculate_watchlist_scores(inputs)

    # With ±20% clamp, -15% should map to ~25 score
    # Formula: (change + 20) / 40 * 100 = (5) / 40 * 100 = 12.5
    # Current ±10% clamp: max(-10, -15) = -10 → (-10 + 10) / 20 * 100 = 0
    expected_score_20pct_clamp = 12.5

    # Test should FAIL with current ±10% clamp (gets 0)
    assert scores.price.score > 0, f"Expected score > 0 for -15% move, got {scores.price.score}"
    assert pytest.approx(scores.price.score, abs=2.0) == expected_score_20pct_clamp


def test_price_change_up_18_percent_retains_differentiation() -> None:
    """Test that a +18% price move doesn't get clamped to 100."""
    now = datetime.now(UTC)
    inputs = WatchlistScoreInputs(
        price=make_price_data(cached_at=now - timedelta(minutes=5)),
        price_change_pct=18.0,  # Stock up 18%
        technical=TechnicalSnapshot(
            rsi_14=50.0,
            calculated_at=now - timedelta(minutes=10),
        ),
        weights=ScoreWeights(price=100.0, technical=0.0),  # Pure price score
        now=now,
    )

    scores = calculate_watchlist_scores(inputs)

    # With ±20% clamp, +18% should map to ~95 score
    # Formula: (change + 20) / 40 * 100 = (38) / 40 * 100 = 95
    # Current ±10% clamp: min(10, 18) = 10 → (10 + 10) / 20 * 100 = 100
    expected_score_20pct_clamp = 95.0

    # Test should FAIL with current ±10% clamp (gets 100)
    assert scores.price.score < 100, f"Expected score < 100 for +18% move, got {scores.price.score}"
    assert pytest.approx(scores.price.score, abs=2.0) == expected_score_20pct_clamp
