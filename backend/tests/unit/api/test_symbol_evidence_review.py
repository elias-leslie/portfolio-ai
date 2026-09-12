"""Evidence fidelity for model explanations and historical heuristic snapshots."""

from datetime import UTC, datetime

from app.api.symbols.builders import build_trading_section
from app.api.symbols.decision_evidence import attach_decision_evidence
from app.api.symbols.models import (
    DecisionSection,
    PillarScore,
    PortfolioSection,
    ScoresSection,
    SignalSection,
    SymbolIntelligenceResponse,
    TrendSection,
)
from app.watchlist.trading_style import classify_trading_style


def test_unknown_style_and_historical_precision_are_withheld():
    assert classify_trading_style("AAPL", 5, "HOLD", 50, -2) == {
        "style": None,
        "confidence": None,
        "holding_period": None,
        "risk_level": None,
    }
    historical = build_trading_section(
        {
            "recommended_style": "Value",
            "style_confidence": 6,
            "risk_level": "Medium-Low",
            "optimal_holding_period": "6-12 months",
        }
    )
    assert (
        historical.style
        is historical.confidence
        is historical.holding_period
        is historical.risk_level
        is None
    )
    index = classify_trading_style("QQQ", 5, "HOLD", 50, None)
    assert index["style"] == "Index" and index["risk_level"] is None


def test_watch_explains_actual_inputs_gaps_and_crossing_trigger():
    response = SymbolIntelligenceResponse(
        symbol="AAPL",
        generated_at=datetime.now(UTC),
        portfolio=PortfolioSection(held=False),
        signal=SignalSection(type="HOLD", strength=5),
        scores=ScoresSection(
            overall=56,
            signal_type="HOLD",
            signal_strength=5,
            pillars={
                "technical": PillarScore(
                    score=57,
                    weight=0.22,
                    metadata={
                        "rsi_14": 62.8,
                        "macd": 3.26,
                        "macd_signal": 1.95,
                        "vwap_missing": True,
                    },
                ),
                "catalyst": PillarScore(score=None, weight=0.17),
            },
        ),
        trends=TrendSection(short_term_aligned=False, long_term_aligned=True),
        decision=DecisionSection(
            action="WATCH",
            headline="Watch",
            summary="HOLD signal",
            reasoning=["HOLD signal"],
            source_kind="live_signal_model",
            source_label="Live signal model",
        ),
    )
    attach_decision_evidence(response)
    assert response.decision
    assert any("62.8" in value for value in response.decision.reasoning)
    assert any("VWAP" in value for value in response.decision.missing_evidence)
    assert any("MACD crosses below" in value for value in response.decision.review_triggers)
    assert "potential new position" in (response.decision.portfolio_relevance or "")
    assert response.decision.source_label == "Model evidence"
    response.portfolio = None
    response.decision.source_kind = "jenny_review"
    response.decision.reasoning = ["Actual saved review."]
    attach_decision_evidence(response)
    assert response.decision.reasoning == ["Actual saved review."]
    assert "unknown" in (response.decision.portfolio_relevance or "")
