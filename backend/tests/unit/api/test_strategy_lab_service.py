from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.api.strategy_lab.models import (
    StrategyLabBacktestSnapshot,
    StrategyLabDetailResponse,
    StrategyLabPrimaryAccountTarget,
    StrategyLabReviewCapability,
)
from app.api.strategy_lab.service import (
    NO_CASH_MESSAGE,
    STALE_HELPER_TEXT,
    STALE_WATCH_ITEM,
    STALE_WHY_BULLETS,
    _build_backtest_snapshot,
    _evaluate_symbol,
    _ticket,
    list_strategy_lab,
)
from app.backtest.replay import InsufficientDataError


class DummyTarget(StrategyLabPrimaryAccountTarget):
    pass


def test_ticket_returns_expected_first_tranche() -> None:
    ticket, helper = _ticket(
        "buy_in_stages",
        DummyTarget(
            account_id="acct-1",
            account_name="Roth",
            account_type="Roth",
            cash_balance=1000.99,
            held_market_value=None,
        ),
        50.0,
    )
    assert helper is None
    assert ticket is not None
    assert ticket.dollars == 1000.0
    assert ticket.first_tranche_dollars == 500.0
    assert ticket.estimated_shares == 10.0


def test_ticket_returns_no_cash_helper_below_threshold() -> None:
    ticket, helper = _ticket(
        "buy_in_stages",
        DummyTarget(
            account_id="acct-1",
            account_name="Roth",
            account_type="Roth",
            cash_balance=999.99,
            held_market_value=None,
        ),
        50.0,
    )
    assert ticket is None
    assert helper == NO_CASH_MESSAGE


def test_evaluate_symbol_returns_none_for_untracked(monkeypatch) -> None:
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_accounts", lambda: [])
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_positions", lambda _accounts: [])
    monkeypatch.setattr("app.api.strategy_lab.service._watchlist_membership", lambda: {})
    detail = _evaluate_symbol("vti", allow_stale_detail=True, now_utc=datetime.now(UTC))
    assert detail is None


def test_evaluate_symbol_returns_stale_detail_for_tracked_symbol(monkeypatch) -> None:
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_accounts", lambda: [])
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_positions", lambda _accounts: [])
    monkeypatch.setattr("app.api.strategy_lab.service._watchlist_membership", lambda: {"VTI": "item-1"})
    def _resolve_quote_stub(symbol, watchlist_map, positions_by_symbol, now_utc):
        _ = (symbol, watchlist_map, positions_by_symbol, now_utc)
        return SimpleNamespace(price=None, updated_at=None, is_fresh=False, tracked=True, is_held_symbol=False)

    monkeypatch.setattr(
        "app.api.strategy_lab.service._resolve_quote",
        _resolve_quote_stub,
    )
    monkeypatch.setattr("app.api.strategy_lab.service._select_primary_account_target", lambda *_args, **_kwargs: None)

    detail = _evaluate_symbol("vti", allow_stale_detail=True, now_utc=datetime.now(UTC))
    assert detail is not None
    assert detail.action == "wait"
    assert detail.helper_text == STALE_HELPER_TEXT
    assert detail.why_bullets == STALE_WHY_BULLETS
    assert detail.watch_item == STALE_WATCH_ITEM
    assert detail.backtest_snapshot.status == "quote_unavailable"
    assert detail.review == StrategyLabReviewCapability(available=False, message="Quote is stale")


