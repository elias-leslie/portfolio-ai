from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.strategy_lab.models import (
    StrategyLabBacktestSnapshot,
    StrategyLabPrimaryAccountTarget,
    StrategyLabReviewCapability,
)
from app.api.strategy_lab.service import (
    NO_CASH_MESSAGE,
    STALE_HELPER_TEXT,
    STALE_WATCH_ITEM,
    STALE_WHY_BULLETS,
    _evaluate_symbol,
    _ticket,
)


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
