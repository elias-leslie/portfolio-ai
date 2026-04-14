"""Unit tests for the home action service."""

from __future__ import annotations

from types import SimpleNamespace

from app.api.symbols.models import PositionInfo
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
            "action_label": "Review decision",
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
    assert all("_rank_score" not in action for action in payload["actions"])


def test_get_action_queue_uses_rank_score_before_title_order() -> None:
    service = object.__new__(HomeActionService)
    service._recommendation_actions = lambda: []
    service._portfolio_health_actions = lambda: [
        {
            "id": "portfolio-health-top-holding",
            "source": "portfolio",
            "category": "investing",
            "priority": "high",
            "title": "Portfolio needs a concentration check",
            "detail": "Largest holding is 97.9% of invested assets.",
            "action_label": "Check concentration",
            "href": "/portfolio?tab=holdings&highlight=concentration#portfolio-overview",
            "symbol": None,
            "badge": "Concentration",
            "_rank_score": 2489.5,
        }
    ]
    service._jenny_actions = lambda: [
        {
            "id": "tsla-review",
            "source": "jenny",
            "category": "investing",
            "priority": "warning",
            "title": "TSLA: Recheck this position",
            "detail": "Small position review.",
            "action_label": "Review decision",
            "href": "/symbols/TSLA?tab=decision",
            "symbol": "TSLA",
            "badge": "Warning",
            "_rank_score": 1009.0,
        },
        {
            "id": "vti-trim",
            "source": "jenny",
            "category": "investing",
            "priority": "warning",
            "title": "VTI: Trim this position",
            "detail": "Large concentration review.",
            "action_label": "Review decision",
            "href": "/symbols/VTI?tab=decision",
            "symbol": "VTI",
            "badge": "Warning",
            "_rank_score": 1500.0,
        },
    ]
    service._workflow_actions = lambda: []
    service._household_actions = lambda: [
        {
            "id": "household-accounts",
            "source": "household",
            "category": "household",
            "priority": "high",
            "title": "Are all accounts covered?",
            "detail": "Confirm account coverage.",
            "action_label": "Review accounts",
            "href": "/money?tab=accounts&focus=account-coverage",
            "symbol": None,
            "badge": "Household",
            "_rank_score": 2300.0,
        }
    ]

    payload = service.get_action_queue()

    assert [action["title"] for action in payload["actions"]] == [
        "Portfolio needs a concentration check",
        "Are all accounts covered?",
        "VTI: Trim this position",
        "TSLA: Recheck this position",
    ]
    assert all("_rank_score" not in action for action in payload["actions"])


def test_get_action_queue_prefers_specific_household_follow_up_for_duplicate_titles() -> None:
    service = object.__new__(HomeActionService)
    service._recommendation_actions = lambda: []
    service._portfolio_health_actions = lambda: []
    service._workflow_actions = lambda: []
    service._jenny_actions = lambda: [
        {
            "id": "jenny-amazon-chase",
            "source": "jenny",
            "category": "investing",
            "priority": "warning",
            "title": "Refresh transactions for Amazon Chase (CC)",
            "detail": "Add statements.",
            "action_label": "Review decision",
            "href": "/portfolio",
            "symbol": None,
            "badge": "Warning",
            "execution": {
                "kind": "acknowledge_notification",
                "notification_id": "note-1",
            },
        }
    ]
    service._household_actions = lambda: [
        {
            "id": "household-amazon-chase",
            "source": "household",
            "category": "household",
            "priority": "high",
            "title": "Refresh transactions for Amazon Chase (CC)",
            "detail": "Need a bank or card statement/export covering the latest gap.",
            "action_label": "Add statements",
            "href": "/money?tab=accounts&account=account-1&intent=evidence",
            "symbol": None,
            "badge": "Household",
        }
    ]

    payload = service.get_action_queue()

    assert len(payload["actions"]) == 1
    assert payload["actions"][0]["source"] == "household"
    assert payload["actions"][0]["href"].startswith("/money?")


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
    assert actions[0]["action_label"] == "Review decision"
    assert actions[0]["decision"]["headline"] == "Exit this position"
    assert actions[0]["decision"]["source_kind"] == "jenny_alert"
    assert actions[1]["href"] == "/symbols/NVDA?tab=decision"


