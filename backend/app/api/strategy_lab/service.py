from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from functools import lru_cache
from importlib import import_module
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.api.portfolio.__init__ import (
    _get_filtered_accounts_and_positions,
)
from app.backtest.replay import InsufficientDataError, replay_backtest
from app.logging_config import get_logger
from app.portfolio.account_types import ACCOUNT_TYPES, is_paper
from app.utils.market_hours import NY_TZ, get_last_trading_day, is_market_hours
from app.watchlist.watchlist_repository import WatchlistRepository

from .models import (
    StrategyLabBacktestPoint,
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
STALE_HELPER_TEXT = "Quote is stale. Refresh market data before acting."
INSUFFICIENT_HISTORY_TEXT = "Not enough daily history to judge this strategy yet."
NO_TRADES_TEXT = "This strategy produced no trades over the test window."
STALE_WHY_BULLETS = [
    "Quote is stale.",
    "Refresh market data before acting.",
    "Strategy details are unavailable until fresh pricing returns.",
]
STALE_WATCH_ITEM = "Refresh and re-check this symbol during market hours."

_ALLOWED_ACCOUNT_TYPES = {value.lower(): value for value in ACCOUNT_TYPES}
_ACCOUNT_PRIORITY = {"Roth": 0, "IRA": 1, "HSA": 2, "Taxable": 3, "401k": 4}


@dataclass(slots=True)
class QuoteInfo:
    price: float | None
    updated_at: datetime | None
    is_fresh: bool
    tracked: bool
    is_held_symbol: bool


@dataclass(slots=True)
class DecisionContext:
    symbol: str
    held: bool
    primary_account_target: StrategyLabPrimaryAccountTarget | None
    action: str
    strategy_template: str
    helper_text: str | None
    quote_price: float | None
    stale: bool
    rolling_30_high: float | None
    sma_50: float | None
    sma_200: float | None


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _watchlist_repo() -> WatchlistRepository:
    return WatchlistRepository(_storage())


@lru_cache(maxsize=1)
def _price_fetcher():
    return import_module("app.portfolio.price_fetcher").PriceDataFetcher(_storage())


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


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _quote_local_date(value: datetime) -> date:
    return value.astimezone(NY_TZ).date()


def _is_fresh_timestamp(value: datetime | None, *, now_utc: datetime) -> bool:
    if value is None:
        return False
    normalized = _normalize_timestamp(value)
    if normalized is None:
        return False
    if is_market_hours(now_utc):
        return (now_utc - normalized) <= timedelta(minutes=30)
    completed_day = get_last_trading_day(now_utc.astimezone(NY_TZ).date())
    return _quote_local_date(normalized) == completed_day


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


def _latest_watchlist_quote(symbol: str, item_id: str, *, now_utc: datetime) -> QuoteInfo:
    df = _watchlist_repo().get_latest_snapshot_for_review(item_id)
    if df.is_empty():
        return QuoteInfo(price=None, updated_at=None, is_fresh=False, tracked=True, is_held_symbol=False)
    row = df.to_dicts()[0]
    fetched_at = row.get("fetched_at")
    updated_at = _normalize_timestamp(fetched_at)
    return QuoteInfo(
        price=float(row.get("price")) if row.get("price") is not None else None,
        updated_at=updated_at,
        is_fresh=_is_fresh_timestamp(updated_at, now_utc=now_utc),
        tracked=True,
        is_held_symbol=False,
    )


def _held_quote(symbol: str, *, now_utc: datetime) -> QuoteInfo:
    price_data = _price_fetcher().fetch_cached_price_data([symbol])
    info = price_data.get(symbol)
    updated_at = _normalize_timestamp(getattr(info, "cached_at", None) if info is not None else None)
    price = float(getattr(info, "price", None)) if info is not None and getattr(info, "price", None) is not None else None
    return QuoteInfo(
        price=price,
        updated_at=updated_at,
        is_fresh=_is_fresh_timestamp(updated_at, now_utc=now_utc),
        tracked=True,
        is_held_symbol=True,
    )


def _resolve_quote(
    symbol: str,
    watchlist_map: dict[str, str],
    positions_by_symbol: dict[str, list[Any]],
    *,
    now_utc: datetime,
) -> QuoteInfo:
    held = symbol in positions_by_symbol and sum(float(getattr(p, "shares", 0.0) or 0.0) for p in positions_by_symbol[symbol]) > 0.01
    if held:
        return _held_quote(symbol, now_utc=now_utc)
    item_id = watchlist_map.get(symbol)
    if item_id is None:
        return QuoteInfo(price=None, updated_at=None, is_fresh=False, tracked=False, is_held_symbol=False)
    return _latest_watchlist_quote(symbol, item_id, now_utc=now_utc)


def _completed_day(now_utc: datetime) -> date:
    return get_last_trading_day(now_utc.astimezone(NY_TZ).date())


def _fetch_day_bars(symbol: str, end_date: date, limit: int = 1500) -> list[dict[str, Any]]:
    df = _storage().query(
        """
        SELECT date, close
        FROM day_bars
        WHERE symbol = ?
          AND date <= ?
        ORDER BY date DESC
        LIMIT ?
        """,
        [symbol, end_date.isoformat(), limit],
    )
    rows = df.to_dicts()
    rows.reverse()
    return rows


def _float_or_none(values: list[float], needed: int) -> float | None:
    if len(values) < needed:
        return None
    return float(sum(values[-needed:]) / needed)


def _rolling_high(values: list[float], needed: int) -> float | None:
    if len(values) < needed:
        return None
    return float(max(values[-needed:]))


def _build_facts(symbol: str, quote_price: float | None, now_utc: datetime) -> tuple[float | None, float | None, float | None, int]:
    rows = _fetch_day_bars(symbol, _completed_day(now_utc), limit=260)
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    return (
        _rolling_high(closes, 30),
        _float_or_none(closes, 50),
        _float_or_none(closes, 200),
        len(closes),
    )


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _floor_dollars(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_DOWN))


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


