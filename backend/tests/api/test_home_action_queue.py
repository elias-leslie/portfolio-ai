"""API tests for the home dashboard endpoints."""

from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.home import HomeActionQueueResponse, HomeTodayBriefResponse
from app.main import app


def test_home_action_queue_returns_actions(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "app.api.home._home_action_service",
        lambda: Mock(
            get_action_queue=Mock(
                return_value=HomeActionQueueResponse(
                    generated_at="2026-03-10T00:00:00Z",
                    actions=[
                        {
                            "id": "action-1",
                            "source": "recommendations",
                            "category": "investing",
                            "priority": "high",
                            "title": "Review NVDA setup",
                            "detail": "Signal strength 8/10 with both thesis and strategy support.",
                            "action_label": "Open symbol",
                            "href": "/symbols/NVDA",
                            "symbol": "NVDA",
                            "badge": "High",
                        }
                    ],
                    summary="1 prioritized action ready.",
                )
            )
        ),
    )

    response = client.get("/api/home/action-queue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "1 prioritized action ready."
    assert payload["actions"][0]["href"] == "/symbols/NVDA"
    assert payload["actions"][0]["category"] == "investing"


def test_home_today_brief_returns_market_pulse(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "app.api.home._home_today_brief_service",
        lambda: Mock(
            get_today_brief=Mock(
                return_value=HomeTodayBriefResponse(
                    generated_at="2026-03-10T00:00:00Z",
                    cache_ttl_seconds=300,
                    as_of={
                        "household": "2026-03-10T00:00:00Z",
                        "portfolio": "2026-03-10T00:00:00Z",
                        "market": "2026-03-10T00:00:00Z",
                        "news": "2026-03-10T00:00:00Z",
                    },
                    market_status="open",
                    brief={
                        "headline": "Markets steady as yields cool",
                        "summary": "Rates eased and breadth improved.",
                        "stance": "constructive",
                        "confidence": "medium",
                        "why_now": "Macro pressure relaxed.",
                        "bullets": [],
                    },
                    catalysts=[
                        {
                            "id": "catalyst-1",
                            "title": "Treasury yields eased",
                            "direction": "positive",
                            "market_effect": "Broad equities bid higher.",
                            "portfolio_effect": "Supports VTI-heavy exposure.",
                            "money_effect": "Reduces immediate financing pressure.",
                            "source_ids": ["official_treasury"],
                        }
                    ],
                    impacts=[
                        {
                            "label": "Broad equity exposure gets a tailwind",
                            "direction": "tailwind",
                            "magnitude": "medium",
                            "rationale": "Lower yields help duration-sensitive equities.",
                            "affected_symbols": ["VTI"],
                            "source_ids": ["official_treasury"],
                        }
                    ],
                    market_metrics=[
                        {
                            "key": "sp500",
                            "label": "S&P 500",
                            "value": "7,022.95",
                            "change_pct": 0.4,
                            "detail": "Broad market benchmark",
                            "tone": "positive",
                        }
                    ],
                    sources=[
                        {
                            "id": "official_treasury",
                            "kind": "market_data",
                            "label": "U.S. Treasury yield curve",
                            "published_at": None,
                            "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/textview",
                            "source_signal_tier": "primary",
                            "decision_value_score": 0.9,
                        }
                    ],
                    staleness_notes=[],
                ).model_dump(mode="json")
            )
        ),
    )

    response = client.get("/api/home/today-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market_status"] == "open"
    assert payload["brief"]["headline"] == "Markets steady as yields cool"
    assert payload["catalysts"][0]["source_ids"] == ["official_treasury"]
