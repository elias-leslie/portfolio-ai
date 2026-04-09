"""Unit tests for watchlist decision enrichment."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.jenny import JennyAgentEvaluation, JennyNotification, JennySymbolReview
from app.watchlist._service import item_enrichment


def test_build_watchlist_decision_map_prefers_jenny_alert(monkeypatch) -> None:
    monkeypatch.setattr(
        item_enrichment,
        "_build_portfolio_context",
        lambda _storage, _symbols: ({}, None),
    )
    monkeypatch.setattr(
        item_enrichment,
        "get_market_data",
        lambda _storage: {"fear_greed": {"score": 55}},
    )
    monkeypatch.setattr(
        item_enrichment,
        "_get_jenny_dashboard",
        lambda: SimpleNamespace(
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
                    recommendation="Reduce risk now.",
                    created_at="2026-04-08T14:00:00+00:00",
                )
            ],
            symbol_reviews=[],
            trade_reviews=[],
        ),
    )

    decisions = item_enrichment.build_watchlist_decision_map(
        storage=object(),
        items=[
            {
                "symbol": "NVDA",
                "signal_type": "BUY",
                "signal_strength": 8,
                "updated_at": "2026-04-08T15:00:00+00:00",
            }
        ],
    )

    assert decisions["NVDA"]["headline"] == "Exit this position"
    assert decisions["NVDA"]["source_kind"] == "jenny_alert"
    assert decisions["NVDA"]["severity"] == "critical"


def test_build_watchlist_decision_map_falls_back_to_live_signal_model(monkeypatch) -> None:
    monkeypatch.setattr(
        item_enrichment,
        "_build_portfolio_context",
        lambda _storage, _symbols: ({}, None),
    )
    monkeypatch.setattr(
        item_enrichment,
        "get_market_data",
        lambda _storage: {"fear_greed": {"score": 28}},
    )
    monkeypatch.setattr(
        item_enrichment,
        "_get_jenny_dashboard",
        lambda: SimpleNamespace(
            notifications=[],
            symbol_reviews=[],
            trade_reviews=[],
        ),
    )

    decisions = item_enrichment.build_watchlist_decision_map(
        storage=object(),
        items=[
            {
                "symbol": "NVDA",
                "signal_type": "BUY",
                "signal_strength": 8,
                "updated_at": "2026-04-08T15:00:00+00:00",
            }
        ],
    )

    assert decisions["NVDA"]["action"] == "INITIATE_POSITION"
    assert decisions["NVDA"]["headline"] == "Initiate position"
    assert decisions["NVDA"]["source_kind"] == "live_signal_model"
    assert decisions["NVDA"]["reasoning"] == [
        "Strong BUY signal (8/10)",
        "Market in Fear (28) - consider smaller positions",
    ]


def test_build_watchlist_decision_map_uses_recent_jenny_review_before_live_model(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        item_enrichment,
        "_build_portfolio_context",
        lambda _storage, _symbols: ({}, None),
    )
    monkeypatch.setattr(
        item_enrichment,
        "get_market_data",
        lambda _storage: {"fear_greed": {"score": 55}},
    )
    monkeypatch.setattr(
        item_enrichment,
        "_get_jenny_dashboard",
        lambda: SimpleNamespace(
            notifications=[],
            symbol_reviews=[
                JennySymbolReview(
                    symbol="NVDA",
                    final_verdict="review",
                    management_action="trim",
                    management_detail="Position is oversized after the run.",
                    reasons=["Risk has outrun upside."],
                    evaluations=[
                        JennyAgentEvaluation(
                            id="eval-1",
                            routine_id="routine-1",
                            symbol="NVDA",
                            agent_name="risk-manager",
                            verdict="review",
                            confidence=0.7,
                            rationale="Position is stretched.",
                            created_at="2026-04-08T13:30:00+00:00",
                        )
                    ],
                )
            ],
            trade_reviews=[],
        ),
    )

    decisions = item_enrichment.build_watchlist_decision_map(
        storage=object(),
        items=[
            {
                "symbol": "NVDA",
                "signal_type": "BUY",
                "signal_strength": 8,
                "updated_at": "2026-04-08T15:00:00+00:00",
            }
        ],
    )

    assert decisions["NVDA"]["headline"] == "Trim"
    assert decisions["NVDA"]["source_kind"] == "jenny_review"
