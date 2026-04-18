from __future__ import annotations

import importlib
from datetime import UTC, datetime

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.strategy_lab.models import (
    StrategyLabBacktestSnapshot,
    StrategyLabDetailResponse,
    StrategyLabListItem,
    StrategyLabListResponse,
    StrategyLabReviewCapability,
    StrategyLabReviewSuccess,
)
from app.main import app

client = TestClient(app)
strategy_lab_router_module = importlib.import_module("app.api.strategy_lab.router")


def _detail(*, review: StrategyLabReviewCapability | None = None) -> StrategyLabDetailResponse:
    return StrategyLabDetailResponse(
        symbol="VTI",
        action="wait",
        strategy_template="breakout_confirmation",
        primary_account_target=None,
        updated_at=datetime.now(UTC),
        helper_text="Quote is stale. Refresh market data before acting.",
        why_bullets=[
            "Quote is stale.",
            "Refresh market data before acting.",
            "Strategy details are unavailable until fresh pricing returns.",
        ],
        watch_item="Refresh and re-check this symbol during market hours.",
        ticket=None,
        backtest_snapshot=StrategyLabBacktestSnapshot(
            status="quote_unavailable",
            trade_count=0,
            equity_curve=[],
            helper_text="Quote is stale. Refresh market data before acting.",
        ),
        review=review or StrategyLabReviewCapability(available=False, message="Quote is stale"),
    )


def test_strategy_lab_list_route_returns_wrapper(monkeypatch) -> None:
    monkeypatch.setattr(
        strategy_lab_router_module,
        "list_strategy_lab",
        lambda: StrategyLabListResponse(
            items=[
                StrategyLabListItem(
                    symbol="VTI",
                    action="wait",
                    strategy_template="breakout_confirmation",
                    primary_account_target=None,
                    updated_at=datetime.now(UTC),
                    helper_text=None,
                )
            ],
            total_count=1,
        ),
    )

    response = client.get("/api/strategy-lab")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total_count"}
    assert body["total_count"] == 1
    assert body["items"][0]["symbol"] == "VTI"


def test_strategy_lab_detail_route_preserves_http_404(monkeypatch) -> None:
    def _raise(symbol: str):
        raise HTTPException(status_code=404, detail="Strategy Lab symbol not found")

    monkeypatch.setattr(strategy_lab_router_module, "get_strategy_lab_detail", _raise)

    response = client.get("/api/strategy-lab/vti")
    assert response.status_code == 404
    assert response.json() == {"detail": "Strategy Lab symbol not found"}


def test_strategy_lab_review_route_returns_stale_quote_conflict(monkeypatch) -> None:
    monkeypatch.setattr(strategy_lab_router_module, "get_strategy_lab_detail", lambda _symbol: _detail())

    response = client.post("/api/strategy-lab/vti/review")
    assert response.status_code == 409
    assert response.json() == {
        "status": "stale_quote",
        "message": "Quote is stale. Refresh market data before acting.",
    }


def test_strategy_lab_review_route_returns_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        strategy_lab_router_module,
        "get_strategy_lab_detail",
        lambda _symbol: _detail(review=StrategyLabReviewCapability(available=False, message="Review is unavailable right now.")),
    )

    response = client.post("/api/strategy-lab/vti/review")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "message": "Review is unavailable right now.",
    }


def test_strategy_lab_review_route_returns_success_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        strategy_lab_router_module,
        "get_strategy_lab_detail",
        lambda _symbol: _detail(review=StrategyLabReviewCapability(available=True, message=None)),
    )
    monkeypatch.setattr(
        strategy_lab_router_module,
        "run_review",
        lambda _detail: StrategyLabReviewSuccess(
            verdict="Act",
            summary="Summary",
            tailwinds=["Tailwind"],
            headwinds=["Headwind"],
            invalidation_triggers=["Trigger"],
            act_now_or_wait="Act now",
            generated_at=datetime.now(UTC),
        ),
    )

    response = client.post("/api/strategy-lab/vti/review")
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "Act"
    assert body["summary"] == "Summary"