def test_evaluate_symbol_held_pullback_with_no_cash_falls_back_to_hold(monkeypatch) -> None:
    account = SimpleNamespace(id="acct-1", name="Roth", account_type="Roth", cash_balance=100.0)
    position = SimpleNamespace(account_id="acct-1", symbol="VTI", shares=10.0)
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_accounts", lambda: [account])
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_positions", lambda _accounts: [position])
    monkeypatch.setattr("app.api.strategy_lab.service._watchlist_membership", lambda: {"VTI": "item-1"})
    def _resolve_quote_stub(symbol, watchlist_map, positions_by_symbol, now_utc):
        _ = (symbol, watchlist_map, positions_by_symbol, now_utc)
        return SimpleNamespace(price=100.0, updated_at=datetime.now(UTC), is_fresh=True, tracked=True, is_held_symbol=True)

    monkeypatch.setattr(
        "app.api.strategy_lab.service._resolve_quote",
        _resolve_quote_stub,
    )
    monkeypatch.setattr(
        "app.api.strategy_lab.service._select_primary_account_target",
        lambda *_args, **_kwargs: StrategyLabPrimaryAccountTarget(
            account_id="acct-1",
            account_name="Roth",
            account_type="Roth",
            cash_balance=100.0,
            held_market_value=1000.0,
        ),
    )
    monkeypatch.setattr("app.api.strategy_lab.service._build_facts", lambda *_args, **_kwargs: (120.0, 110.0, 90.0, 260))
    monkeypatch.setattr(
        "app.api.strategy_lab.service._build_backtest_snapshot",
        lambda *_args, **_kwargs: StrategyLabBacktestSnapshot(status="ready", lookback_days=260, trade_count=1, equity_curve=[], helper_text=None),
    )
    monkeypatch.setattr(
        "app.api.strategy_lab.service.get_review_capability",
        lambda _detail: StrategyLabReviewCapability(available=False, message="Review is unavailable right now."),
    )

    detail = _evaluate_symbol("vti", allow_stale_detail=True, now_utc=datetime.now(UTC))
    assert detail is not None
    assert detail.action == "hold"
    assert detail.helper_text == NO_CASH_MESSAGE
    assert detail.ticket is None


def test_evaluate_symbol_unheld_pullback_with_cash_uses_buy_in_stages(monkeypatch) -> None:
    account = SimpleNamespace(id="acct-1", name="Roth", account_type="Roth", cash_balance=1000.0)
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_accounts", lambda: [account])
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_positions", lambda _accounts: [])
    monkeypatch.setattr("app.api.strategy_lab.service._watchlist_membership", lambda: {"VTI": "item-1"})
    def _resolve_quote_stub(symbol, watchlist_map, positions_by_symbol, now_utc):
        _ = (symbol, watchlist_map, positions_by_symbol, now_utc)
        return SimpleNamespace(price=100.0, updated_at=datetime.now(UTC), is_fresh=True, tracked=True, is_held_symbol=False)

    monkeypatch.setattr(
        "app.api.strategy_lab.service._resolve_quote",
        _resolve_quote_stub,
    )
    monkeypatch.setattr(
        "app.api.strategy_lab.service._select_primary_account_target",
        lambda *_args, **_kwargs: StrategyLabPrimaryAccountTarget(
            account_id="acct-1",
            account_name="Roth",
            account_type="Roth",
            cash_balance=1000.0,
            held_market_value=None,
        ),
    )
    monkeypatch.setattr("app.api.strategy_lab.service._build_facts", lambda *_args, **_kwargs: (120.0, 110.0, 90.0, 260))
    monkeypatch.setattr(
        "app.api.strategy_lab.service._build_backtest_snapshot",
        lambda *_args, **_kwargs: StrategyLabBacktestSnapshot(status="ready", lookback_days=260, trade_count=1, equity_curve=[], helper_text=None),
    )
    monkeypatch.setattr(
        "app.api.strategy_lab.service.get_review_capability",
        lambda _detail: StrategyLabReviewCapability(available=False, message="Review is unavailable right now."),
    )

    detail = _evaluate_symbol("vti", allow_stale_detail=True, now_utc=datetime.now(UTC))
    assert detail is not None
    assert detail.action == "buy_in_stages"
    assert detail.ticket is not None
    assert detail.ticket.first_tranche_dollars == 500.0


def test_build_backtest_snapshot_returns_insufficient_history_when_replay_lacks_lookback(monkeypatch) -> None:
    requested_start = date(2021, 4, 23)
    requested_end = date(2026, 4, 23)
    available_start = date(2022, 3, 1)
    available_end = date(2026, 4, 23)

    monkeypatch.setattr(
        "app.api.strategy_lab.service._build_signal_dates",
        lambda *_args, **_kwargs: ({requested_start}, 260),
    )

    def _raise_insufficient(*_args, **_kwargs):
        raise InsufficientDataError(
            "AMZN",
            requested_start,
            requested_end,
            available_start,
            available_end,
        )

    monkeypatch.setattr("app.api.strategy_lab.service.replay_backtest", _raise_insufficient)

    snapshot = _build_backtest_snapshot(
        "AMZN",
        "breakout_confirmation",
        now_utc=datetime(2026, 4, 24, tzinfo=UTC),
    )

    assert snapshot.status == "insufficient_history"
    assert snapshot.lookback_days == 260
    assert snapshot.requested_start_date == requested_start.isoformat()
    assert snapshot.requested_end_date == requested_end.isoformat()
    assert snapshot.available_start_date == available_start.isoformat()
    assert snapshot.available_end_date == available_end.isoformat()
    assert snapshot.helper_text == "Not enough daily history to judge this strategy yet."


