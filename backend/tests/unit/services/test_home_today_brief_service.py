"""Unit tests for the home today brief service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.models.market_events import MarketEvent
from app.services.home_today_brief_service import (
    HomeTodayBriefService,
    _upcoming_event_payloads,
)


def test_upcoming_event_payloads_use_market_event_contract() -> None:
    events = [
        MarketEvent(
            id=1,
            event_type="cpi_release",
            event_date="2026-05-12",
            event_time=None,
            title="CPI release",
            description=None,
            expected_value=None,
            actual_value=None,
            prior_value=None,
            surprise_pct=None,
            impact_score=4,
            spy_change_1h=None,
            spy_change_1d=None,
            source="test",
            created_at=None,
        )
    ]

    assert _upcoming_event_payloads(events) == [
        {
            "label": "CPI release",
            "event_type": "cpi_release",
            "event_date": "2026-05-12",
            "importance": "high",
            "impact_score": 4,
        }
    ]


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


def test_market_metrics_use_per_metric_current_timestamps() -> None:
    service = object.__new__(HomeTodayBriefService)
    market = {
        "last_updated": "2026-05-04T19:31:00+00:00",
        "indicators": {
            "sp500": {
                "value": 7201.71,
                "change_pct": -0.39,
                "last_updated": "2026-05-04T19:31:00+00:00",
            },
            "vix": {
                "value": 18.25,
                "change_pct": 7.42,
                "last_updated": "2026-05-04T19:31:05+00:00",
            },
            "tnx": {
                "value": 4.446,
                "change_pct": 1.55,
                "last_updated": "2026-05-04T19:31:10+00:00",
            },
        },
        "fear_greed": {
            "score": 62,
            "score_change": 0.0,
            "label": "Greed",
            "last_updated": "2026-05-01T21:00:00+00:00",
        },
        "sector_rotation": {
            "leading": [
                {
                    "name": "Technology",
                    "change_pct": 1.76,
                    "last_updated": "2026-05-04T19:31:20+00:00",
                }
            ]
        },
    }

    metrics = service._market_metrics(market)

    assert metrics[0]["horizon"] == "Current quote · 1D vs prior close"
    assert metrics[0]["as_of"] == "2026-05-04T19:31:00+00:00"
    assert metrics[0]["as_of_label"] == "As of May 4, 3:31 PM ET"
    assert metrics[3]["key"] == "intraday_mood"
    assert metrics[3]["label"] == "Intraday Mood"
    assert metrics[3]["horizon"] == "Live proxy · Quote inputs"
    assert metrics[3]["as_of"] == "2026-05-04T19:31:00+00:00"
    assert metrics[3]["as_of_label"] == "As of May 4, 3:31 PM ET"
    assert metrics[4]["horizon"] == "Current quotes · 1D sectors"
    assert metrics[4]["as_of_label"] == "As of May 4, 3:31 PM ET"


def test_market_metrics_tolerate_missing_core_indicators() -> None:
    service = object.__new__(HomeTodayBriefService)
    market = {
        "last_updated": "2026-05-04T19:31:00+00:00",
        "indicators": {
            "vix": {
                "value": 18.25,
                "change_pct": 7.42,
                "last_updated": "2026-05-04T19:31:05+00:00",
            }
        },
        "sector_rotation": {"leading": []},
    }

    metrics = service._market_metrics(market)

    assert metrics[0]["key"] == "sp500"
    assert metrics[0]["value"] == "Unavailable"
    assert metrics[0]["tone"] == "neutral"
    assert metrics[2]["key"] == "tnx"
    assert metrics[2]["value"] == "Unavailable"


def test_today_brief_cache_keys_ignore_volatile_timestamps() -> None:
    service = object.__new__(HomeTodayBriefService)
    household = {
        "generated_at": "2026-05-04T19:31:00+00:00",
        "net_worth_status": "current",
        "monthly_spend_status": "current",
        "needs_refresh_count": 1,
        "future_dated_transactions": 0,
        "pace_status": "on_track",
    }
    portfolio = {
        "quotes_updated_at": "2026-05-04T19:31:00+00:00",
        "quote_freshness_status": "fresh",
        "positions": [{"symbol": "VTI"}, {"symbol": "NVDA"}],
        "concentration": {
            "method": "lookthrough",
            "top_holding_name": "Apple",
            "top_holding_pct": 4.04,
            "top_3_pct": 9.96,
        },
    }
    market = {
        "status": "open",
        "last_updated": "2026-05-04T19:31:00+00:00",
        "indicators": {
            "sp500": {"change_pct": 0.24, "last_updated": "2026-05-04T19:31:00+00:00"},
            "vix": {"value": 18.25, "last_updated": "2026-05-04T19:31:00+00:00"},
            "tnx": {"value": 4.446, "last_updated": "2026-05-04T19:31:00+00:00"},
        },
        "fear_greed": {"score": 62, "label": "Greed"},
        "sector_rotation": {"leading": [{"name": "Technology"}]},
    }
    articles = [{"headline": "Rates cool"}]
    events = [{"label": "CPI release"}]

    first = service._research_cache_key(household, portfolio, market, articles, events)

    household["generated_at"] = "2026-05-04T19:32:00+00:00"
    portfolio["quotes_updated_at"] = "2026-05-04T19:32:00+00:00"
    market["last_updated"] = "2026-05-04T19:32:00+00:00"
    market["indicators"]["sp500"]["last_updated"] = "2026-05-04T19:32:00+00:00"
    second = service._research_cache_key(household, portfolio, market, articles, events)

    assert second == first
