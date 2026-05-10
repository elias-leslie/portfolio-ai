from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.api.portfolio.__init__ import (
    _get_filtered_accounts_and_positions,
)
from app.backtest.replay import InsufficientDataError, replay_backtest
from app.logging_config import get_logger
from app.portfolio.account_types import ACCOUNT_TYPES, is_paper

from ._backtest import (
    _backtest_insufficient_history,
    _backtest_quote_unavailable,
    _build_signal_dates,
    _buy_hold_return,
    _sample_equity_curve,
    _unavailable_from_error,
    _unavailable_from_snapshot,
)
from ._facts import (
    _completed_day,
    _fetch_day_bars,
    _float_or_none,
    _floor_dollars,
    _rolling_high,
    _round_money,
    _storage,
    _watchlist_repo,
)
from ._quotes import QuoteInfo, _resolve_quote
from ._text import (
    INSUFFICIENT_HISTORY_TEXT,
    NO_TRADES_TEXT,
    STALE_HELPER_TEXT,
    STALE_WATCH_ITEM,
    STALE_WHY_BULLETS,
    _healthy_why_bullets,
    _stale_template,
    _watch_item,
)
from .models import (
    StrategyLabBacktestSnapshot,
    StrategyLabDetailResponse,
    StrategyLabListItem,
    StrategyLabListResponse,
    StrategyLabPrimaryAccountTarget,
    StrategyLabReviewCapability,
    StrategyLabTicket,
    StrategyLabUnavailableItem,
)
from .presets import (
    FIXED_INITIAL_CAPITAL,
    BreakoutConfirmationBacktestStrategy,
    PullbackAccumulatorBacktestStrategy,
    compute_breakout_signal,
    compute_pullback_signal,
)
from .review import REVIEW_UNAVAILABLE_MESSAGE, STALE_QUOTE_MESSAGE, get_review_capability

logger = get_logger(__name__)

NO_CASH_MESSAGE = "Not enough cash for a first buy right now."

_ALLOWED_ACCOUNT_TYPES = {value.lower(): value for value in ACCOUNT_TYPES}
_ACCOUNT_PRIORITY = {"Roth": 0, "IRA": 1, "HSA": 2, "Taxable": 3, "401k": 4}


def _normalize_account_type(raw: Any) -> str | None:
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    return _ALLOWED_ACCOUNT_TYPES.get(normalized)


def _eligible_accounts() -> list[Any]:
    accounts, _, _ = _get_filtered_accounts_and_positions(include_paper=True)
    result = []
    for account in accounts:
        account_type = _normalize_account_type(getattr(account, "account_type", None))
        if account_type and not is_paper(account_type):
            result.append(account)
    return result


def _eligible_positions(accounts: list[Any]) -> list[Any]:
    account_ids = {str(acc.id) for acc in accounts}
    _, _, positions = _get_filtered_accounts_and_positions(include_paper=True)
    result = []
    for position in positions:
        if str(position.account_id) not in account_ids:
            continue
        if str(getattr(position, "position_type", "long")).lower() != "long":
            continue
        if float(getattr(position, "shares", 0.0) or 0.0) <= 0:
            continue
        result.append(position)
    return result


def _watchlist_membership() -> dict[str, str]:
    df = _watchlist_repo().get_all_symbols()
    if df.is_empty():
        return {}
    return {str(row["symbol"]).upper(): str(row["id"]) for row in df.to_dicts()}