def test_jenny_actions_skip_household_notifications_that_already_have_precise_household_routes() -> None:
    service = object.__new__(HomeActionService)
    service._jenny_service = lambda: SimpleNamespace(
        get_dashboard=lambda: JennyDashboard(
            notifications=[
                JennyNotification(
                    id="note-household",
                    routine_id="routine-1",
                    symbol=None,
                    category="household_inbox:account-stale-balance",
                    severity="critical",
                    status="open",
                    title="Refresh Amazon Chase (CC)",
                    detail="Add evidence.",
                    recommendation="Add evidence.",
                    created_at="2026-04-14T16:00:00Z",
                )
            ],
            trade_reviews=[],
        )
    )

    actions = service._jenny_actions()

    assert actions == []


def test_jenny_actions_rank_large_current_positions_above_small(monkeypatch) -> None:
    service = object.__new__(HomeActionService)
    service.storage = object()
    service._jenny_service = lambda: SimpleNamespace(
        get_dashboard=lambda: JennyDashboard(
            notifications=[
                JennyNotification(
                    id="note-vti",
                    routine_id="routine-1",
                    symbol="VTI",
                    category="position_trim",
                    severity="warning",
                    status="open",
                    title="VTI: Trim this position",
                    detail="Trim concentration.",
                    recommendation="Take partial profits.",
                    created_at="2026-03-10T16:00:00Z",
                ),
                JennyNotification(
                    id="note-tsla",
                    routine_id="routine-1",
                    symbol="TSLA",
                    category="position_review",
                    severity="warning",
                    status="open",
                    title="TSLA: Recheck this position",
                    detail="Review thesis.",
                    recommendation="Review the thesis.",
                    created_at="2026-03-10T16:00:00Z",
                ),
            ],
            trade_reviews=[],
        )
    )

    def fake_position(_storage: object, symbol: str | None) -> PositionInfo:
        if symbol == "VTI":
            return PositionInfo(
                shares=10.0,
                cost_basis=100.0,
                current_value=160.0,
                gain=60.0,
                gain_pct=60.0,
                weight_pct=97.0,
            )
        return PositionInfo(
            shares=1.0,
            cost_basis=100.0,
            current_value=94.0,
            gain=-6.0,
            gain_pct=-6.0,
            weight_pct=0.4,
        )

    monkeypatch.setattr(
        "app.services.home_action_service._portfolio_position_for_symbol",
        fake_position,
    )

    actions = service._jenny_actions()
    scores = {action["symbol"]: action["_rank_score"] for action in actions}

    assert scores["VTI"] > scores["TSLA"]


def test_recommendation_actions_use_decision_contract(monkeypatch) -> None:
    service = object.__new__(HomeActionService)
    service.storage = object()

    monkeypatch.setattr(
        "app.services.home_action_service.get_effective_portfolio_totals",
        lambda *_args, **_kwargs: SimpleNamespace(effective_invested_total_value=250000.0),
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
    assert (
        actions[0]["href"]
        == "/portfolio?tab=holdings&highlight=concentration#portfolio-overview"
    )
    assert actions[0]["action_label"] == "Check concentration"
    assert actions[0]["badge"] == "Concentration"
    assert actions[0]["detail"] == (
        "Largest holding is 38.2% of invested assets. "
        "Open Holdings to review portfolio concentration."
    )


def test_household_actions_use_specific_labels_and_focused_destinations() -> None:
    service = object.__new__(HomeActionService)
    service._household_service = lambda: SimpleNamespace(
        get_dashboard=lambda: SimpleNamespace(
            inbox=[
                SimpleNamespace(
                    id="need_account_completeness",
                    category="coverage",
                    title="Are all accounts covered?",
                    detail="Confirm account coverage.",
                    priority="high",
                    action_label="Review accounts",
                    action_href="/money?tab=accounts&focus=account-coverage",
                    related_question_id=None,
                ),
                SimpleNamespace(
                    id="discover-chase-1234",
                    category="account",
                    title="Confirm possible account: Chase · …1234",
                    detail="Imported transfers reference a likely Chase card ending in 1234.",
                    priority="medium",
                    action_label="Review accounts",
                    action_href="/money?tab=accounts&focus=discovered-accounts",
                    related_question_id=None,
                ),
            ]
        )
    )

    actions = service._household_actions()

    assert actions[0]["action_label"] == "Review accounts"
    assert actions[0]["href"] == "/money?tab=accounts&focus=account-coverage"
    assert actions[1]["action_label"] == "Review accounts"
    assert actions[1]["href"] == "/money?tab=accounts&focus=discovered-accounts"
