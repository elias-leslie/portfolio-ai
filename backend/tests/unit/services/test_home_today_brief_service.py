"""Unit tests for the home today brief service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.services.home_today_brief_service import HomeTodayBriefService


def test_agent_payload_uses_dedicated_market_pulse_agent(monkeypatch) -> None:
    client = Mock()
    client.complete_messages.return_value = SimpleNamespace(content="not-json")
    client_cls = Mock(return_value=client)
    monkeypatch.setattr(
        "app.services.home_today_brief_service.AgentHubAPIClient",
        client_cls,
    )

    fallback = {
        "brief": {
            "headline": "Fallback",
            "summary": "Fallback summary",
            "stance": "neutral",
            "confidence": "low",
            "why_now": "Fallback why now",
            "bullets": ["Fallback bullet"],
        },
        "catalysts": [
            {
                "id": "catalyst_1",
                "title": "Fallback catalyst",
                "direction": "mixed",
                "market_effect": "Fallback market effect",
                "portfolio_effect": "Fallback portfolio effect",
                "money_effect": "Fallback money effect",
                "source_ids": [],
            }
        ],
        "impacts": [
            {
                "label": "Fallback impact",
                "direction": "mixed",
                "magnitude": "low",
                "rationale": "Fallback rationale",
                "affected_symbols": [],
                "source_ids": [],
            }
        ],
    }

    service = object.__new__(HomeTodayBriefService)
    result = service._agent_payload(
        context={"run_timestamp": "2026-04-16T00:00:00+00:00"},
        fallback=fallback,
        source_ids=set(),
    )

    assert result == fallback
    client_cls.assert_called_once_with(
        agent_slug="market-pulse-analyst",
    )
    assert "model" not in client_cls.call_args.kwargs
    call = client.complete_messages.call_args
    assert call is not None
    assert call.kwargs["execute_tools"] is True
    assert call.kwargs["enable_programmatic_tools"] is True
    assert "system_prompt" not in call.kwargs