def test_list_strategy_lab_returns_partial_results_for_insufficient_history(monkeypatch) -> None:
    ready_detail = StrategyLabDetailResponse(
        symbol="VTI",
        action="wait",
        strategy_template="breakout_confirmation",
        primary_account_target=None,
        updated_at=datetime(2026, 4, 24, tzinfo=UTC),
        helper_text=None,
        why_bullets=[],
        watch_item="Watch VTI.",
        ticket=None,
        backtest_snapshot=StrategyLabBacktestSnapshot(
            status="ready",
            lookback_days=300,
            trade_count=1,
            equity_curve=[],
            helper_text=None,
        ),
        review=StrategyLabReviewCapability(available=False, message="Review unavailable"),
    )
    insufficient_detail = StrategyLabDetailResponse(
        symbol="AMZN",
        action="wait",
        strategy_template="breakout_confirmation",
        primary_account_target=None,
        updated_at=datetime(2026, 4, 24, tzinfo=UTC),
        helper_text="Not enough daily history to judge this strategy yet.",
        why_bullets=[],
        watch_item="Watch AMZN.",
        ticket=None,
        backtest_snapshot=StrategyLabBacktestSnapshot(
            status="insufficient_history",
            lookback_days=180,
            requested_start_date="2021-04-23",
            requested_end_date="2026-04-23",
            available_start_date="2024-01-02",
            available_end_date="2026-04-23",
            trade_count=0,
            equity_curve=[],
            helper_text="Not enough daily history to judge this strategy yet.",
        ),
        review=StrategyLabReviewCapability(available=False, message="Review unavailable"),
    )

    monkeypatch.setattr("app.api.strategy_lab.service._eligible_accounts", lambda: [])
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_positions", lambda _accounts: [])
    monkeypatch.setattr("app.api.strategy_lab.service._held_positions_by_symbol", lambda _positions: {})
    monkeypatch.setattr("app.api.strategy_lab.service._watchlist_membership", lambda: {"AMZN": "item-1", "VTI": "item-2"})
    monkeypatch.setattr(
        "app.api.strategy_lab.service._evaluate_symbol",
        lambda symbol, **_kwargs: insufficient_detail if symbol == "AMZN" else ready_detail,
    )

    response = list_strategy_lab()

    assert [item.symbol for item in response.items] == ["AMZN", "VTI"]
    assert response.items[0].backtest_status == "insufficient_history"
    assert response.unavailable_items[0].symbol == "AMZN"
    assert response.unavailable_items[0].requested_start_date == "2021-04-23"


def test_list_strategy_lab_keeps_other_symbols_when_one_evaluation_raises(monkeypatch) -> None:
    ready_detail = StrategyLabDetailResponse(
        symbol="VTI",
        action="wait",
        strategy_template="breakout_confirmation",
        primary_account_target=None,
        updated_at=datetime(2026, 4, 24, tzinfo=UTC),
        helper_text=None,
        why_bullets=[],
        watch_item="Watch VTI.",
        ticket=None,
        backtest_snapshot=StrategyLabBacktestSnapshot(
            status="ready",
            lookback_days=300,
            trade_count=1,
            equity_curve=[],
            helper_text=None,
        ),
        review=StrategyLabReviewCapability(available=False, message="Review unavailable"),
    )

    def _evaluate(symbol: str, **_kwargs):
        if symbol == "AMZN":
            raise RuntimeError("boom")
        return ready_detail

    monkeypatch.setattr("app.api.strategy_lab.service._eligible_accounts", lambda: [])
    monkeypatch.setattr("app.api.strategy_lab.service._eligible_positions", lambda _accounts: [])
    monkeypatch.setattr("app.api.strategy_lab.service._held_positions_by_symbol", lambda _positions: {})
    monkeypatch.setattr("app.api.strategy_lab.service._watchlist_membership", lambda: {"AMZN": "item-1", "VTI": "item-2"})
    monkeypatch.setattr("app.api.strategy_lab.service._evaluate_symbol", _evaluate)

    response = list_strategy_lab()

    assert [item.symbol for item in response.items] == ["VTI"]
    assert response.unavailable_items[0].symbol == "AMZN"
    assert response.unavailable_items[0].reason == "evaluation_error"
