from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.api.portfolio.__init__ import (
    _get_filtered_accounts_and_positions,
)
from app.api.recommendations.logic import DEFAULT_POSITION_PCT
from app.api.recommendations.models import TradeRecommendation
from app.api.recommendations.queries import fetch_recommendations
from app.backtest.replay import InsufficientDataError, replay_backtest
from app.logging_config import get_logger
from app.portfolio.account_types import ACCOUNT_TYPES, is_paper
from app.services.household_portfolio_totals import get_effective_portfolio_totals
from app.services.symbol_workflow_service import SymbolWorkflowService

from ._backtest import (
    _backtest_insufficient_history,
    _backtest_quote_unavailable,
    _build_signal_dates,
    _buy_hold_curve,
    _buy_hold_return,
    _sample_equity_curve,
    _unavailable_from_error,
    _unavailable_from_snapshot,
)
from ._facts import (
    _completed_day,
    _floor_dollars,
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
    _stale_template,
)
from .models import (
    StrategyLabBacktestSnapshot,
    StrategyLabDetailResponse,
    StrategyLabDiscoveryItem,
    StrategyLabListItem,
    StrategyLabListResponse,
    StrategyLabPrimaryAccountTarget,
    StrategyLabReviewCapability,
    StrategyLabRiskFrame,
    StrategyLabSignalSnapshot,
    StrategyLabTicket,
    StrategyLabUnavailableItem,
)
from .presets import (
    FIXED_INITIAL_CAPITAL,
    BreakoutConfirmationBacktestStrategy,
    PullbackAccumulatorBacktestStrategy,
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


def _load_recommendations_by_symbol() -> dict[str, TradeRecommendation]:
    """Pull live BUY recommendations once and key by uppercase symbol.

    Strategy Lab is a presentation layer on top of /api/recommendations — we
    never duplicate signal logic, we just pick the strongest qualifying call
    for each tracked symbol.
    """
    try:
        portfolio_size = get_effective_portfolio_totals(
            _storage(),
            include_paper=False,
        ).effective_invested_total_value
    except Exception as exc:
        logger.warning("strategy_lab_portfolio_size_failed", error=str(exc))
        portfolio_size = 0.0
    try:
        recs = fetch_recommendations(
            min_strength=5,
            limit=50,
            signal_type="BUY",
            portfolio_size=max(portfolio_size, 1000.0),
            position_pct=DEFAULT_POSITION_PCT,
            validation_filter=None,
        )
    except Exception as exc:
        logger.warning("strategy_lab_recommendations_failed", error=str(exc))
        return {}
    by_symbol: dict[str, TradeRecommendation] = {}
    for rec in recs:
        key = rec.symbol.upper()
        existing = by_symbol.get(key)
        if existing is None or rec.signal_strength > existing.signal_strength:
            by_symbol[key] = rec
    return by_symbol


def _template_for_strategy(strategy_type: str | None, held: bool) -> str:
    name = (strategy_type or "").lower()
    if any(token in name for token in ("breakout", "momentum", "trend")):
        return "breakout_confirmation"
    if any(token in name for token in ("pullback", "mean_reversion", "reversion")):
        return "pullback_accumulator"
    return "pullback_accumulator" if held else "breakout_confirmation"


def _action_from_recommendation(
    rec: TradeRecommendation | None,
    *,
    held: bool,
    has_cash: bool,
) -> str:
    if held:
        return "hold"
    if rec is None or not has_cash:
        return "wait"
    if rec.signal_status == "valid":
        return "buy_now"
    if rec.signal_status == "better_entry":
        return "buy_in_stages"
    return "wait"


def _signal_snapshot_from_rec(rec: TradeRecommendation) -> StrategyLabSignalSnapshot:
    return StrategyLabSignalSnapshot(
        strategy_id=rec.strategy_id,
        strategy_name=rec.strategy_name,
        strategy_type=rec.strategy_type,
        signal_strength=rec.signal_strength,
        signal_status=rec.signal_status,
        signal_reasons=list(rec.signal_reasons),
        signal_date=rec.signal_date,
        expected_sharpe=rec.expected_sharpe,
        validation_type=rec.validation_type,
        risk=StrategyLabRiskFrame(
            entry_price=rec.entry_price,
            current_price=rec.current_price,
            price_change_pct=rec.price_change_pct,
            stop_loss=rec.stop_loss,
            target_price=rec.target_price,
            risk_reward_ratio=rec.risk_reward_ratio,
        ),
        suggested_size_dollars=rec.position_size_dollars,
        suggested_size_shares=rec.position_size_shares,
    )


def _why_bullets_from_signal(
    action: str,
    held: bool,
    primary: StrategyLabPrimaryAccountTarget | None,
    rec: TradeRecommendation | None,
) -> list[str]:
    if rec is None:
        if held:
            return [
                "Signal: no fresh BUY signal from any active strategy.",
                "Position: held — Strategy Lab is in monitor-only mode here.",
                f"Account: tracked in {primary.account_name}." if primary else "Account: unavailable.",
            ]
        return [
            "Signal: no validated strategy is firing on this symbol right now.",
            "Action: nothing to do — wait for a qualifying signal or a better entry.",
            "Account: ready to deploy when a signal fires." if primary else "Account: no fundable account selected.",
        ]
    bullets = [
        f"Signal: {rec.strategy_name} fired strength {rec.signal_strength}/10 on {rec.signal_date} ({rec.validation_type} validation).",
        f"Edge: expected Sharpe {rec.expected_sharpe:.2f}." if rec.expected_sharpe is not None
        else "Edge: backtest Sharpe unavailable.",
    ]
    if rec.signal_reasons:
        bullets.append("Why now: " + "; ".join(rec.signal_reasons[:2]) + ".")
    if action in {"buy_now", "buy_in_stages"} and primary is not None:
        bullets.append(f"Account: {primary.account_name} is the chosen target ({primary.account_type}).")
    elif held:
        bullets.append(f"Account: already held in {primary.account_name}." if primary else "Account: already held.")
    elif primary is None:
        bullets.append("Account: no fundable account — add cash or another funded account to act.")
    return bullets


def _watch_item_from_signal(action: str, rec: TradeRecommendation | None) -> str:
    if rec is None:
        return "Watch: re-check after the next strategy refresh or on a sharp move."
    if action == "buy_now":
        return f"Watch: stop at ${rec.stop_loss:,.2f}, target ${rec.target_price:,.2f} (R:R {rec.risk_reward_ratio:.2f})."
    if action == "buy_in_stages":
        return f"Watch: better entry zone — first tranche now, top up if it pulls toward ${rec.stop_loss:,.2f}."
    if action == "hold":
        return f"Watch: thesis intact while above stop ${rec.stop_loss:,.2f}; reassess if it breaks."
    return "Watch: wait for a valid signal or a clean better-entry pullback."


def _ticket(
    action: str,
    account: StrategyLabPrimaryAccountTarget | None,
    quote_price: float | None,
    suggested_dollars: float | None = None,
) -> tuple[StrategyLabTicket | None, str | None]:
    """Size the first tranche.

    We respect three things at once: (1) what the recommendations layer says
    the position should be (suggested_dollars), (2) what cash the chosen
    account actually has, (3) whether to deploy in one go or stage it.
    """
    if account is None:
        return None, NO_CASH_MESSAGE
    available = _floor_dollars(account.cash_balance)
    target = (
        min(_floor_dollars(suggested_dollars), available)
        if suggested_dollars and suggested_dollars > 0
        else available
    )
    if action == "buy_now":
        first = target
    elif action == "buy_in_stages":
        first = _floor_dollars(target / 2)
    else:
        return None, None
    if first < 500 or account.cash_balance <= 0 or quote_price is None or quote_price <= 0:
        return None, NO_CASH_MESSAGE
    return (
        StrategyLabTicket(
            account_id=account.account_id,
            account_name=account.account_name,
            action=action,
            dollars=round(target, 2),
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
    sampled_equity = _sample_equity_curve(state.equity_curve)
    target_dates = []
    for point in sampled_equity:
        try:
            target_dates.append(date.fromisoformat(point.date))
        except (TypeError, ValueError):
            continue
    buy_hold_curve = _buy_hold_curve(
        symbol,
        start_date,
        end_date,
        float(FIXED_INITIAL_CAPITAL),
        target_dates=target_dates or None,
    )
    return StrategyLabBacktestSnapshot(
        status="ready",
        lookback_days=lookback_days,
        total_return_pct=total_return,
        buy_hold_return_pct=buy_hold,
        excess_return_pct=round(total_return - buy_hold, 2) if buy_hold is not None else None,
        max_drawdown_pct=max_drawdown,
        trade_count=len(state.trades),
        equity_curve=sampled_equity,
        buy_hold_curve=buy_hold_curve,
        helper_text=None,
    )


def _evaluate_symbol(
    symbol: str,
    *,
    allow_stale_detail: bool,
    now_utc: datetime,
    recommendation: TradeRecommendation | None = None,
) -> StrategyLabDetailResponse | None:
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

    rec = recommendation
    if rec is None and (allow_stale_detail or quote.is_fresh):
        rec = _load_recommendations_by_symbol().get(symbol)
    signal = _signal_snapshot_from_rec(rec) if rec is not None else None

    if not quote.is_fresh:
        if not allow_stale_detail:
            return None
        detail = StrategyLabDetailResponse(
            symbol=symbol,
            action="wait",
            strategy_template=_stale_template(held),
            primary_account_target=primary,
            updated_at=updated_at,
            helper_text=STALE_HELPER_TEXT,
            why_bullets=STALE_WHY_BULLETS,
            watch_item=STALE_WATCH_ITEM,
            ticket=None,
            signal=signal,
            backtest_snapshot=_backtest_quote_unavailable(),
            review=StrategyLabReviewCapability(available=False, message=STALE_QUOTE_MESSAGE),
        )
        return detail

    has_cash = primary is not None and primary.cash_balance > 0
    tentative_action = _action_from_recommendation(rec, held=held, has_cash=has_cash)
    suggested_dollars = rec.position_size_dollars if rec is not None else None
    ticket, ticket_helper = _ticket(tentative_action, primary, quote.price, suggested_dollars)
    if ticket is None and tentative_action in {"buy_now", "buy_in_stages"}:
        action = "hold" if held else "wait"
        helper_text = ticket_helper or NO_CASH_MESSAGE
    else:
        action = tentative_action
        helper_text = None if ticket is not None else (ticket_helper if action in {"hold", "wait"} else None)
        if action in {"hold", "wait"} and primary is None and not held:
            helper_text = NO_CASH_MESSAGE

    strategy_type_for_template = rec.strategy_type if rec is not None else None
    strategy_template = _template_for_strategy(strategy_type_for_template, held)
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
        why_bullets=_why_bullets_from_signal(action, held, primary, rec),
        watch_item=_watch_item_from_signal(action, rec),
        ticket=ticket,
        signal=signal,
        backtest_snapshot=backtest_snapshot,
        review=StrategyLabReviewCapability(available=False, message=REVIEW_UNAVAILABLE_MESSAGE),
    )
    detail.review = get_review_capability(detail)
    return detail


_ACTION_RANK = {"buy_now": 0, "buy_in_stages": 1, "hold": 2, "wait": 3}


def list_strategy_lab() -> StrategyLabListResponse:
    now_utc = datetime.now(UTC)
    accounts = _eligible_accounts()
    positions = _eligible_positions(accounts)
    held_symbols = set(_held_positions_by_symbol(positions).keys())
    tracked_symbols = sorted(set(_watchlist_membership().keys()) | held_symbols)
    recs_by_symbol = _load_recommendations_by_symbol()

    items: list[StrategyLabListItem] = []
    unavailable_items: list[StrategyLabUnavailableItem] = []
    for symbol in tracked_symbols:
        try:
            detail = _evaluate_symbol(
                symbol,
                allow_stale_detail=False,
                now_utc=now_utc,
                recommendation=recs_by_symbol.get(symbol.upper()),
            )
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
                signal=detail.signal,
                backtest_status=detail.backtest_snapshot.status,
                backtest_helper_text=detail.backtest_snapshot.helper_text,
                backtest_lookback_days=detail.backtest_snapshot.lookback_days,
            )
        )

    discoveries: list[StrategyLabDiscoveryItem] = []
    tracked_set = {s.upper() for s in tracked_symbols}
    for sym, rec in recs_by_symbol.items():
        if sym in tracked_set:
            continue
        discoveries.append(
            StrategyLabDiscoveryItem(
                symbol=sym,
                strategy_name=rec.strategy_name,
                strategy_type=rec.strategy_type,
                signal_strength=rec.signal_strength,
                signal_status=rec.signal_status,
                validation_type=rec.validation_type,
                expected_sharpe=rec.expected_sharpe,
                risk=StrategyLabRiskFrame(
                    entry_price=rec.entry_price,
                    current_price=rec.current_price,
                    price_change_pct=rec.price_change_pct,
                    stop_loss=rec.stop_loss,
                    target_price=rec.target_price,
                    risk_reward_ratio=rec.risk_reward_ratio,
                ),
            )
        )
    discoveries.sort(key=lambda d: (-d.signal_strength, d.symbol))
    discoveries = discoveries[:8]

    if discoveries:
        top = discoveries[0]
        top_rec = recs_by_symbol.get(top.symbol)
        try:
            snapshot = _build_backtest_snapshot(
                top.symbol,
                _template_for_strategy(top_rec.strategy_type if top_rec else None, held=False),
                now_utc=now_utc,
            )
            discoveries[0] = top.model_copy(update={"backtest_snapshot": snapshot})
        except Exception as exc:
            logger.warning("strategy_lab_discovery_snapshot_failed", symbol=top.symbol, error=str(exc))

    items.sort(
        key=lambda item: (
            _ACTION_RANK.get(item.action, 9),
            -(item.signal.signal_strength if item.signal else 0),
            0 if item.symbol in held_symbols else 1,
            item.symbol,
        )
    )
    unavailable_items.sort(key=lambda item: item.symbol)
    return StrategyLabListResponse(
        items=items,
        unavailable_items=unavailable_items,
        discoveries=discoveries,
        total_count=len(items),
    )


