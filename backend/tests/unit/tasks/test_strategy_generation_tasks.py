"""Unit tests for strategy generation helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.tasks.strategy.generation_tasks import (
    _filter_symbols_without_active_strategy,
    _generate_strategies_batch,
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