def _held_positions_by_symbol(positions: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for position in positions:
        symbol = str(position.symbol).upper()
        grouped.setdefault(symbol, []).append(position)
    return grouped


def _select_primary_account_target(
    symbol: str,
    held: bool,
    accounts: list[Any],
    positions_by_symbol: dict[str, list[Any]],
    quote_price: float | None,
) -> StrategyLabPrimaryAccountTarget | None:
    if held:
        candidates = []
        for position in positions_by_symbol.get(symbol, []):
            account = next((acc for acc in accounts if str(acc.id) == str(position.account_id)), None)
            if account is None:
                continue
            held_market_value = None if quote_price is None else round(float(position.shares) * quote_price, 2)
            candidates.append(
                (
                    -(held_market_value or 0.0),
                    _ACCOUNT_PRIORITY.get(_normalize_account_type(account.account_type) or "", 99),
                    str(account.name).lower(),
                    StrategyLabPrimaryAccountTarget(
                        account_id=str(account.id),
                        account_name=str(account.name),
                        account_type=str(_normalize_account_type(account.account_type) or account.account_type),
                        cash_balance=round(float(getattr(account, "cash_balance", 0.0) or 0.0), 2),
                        held_market_value=held_market_value,
                    ),
                )
            )
        if candidates:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return candidates[0][3]
    candidates = []
    for account in accounts:
        cash = round(float(getattr(account, "cash_balance", 0.0) or 0.0), 2)
        if cash <= 0:
            continue
        candidates.append(
            (
                -cash,
                _ACCOUNT_PRIORITY.get(_normalize_account_type(account.account_type) or "", 99),
                str(account.name).lower(),
                StrategyLabPrimaryAccountTarget(
                    account_id=str(account.id),
                    account_name=str(account.name),
                    account_type=str(_normalize_account_type(account.account_type) or account.account_type),
                    cash_balance=cash,
                    held_market_value=None,
                ),
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][3]


def _build_facts(symbol: str, quote_price: float | None, now_utc: datetime) -> tuple[float | None, float | None, float | None, int]:
    rows = _fetch_day_bars(symbol, _completed_day(now_utc), limit=260)
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    return (
        _rolling_high(closes, 30),
        _float_or_none(closes, 50),
        _float_or_none(closes, 200),
        len(closes),
    )


def _ticket(
    action: str,
    account: StrategyLabPrimaryAccountTarget | None,
    quote_price: float | None,
) -> tuple[StrategyLabTicket | None, str | None]:
    if account is None:
        return None, NO_CASH_MESSAGE
    dollars = _floor_dollars(account.cash_balance)
    if action == "buy_now":
        first = dollars
    elif action == "buy_in_stages":
        first = _floor_dollars(dollars / 2)
    else:
        return None, None
    if first < 500 or account.cash_balance <= 0 or quote_price is None or quote_price <= 0:
        return None, NO_CASH_MESSAGE
    return (
        StrategyLabTicket(
            account_id=account.account_id,
            account_name=account.account_name,
            action=action,
            dollars=round(dollars, 2),
            estimated_shares=round(first / quote_price, 2),
            first_tranche_dollars=round(first, 2),
            helper_text=None,
        ),
        None,
    )


def _build_backtest_snapshot(symbol: str, template: str, *, now_utc: datetime) -> StrategyLabBacktestSnapshot:
    end_date = _completed_day(now_utc)
    signal_dates, lookback_days = _build_signal_dates(symbol, template, end_date)
    if lookback_days < 252:
        return _backtest_insufficient_history(lookback_days=lookback_days)
    if not signal_dates:
        return StrategyLabBacktestSnapshot(
            status="no_trades",
            lookback_days=lookback_days,
            trade_count=0,
            equity_curve=[],
            helper_text=NO_TRADES_TEXT,
        )
    start_date = max(min(signal_dates), end_date - timedelta(days=365 * 5))
    strategy = (
        PullbackAccumulatorBacktestStrategy(signal_dates)
        if template == "pullback_accumulator"
        else BreakoutConfirmationBacktestStrategy(signal_dates)
    )
    try:
        state = replay_backtest(
            storage=_storage(),
            run_id=f"strategy-lab-{uuid4()}",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=FIXED_INITIAL_CAPITAL,
            strategy=strategy,
            sizing_method="fixed_dollars",
            size_value=FIXED_INITIAL_CAPITAL,
        )
    except InsufficientDataError as exc:
        logger.info(
            "strategy_lab_insufficient_history",
            symbol=symbol,
            requested_start=str(exc.requested_start),
            requested_end=str(exc.requested_end),
            available_start=str(exc.available_start) if exc.available_start else None,
            available_end=str(exc.available_end) if exc.available_end else None,
        )
        return _backtest_insufficient_history(lookback_days=lookback_days, error=exc)
    if not state.trades:
        return StrategyLabBacktestSnapshot(
            status="no_trades",
            lookback_days=lookback_days,
            trade_count=0,
            equity_curve=[],
            helper_text=NO_TRADES_TEXT,
        )
    final_equity = float(state.equity_curve[-1].equity)
    total_return = round(((final_equity - float(FIXED_INITIAL_CAPITAL)) / float(FIXED_INITIAL_CAPITAL)) * 100, 2)
    buy_hold = _buy_hold_return(symbol, start_date, end_date)
    max_drawdown = round(max(float(point.drawdown_pct) for point in state.equity_curve), 2) if state.equity_curve else 0.0
    return StrategyLabBacktestSnapshot(
        status="ready",
        lookback_days=lookback_days,
        total_return_pct=total_return,
        buy_hold_return_pct=buy_hold,
        excess_return_pct=round(total_return - buy_hold, 2) if buy_hold is not None else None,
        max_drawdown_pct=max_drawdown,
        trade_count=len(state.trades),
        equity_curve=_sample_equity_curve(state.equity_curve),
        helper_text=None,
    )


def _evaluate_symbol(symbol: str, *, allow_stale_detail: bool, now_utc: datetime) -> StrategyLabDetailResponse | None:
    symbol = symbol.upper()
    accounts = _eligible_accounts()
    positions = _eligible_positions(accounts)
    positions_by_symbol = _held_positions_by_symbol(positions)
    watchlist_map = _watchlist_membership()
    quote = _resolve_quote(symbol, watchlist_map, positions_by_symbol, now_utc=now_utc)
    if not quote.tracked:
        return None
    held = symbol in positions_by_symbol and sum(float(getattr(p, 'shares', 0.0) or 0.0) for p in positions_by_symbol[symbol]) > 0.01
    primary = _select_primary_account_target(symbol, held, accounts, positions_by_symbol, quote.price)
    updated_at = now_utc
    if not quote.is_fresh:
        if not allow_stale_detail:
            return None
        helper = STALE_HELPER_TEXT
        detail = StrategyLabDetailResponse(
            symbol=symbol,
            action="wait",
            strategy_template=_stale_template(held),
            primary_account_target=primary,
            updated_at=updated_at,
            helper_text=helper,
            why_bullets=STALE_WHY_BULLETS,
            watch_item=STALE_WATCH_ITEM,
            ticket=None,
            backtest_snapshot=_backtest_quote_unavailable(),
            review=StrategyLabReviewCapability(available=False, message=STALE_QUOTE_MESSAGE),
        )
        return detail

    rolling_30_high, sma_50, sma_200, _lookback_days = _build_facts(symbol, quote.price, now_utc)
    pullback = quote.price is not None and compute_pullback_signal(quote.price, rolling_30_high, sma_200)
    breakout = quote.price is not None and compute_breakout_signal(quote.price, rolling_30_high, sma_50, sma_200)

    if pullback:
        strategy_template = "pullback_accumulator"
        tentative_action = "buy_in_stages"
    elif (not held) and breakout:
        strategy_template = "breakout_confirmation"
        tentative_action = "buy_now"
    else:
        strategy_template = "pullback_accumulator" if held else "breakout_confirmation"
        tentative_action = "hold" if held else "wait"

    ticket, ticket_helper = _ticket(tentative_action, primary, quote.price)
    if ticket is None and tentative_action in {"buy_now", "buy_in_stages"}:
        action = "hold" if held else "wait"
        helper_text = ticket_helper or NO_CASH_MESSAGE
    else:
        action = tentative_action
        helper_text = None if ticket is not None else (ticket_helper if action in {"hold", "wait"} else None)
        if action in {"hold", "wait"} and primary is None and not held:
            helper_text = NO_CASH_MESSAGE

    backtest_snapshot = _build_backtest_snapshot(symbol, strategy_template, now_utc=now_utc)
    detail_helper_text = helper_text
    if backtest_snapshot.status == "insufficient_history" and detail_helper_text is None:
        detail_helper_text = backtest_snapshot.helper_text

    detail = StrategyLabDetailResponse(
        symbol=symbol,
        action=action,
        strategy_template=strategy_template,
        primary_account_target=primary,
        updated_at=updated_at,
        helper_text=detail_helper_text,
        why_bullets=_healthy_why_bullets(action, held, primary, pullback, breakout, sma_200),
        watch_item=_watch_item(action, held, pullback, breakout),
        ticket=ticket,
        backtest_snapshot=backtest_snapshot,
        review=StrategyLabReviewCapability(available=False, message=REVIEW_UNAVAILABLE_MESSAGE),
    )
    detail.review = get_review_capability(detail)
    return detail


def list_strategy_lab() -> StrategyLabListResponse:
    now_utc = datetime.now(UTC)
    accounts = _eligible_accounts()
    positions = _eligible_positions(accounts)
    held_symbols = set(_held_positions_by_symbol(positions).keys())
    tracked_symbols = sorted(set(_watchlist_membership().keys()) | held_symbols)
    items: list[StrategyLabListItem] = []
    unavailable_items: list[StrategyLabUnavailableItem] = []
    for symbol in tracked_symbols:
        try:
            detail = _evaluate_symbol(symbol, allow_stale_detail=False, now_utc=now_utc)
        except Exception as exc:
            logger.warning("strategy_lab_symbol_unavailable", symbol=symbol, error=str(exc))
            unavailable_items.append(_unavailable_from_error(symbol, exc))
            continue
        if detail is None:
            continue
        if detail.backtest_snapshot.status == "insufficient_history":
            unavailable_items.append(_unavailable_from_snapshot(detail.symbol, detail.backtest_snapshot))
        items.append(
            StrategyLabListItem(
                symbol=detail.symbol,
                action=detail.action,
                strategy_template=detail.strategy_template,
                primary_account_target=detail.primary_account_target,
                updated_at=detail.updated_at,
                helper_text=detail.helper_text,
                backtest_status=detail.backtest_snapshot.status,
                backtest_helper_text=detail.backtest_snapshot.helper_text,
                backtest_lookback_days=detail.backtest_snapshot.lookback_days,
            )
        )
    items.sort(key=lambda item: (0 if item.symbol in held_symbols else 1, item.symbol))
    unavailable_items.sort(key=lambda item: item.symbol)
    return StrategyLabListResponse(items=items, unavailable_items=unavailable_items, total_count=len(items))


def get_strategy_lab_detail(symbol: str) -> StrategyLabDetailResponse:
    detail = _evaluate_symbol(symbol, allow_stale_detail=True, now_utc=datetime.now(UTC))
    if detail is None:
        raise HTTPException(status_code=404, detail="Strategy Lab symbol not found")
    return detail


__all__ = [
    "INSUFFICIENT_HISTORY_TEXT",
    "NO_CASH_MESSAGE",
    "STALE_HELPER_TEXT",
    "STALE_WATCH_ITEM",
    "STALE_WHY_BULLETS",
    "QuoteInfo",
    "_build_backtest_snapshot",
    "_build_facts",
    "_eligible_accounts",
    "_eligible_positions",
    "_evaluate_symbol",
    "_held_positions_by_symbol",
    "_normalize_account_type",
    "_resolve_quote",
    "_round_money",
    "_select_primary_account_target",
    "_ticket",
    "_watchlist_membership",
    "get_strategy_lab_detail",
    "list_strategy_lab",
]
