"""Unit tests for the home action service."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.jenny import JennyDashboard, JennyNotification, JennyTradeReview
from app.services.home_action_service import HomeActionService


def test_get_action_queue_sorts_and_dedupes_actions() -> None:
    service = object.__new__(HomeActionService)
    service._recommendation_actions = lambda: [
        {
            "id": "rec-1",
            "source": "recommendations",
            "category": "investing",
            "priority": "high",
            "title": "Review NVDA",
            "detail": "Setup ready.",
            "action_label": "Open symbol",
            "href": "/symbols/NVDA",
            "symbol": "NVDA",
            "badge": "High",
        }
    ]
    service._portfolio_health_actions = lambda: []
    service._jenny_actions = lambda: [
        {
            "id": "jenny-1",
            "source": "jenny",
            "category": "investing",
            "priority": "critical",
            "title": "Trim VTI concentration",
            "detail": "Largest position is too large.",
            "action_label": "Review with Jenny",
            "href": "/symbols/VTI",
            "symbol": "VTI",
            "badge": "Critical",
        },
        {
            "id": "dup",
            "source": "jenny",
            "category": "investing",
            "priority": "critical",
            "title": "Review NVDA",
            "detail": "Duplicate title should collapse by href and symbol.",
            "action_label": "Open symbol",
            "href": "/symbols/NVDA",
            "symbol": "NVDA",
            "badge": "Critical",
        },
    ]
    service._workflow_actions = lambda: []
    service._household_actions = lambda: []

    payload = service.get_action_queue()

    assert payload["summary"] == "2 prioritized actions ready."
    assert [action["title"] for action in payload["actions"]] == [
        "Trim VTI concentration",
        "Review NVDA",
    ]


def test_jenny_actions_link_into_decision_context() -> None:
    service = object.__new__(HomeActionService)
    service._jenny_service = lambda: SimpleNamespace(
        get_dashboard=lambda: JennyDashboard(
            notifications=[
                JennyNotification(
                    id="note-1",
                    routine_id="routine-1",
                    symbol="NVDA",
                    category="position_exit",
                    severity="critical",
                    status="open",
                    title="NVDA: Exit this position",
                    detail="The thesis broke.",
                    recommendation="Cut exposure now.",
                    created_at="2026-03-10T16:00:00Z",
                )
            ],
            trade_reviews=[
                JennyTradeReview(
                    id="review-1",
                    symbol="NVDA",
                    review_source="operator",
                    outcome_label="win",
                    lesson="Respect the setup.",
                    created_at="2026-03-09T12:00:00Z",
                    updated_at="2026-03-09T12:00:00Z",
                )
            ],
        )
    )

    actions = service._jenny_actions()

    assert actions[0]["href"] == "/symbols/NVDA?tab=decision"
    assert actions[0]["action_label"] == "Review with Jenny"
    assert actions[0]["decision"]["headline"] == "Exit this position"
    assert actions[0]["decision"]["source_kind"] == "jenny_alert"
    assert actions[1]["href"] == "/symbols/NVDA?tab=decision"


def test_recommendation_actions_use_decision_contract(monkeypatch) -> None:
    service = object.__new__(HomeActionService)
    service.storage = object()

    monkeypatch.setattr(
        "app.services.home_action_service.get_live_portfolio_totals",
        lambda *_args, **_kwargs: SimpleNamespace(cash_inclusive_total_value=250000.0),
    )
    monkeypatch.setattr(
        "app.services.home_action_service.fetch_recommendations",
        lambda **_kwargs: [
            SimpleNamespace(
                symbol="NVDA",
                strategy_id="strat-1",
                signal_type="BUY",
                signal_strength=8,
                position_size_dollars=5000.0,
                validation_type="both",
                generated_at="2026-04-08T15:00:00+00:00",
            )
        ],
    )

    actions = service._recommendation_actions()

    assert actions[0]["href"] == "/symbols/NVDA?tab=decision"
    assert actions[0]["action_label"] == "Open decision"
    assert actions[0]["title"] == "NVDA: Initiate position"
    assert actions[0]["detail"] == "Strong BUY signal (8/10) Suggested size $5,000."
    assert actions[0]["decision"]["source_kind"] == "live_signal_model"


def test_portfolio_health_actions_flag_concentration(monkeypatch) -> None:
    service = object.__new__(HomeActionService)

    def fake_analytics(include_paper: bool = False) -> SimpleNamespace:
        assert include_paper is False
        return SimpleNamespace(
            num_positions=4,
            concentration={
                "top_holding_pct": 38.2,
                "top_3_pct": 74.1,
                "top_10_pct": 100.0,
                "herfindahl_index": 1800.0,
            },
            diversification_score=SimpleNamespace(score=46, level="Fair"),
        )

    monkeypatch.setattr(
        "app.services.home_action_service.get_analytics_payload",
        fake_analytics,
    )

    actions = service._portfolio_health_actions()

    assert actions[0]["title"] == "Portfolio needs a concentration check"
    assert actions[0]["href"] == "/portfolio#portfolio-overview"
    assert actions[0]["badge"] == "Concentration"
    assert "38.2%" in actions[0]["detail"]