def _healthy_why_bullets(action: str, held: bool, account: StrategyLabPrimaryAccountTarget | None, pullback: bool, breakout: bool, sma_200: float | None) -> list[str]:
    if pullback:
        price = "Price setup: pullback trigger is active."
    elif breakout and not held:
        price = "Price setup: breakout trigger is active."
    else:
        price = "Price setup: no entry trigger is active."

    if sma_200 is None:
        market = "Market context: unavailable."
    elif pullback:
        market = "Market context: price is still above the 200-day trend."
    elif breakout and not held:
        market = "Market context: price is above the 50-day and 200-day trend filters."
    else:
        market = "Market context: trend filters are not confirming a new entry."

    if account is None:
        account_text = "Account context: unavailable."
    elif held:
        account_text = f"Account context: already held in {account.account_name}."
    elif action in {"buy_now", "buy_in_stages"}:
        account_text = f"Account context: {account.account_name} is the current target account."
    else:
        account_text = "Account context: unavailable."

    return [price, market, account_text]


def _watch_item(action: str, held: bool, pullback: bool, breakout: bool) -> str:
    if pullback and action == "buy_in_stages":
        return "Watch: if the pullback deepens, reassess the next staged buy."
    if breakout and action == "buy_now":
        return "Watch: if the breakout fails, stand aside and reassess."
    if held:
        return "Watch: wait for the pullback trigger to reactivate."
    return "Watch: wait for a qualifying pullback or breakout."


def _stale_template(held: bool) -> str:
    return "pullback_accumulator" if held else "breakout_confirmation"


def _backtest_quote_unavailable() -> StrategyLabBacktestSnapshot:
    return StrategyLabBacktestSnapshot(
        status="quote_unavailable",
        lookback_days=None,
        total_return_pct=None,
        buy_hold_return_pct=None,
        excess_return_pct=None,
        max_drawdown_pct=None,
        trade_count=0,
        equity_curve=[],
        helper_text=STALE_HELPER_TEXT,
    )


