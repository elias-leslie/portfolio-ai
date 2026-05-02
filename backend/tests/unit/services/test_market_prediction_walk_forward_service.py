"""Unit tests for market prediction walk-forward research."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from app.services.market_prediction_walk_forward_service import (
    MarketPredictionWalkForwardService,
    _candidate_grid,
)


class _FakeRepo:
    def __init__(self, bars: list[tuple[date, float, float]]) -> None:
        self.bars = bars

    def list_day_bars_for_research(self, symbol: str) -> list[tuple[date, float, float]]:
        del symbol
        return self.bars


def _bars(count: int, *, daily_move_pct: float = 0.0) -> list[tuple[date, float, float]]:
    rows: list[tuple[date, float, float]] = []
    close = 100.0
    current = date(2021, 1, 1)
    for _ in range(count):
        open_price = close
        close = close * (1.0 + daily_move_pct / 100.0)
        rows.append((current, open_price, close))
        current += timedelta(days=1)
    return rows


def test_walk_forward_returns_insufficient_when_history_is_short() -> None:
    service = MarketPredictionWalkForwardService(repository=cast(Any, _FakeRepo(_bars(80))))

    scorecard = service.build_scorecard(
        symbol="SPY",
        window_days=3,
        min_sample_count=80,
        max_move_mae_pct=1.25,
    )

    assert scorecard.status == "insufficient"
    assert scorecard.passed is False
    assert scorecard.status_reason == "Not enough historical bars for walk-forward test."


def test_walk_forward_tests_candidate_grid_and_fails_fast_when_no_edge() -> None:
    service = MarketPredictionWalkForwardService(repository=cast(Any, _FakeRepo(_bars(900))))

    scorecard = service.build_scorecard(
        symbol="SPY",
        window_days=3,
        min_sample_count=80,
        max_move_mae_pct=1.25,
    )

    assert scorecard.status in {"fail", "insufficient"}
    assert scorecard.passed is False
    assert scorecard.tested_candidates > 300
    assert scorecard.status_reason
    assert scorecard.top_candidates


def test_walk_forward_grid_tests_relative_driver_moves() -> None:
    candidates = _candidate_grid("SPY")

    assert any(candidate.feature_kind == "relative_to_target" for candidate in candidates)
    assert any("/SPY" in candidate.label for candidate in candidates)


def test_walk_forward_is_deterministic_on_fixed_history() -> None:
    service = MarketPredictionWalkForwardService(repository=cast(Any, _FakeRepo(_bars(900))))

    first = service.build_scorecard(
        symbol="SPY",
        window_days=3,
        min_sample_count=80,
        max_move_mae_pct=1.25,
    )
    second = service.build_scorecard(
        symbol="SPY",
        window_days=3,
        min_sample_count=80,
        max_move_mae_pct=1.25,
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