def get_strategy_lab_detail(symbol: str) -> StrategyLabDetailResponse:
    detail = _evaluate_symbol(symbol, allow_stale_detail=True, now_utc=datetime.now(UTC))
    if detail is None:
        raise HTTPException(status_code=404, detail="Strategy Lab symbol not found")
    return detail


_DECISION_NOTES = {
    "act_now": "Strategy Lab: act on first tranche.",
    "stage": "Strategy Lab: start staged buy.",
    "dismiss": "Strategy Lab: dismiss this call.",
    "snooze": "Strategy Lab: snoozed for one day.",
}

_DECISION_NEXT_STEP = {
    "act_now": "Place the first-tranche order in the chosen account, then mark the symbol live.",
    "stage": "Place tranche 1 now; reassess on the next better-entry trigger or stop touch.",
    "dismiss": "Removed from the queue. Strategy Lab will re-surface on the next valid signal.",
    "snooze": "Hidden until the next refresh cycle.",
}


def record_strategy_lab_decision(symbol: str, action: str, note: str | None) -> dict[str, Any]:
    """Persist a Strategy Lab decision through the existing symbol workflow.

    No new tables — auditable rows land in the same workflow_transitions store
    that already powers Today, Symbol, and Jenny. Snooze is a no-op ack.
    """
    if action not in _DECISION_NOTES:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")
    full_note = note.strip() if note and note.strip() else _DECISION_NOTES[action]
    workflow_stage: str | None = None
    if action in {"act_now", "stage"}:
        try:
            workflow = SymbolWorkflowService().transition(symbol.upper(), "tracked", full_note)
            workflow_stage = str(workflow.get("stage")) if isinstance(workflow, dict) else None
        except Exception as exc:
            logger.warning("strategy_lab_decision_transition_failed", symbol=symbol, error=str(exc))
    return {
        "symbol": symbol.upper(),
        "action": action,
        "recorded_at": datetime.now(UTC),
        "workflow_stage": workflow_stage,
        "notification_id": None,
        "summary": full_note,
        "next_step": _DECISION_NEXT_STEP[action],
    }


__all__ = [
    "INSUFFICIENT_HISTORY_TEXT",
    "NO_CASH_MESSAGE",
    "STALE_HELPER_TEXT",
    "STALE_WATCH_ITEM",
    "STALE_WHY_BULLETS",
    "QuoteInfo",
    "_build_backtest_snapshot",
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
