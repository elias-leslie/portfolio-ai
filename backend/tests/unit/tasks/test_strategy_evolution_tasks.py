"""Unit tests for strategy evolution task guardrails."""

from __future__ import annotations

from app.tasks.strategy.evolution_tasks import weekly_strategy_evolution


def test_weekly_strategy_evolution_skips_when_background_strategy_research_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.tasks.strategy.evolution_tasks.get_automation_preferences",
        lambda: {"scheduled_strategy_research_enabled": {"enabled": False}},
    )

    result = weekly_strategy_evolution()

    assert result == {"status": "skipped", "reason": "scheduled_strategy_research_disabled"}
