"""Unit tests for strategy generation helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.tasks.strategy.generation_tasks import (
    _filter_symbols_without_active_strategy,
    _generate_strategies_batch,
    daily_strategy_refresh,
    trigger_strategies_for_top_watchlist,
    trigger_strategy_from_seed,
    weekly_strategy_generation,
)


def test_filter_symbols_without_active_strategy_excludes_existing_symbols() -> None:
    storage = MagicMock()
    storage.get_active_strategy.side_effect = lambda symbol: {"id": symbol} if symbol == "AAPL" else None

    filtered = _filter_symbols_without_active_strategy(["AAPL", "MSFT", "NVDA"], storage)

    assert filtered == ["MSFT", "NVDA"]


def test_generate_strategies_batch_stops_after_max_completed(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(symbol: str, force_regenerate: bool = False) -> tuple[str, dict[str, str] | None]:
        calls.append(symbol)
        return (f"Generated {symbol}", {"status": "completed"})

    monkeypatch.setattr(
        "app.tasks.strategy.generation_tasks._run_strategy_workflow",
        fake_run,
    )

    result = _generate_strategies_batch(["AAPL", "MSFT", "NVDA"], max_count=2)

    assert result["generated_count"] == 2
    assert result["results"] == ["Generated AAPL", "Generated MSFT"]
    assert calls == ["AAPL", "MSFT"]


def test_daily_strategy_refresh_skips_when_background_strategy_research_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.strategy.generation_tasks.get_automation_preferences",
        lambda: {"scheduled_strategy_research_enabled": {"enabled": False}},
    )

    result = daily_strategy_refresh()

    assert result == {
        "status": "skipped",
        "details": ["scheduled_strategy_research_disabled"],
    }


def test_weekly_strategy_generation_skips_when_background_strategy_research_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.strategy.generation_tasks.get_automation_preferences",
        lambda: {"scheduled_strategy_research_enabled": {"enabled": False}},
    )

    result = weekly_strategy_generation()

    assert result == {
        "status": "skipped",
        "details": ["scheduled_strategy_research_disabled"],
    }


def test_trigger_strategies_for_top_watchlist_skips_when_background_strategy_research_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.strategy.generation_tasks.get_automation_preferences",
        lambda: {"scheduled_strategy_research_enabled": {"enabled": False}},
    )

    result = trigger_strategies_for_top_watchlist()

    assert result == {"status": "skipped", "reason": "scheduled_strategy_research_disabled"}


def test_trigger_strategy_from_seed_skips_when_background_strategy_research_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.strategy.generation_tasks.get_automation_preferences",
        lambda: {"scheduled_strategy_research_enabled": {"enabled": False}},
    )

    result = trigger_strategy_from_seed("seed-1", "AAPL")

    assert result == {
        "status": "skipped",
        "seed_id": "seed-1",
        "symbol": "AAPL",
        "reason": "scheduled_strategy_research_disabled",
    }