def _backtest_insufficient_history(
    *,
    lookback_days: int | None,
    error: InsufficientDataError | None = None,
) -> StrategyLabBacktestSnapshot:
    return StrategyLabBacktestSnapshot(
        status="insufficient_history",
        lookback_days=lookback_days,
        requested_start_date=error.requested_start.isoformat() if error else None,
        requested_end_date=error.requested_end.isoformat() if error else None,
        available_start_date=error.available_start.isoformat() if error and error.available_start else None,
        available_end_date=error.available_end.isoformat() if error and error.available_end else None,
        trade_count=0,
        equity_curve=[],
        helper_text=INSUFFICIENT_HISTORY_TEXT,
    )


def _unavailable_from_snapshot(symbol: str, snapshot: StrategyLabBacktestSnapshot) -> StrategyLabUnavailableItem:
    return StrategyLabUnavailableItem(
        symbol=symbol,
        reason="insufficient_history",
        message=snapshot.helper_text or INSUFFICIENT_HISTORY_TEXT,
        requested_start_date=snapshot.requested_start_date,
        requested_end_date=snapshot.requested_end_date,
        available_start_date=snapshot.available_start_date,
        available_end_date=snapshot.available_end_date,
        lookback_days=snapshot.lookback_days,
    )


def _unavailable_from_error(symbol: str, error: Exception) -> StrategyLabUnavailableItem:
    if isinstance(error, InsufficientDataError):
        return StrategyLabUnavailableItem(
            symbol=symbol,
            reason="insufficient_history",
            message=INSUFFICIENT_HISTORY_TEXT,
            requested_start_date=error.requested_start.isoformat(),
            requested_end_date=error.requested_end.isoformat(),
            available_start_date=error.available_start.isoformat() if error.available_start else None,
            available_end_date=error.available_end.isoformat() if error.available_end else None,
            lookback_days=None,
        )
    return StrategyLabUnavailableItem(
        symbol=symbol,
        reason="evaluation_error",
        message="Strategy Lab could not evaluate this symbol right now.",
    )


def _sample_equity_curve(points: list[Any]) -> list[StrategyLabBacktestPoint]:
    if len(points) <= 200:
        selected = points
    else:
        step = (len(points) - 1) / 199
        indexes = sorted({round(i * step) for i in range(200)})
        selected = [points[i] for i in indexes]
    return [
        StrategyLabBacktestPoint(date=point.date.isoformat(), equity=round(float(point.equity), 2))
        for point in selected
    ]


def _build_signal_dates(symbol: str, template: str, end_date: date) -> tuple[set[date], int]:
    rows = _fetch_day_bars(symbol, end_date, limit=1500)
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    if len(closes) < 252:
        return set(), len(closes)
    signal_dates: set[date] = set()
    for idx, row in enumerate(rows):
        current_price = float(row["close"])
        prefix = closes[: idx + 1]
        rolling_30 = _rolling_high(prefix, 30)
        sma_50 = _float_or_none(prefix, 50)
        sma_200 = _float_or_none(prefix, 200)
        if template == "pullback_accumulator":
            if compute_pullback_signal(current_price, rolling_30, sma_200):
                signal_dates.add(row["date"])
        elif compute_breakout_signal(current_price, rolling_30, sma_50, sma_200):
            signal_dates.add(row["date"])
    return signal_dates, len(closes)


def _buy_hold_return(symbol: str, start_date: date, end_date: date) -> float | None:
    df = _storage().query(
        """
        SELECT date, close
        FROM day_bars
        WHERE symbol = ?
          AND date >= ?
          AND date <= ?
        ORDER BY date ASC
        """,
        [symbol, start_date.isoformat(), end_date.isoformat()],
    )
    if df.is_empty() or len(df) < 2:
        return None
    rows = df.to_dicts()
    start = float(rows[0]["close"])
    end = float(rows[-1]["close"])
    if start <= 0:
        return None
    return round(((end - start) / start) * 100, 2)


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
