"""Known net-worth trend from current holdings and latest household evidence."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl

from app.models.household_finance import (
    HouseholdNetWorthTrend,
    HouseholdNetWorthTrendPoint,
)

_METHODOLOGY = (
    "Current shares are repriced with cached recent quotes (live during market "
    "hours, latest close after). Cash, liabilities, and non-symbol accounts use "
    "latest available household balances."
)


def _finite_float(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _date_key(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


def _fetch_closes(storage: Any, symbols: list[str], *, days: int) -> dict[str, dict[str, float]]:
    if not symbols:
        return {}
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    frame = storage.query(
        """
        SELECT symbol, date, close
        FROM day_bars
        WHERE symbol = ANY(?::text[])
          AND date >= ?
        ORDER BY date, symbol
        """,
        [symbols, cutoff],
    )
    if not isinstance(frame, pl.DataFrame) or frame.is_empty():
        return {}

    closes: dict[str, dict[str, float]] = {}
    for row in frame.iter_rows(named=True):
        date_key = _date_key(row["date"])
        symbol = str(row["symbol"]).upper()
        close = _finite_float(row["close"])
        if close <= 0:
            continue
        closes.setdefault(date_key, {})[symbol] = close
    return closes


def _position_shares_by_symbol(positions: list[Any]) -> dict[str, float]:
    shares_by_symbol: dict[str, float] = {}
    for position in positions:
        shares = _finite_float(getattr(position, "shares", 0.0))
        if shares == 0:
            continue
        symbol = str(getattr(position, "symbol", "")).upper()
        if not symbol:
            continue
        sign = -1.0 if str(getattr(position, "position_type", "long")) == "short" else 1.0
        shares_by_symbol[symbol] = shares_by_symbol.get(symbol, 0.0) + (shares * sign)
    return shares_by_symbol


def _current_priced_holdings_value(service: Any, shares_by_symbol: dict[str, float]) -> tuple[float, str | None]:
    if not shares_by_symbol:
        return 0.0, None
    # cache + on-miss vendor fetch with smart TTL (2/5/30 min based on market state).
    # The household holdings cron keeps the cache hot during market hours so this
    # is normally a cache hit; on-miss covers cold loads and never-touched symbols.
    price_data = service.price_fetcher.fetch_price_data(sorted(shares_by_symbol))
    total = 0.0
    quote_dates: list[str] = []
    for symbol, shares in shares_by_symbol.items():
        price = price_data.get(symbol)
        if price is None or getattr(price, "error", None):
            continue
        total += shares * _finite_float(getattr(price, "price", 0.0))
        cached_at = getattr(price, "cached_at", None)
        if cached_at is not None:
            quote_dates.append(_date_key(cached_at))
    return total, max(quote_dates, default=None)


def _gap_detail(
    *,
    missing_balance_account_count: int,
    stale_account_count: int,
    needs_refresh_count: int,
    net_worth_detail: str,
) -> str:
    parts: list[str] = []
    if missing_balance_account_count:
        parts.append(f"{missing_balance_account_count} missing balance")
    if stale_account_count:
        parts.append(f"{stale_account_count} stale balance")
    if needs_refresh_count:
        parts.append(f"{needs_refresh_count} need refresh")
    if not parts:
        return net_worth_detail
    return f"{net_worth_detail} Gaps: {', '.join(parts)}."


def build_net_worth_trend(service: Any, *, days: int = 180) -> HouseholdNetWorthTrend:
    dashboard = service.get_dashboard()
    overview = dashboard.overview
    portfolio_accounts = [
        account
        for account in service.portfolio_mgr.get_accounts()
        if getattr(account, "account_type", None) != "paper"
    ]
    account_ids = {str(account.id) for account in portfolio_accounts}
    positions = [
        position
        for position in service.portfolio_mgr.get_positions()
        if str(getattr(position, "account_id", "")) in account_ids
    ]
    shares_by_symbol = _position_shares_by_symbol(positions)
    symbols = sorted(shares_by_symbol)
    current_priced_value, quote_as_of_date = _current_priced_holdings_value(service, shares_by_symbol)
    total_assets = _finite_float(getattr(overview, "total_tracked_assets", 0.0))
    liabilities = _finite_float(getattr(overview, "liabilities_total", 0.0))
    net_worth = _finite_float(getattr(overview, "net_worth", total_assets - liabilities))
    fixed_assets = total_assets - current_priced_value

    points: list[HouseholdNetWorthTrendPoint] = []
    closes_by_date = _fetch_closes(service.storage, symbols, days=days)
    for date_key in sorted(closes_by_date):
        closes = closes_by_date[date_key]
        if any(symbol not in closes for symbol in symbols):
            continue
        priced_value = sum(shares_by_symbol[symbol] * closes[symbol] for symbol in symbols)
        assets = fixed_assets + priced_value
        points.append(
            HouseholdNetWorthTrendPoint(
                date=date_key,
                net_worth=round(assets - liabilities, 2),
                total_assets=round(assets, 2),
                liabilities=round(liabilities, 2),
                priced_holdings_value=round(priced_value, 2),
                fixed_assets=round(fixed_assets, 2),
            )
        )

    current_date = quote_as_of_date or _date_key(getattr(dashboard, "generated_at", datetime.now(UTC)))
    current_point = HouseholdNetWorthTrendPoint(
        date=current_date,
        net_worth=round(net_worth, 2),
        total_assets=round(total_assets, 2),
        liabilities=round(liabilities, 2),
        priced_holdings_value=round(current_priced_value, 2),
        fixed_assets=round(fixed_assets, 2),
    )
    points = [point for point in points if point.date != current_point.date]
    points.append(current_point)

    accounts = list(getattr(dashboard, "accounts", []) or [])
    missing_balance_account_count = sum(
        1
        for account in accounts
        if getattr(account, "current_value", None) is None
        or getattr(account, "balance_freshness_status", None) == "needs_evidence"
    )
    stale_account_count = sum(
        1
        for account in accounts
        if getattr(account, "balance_freshness_status", None) == "stale"
    )
    needs_refresh_count = int(getattr(overview, "needs_refresh_count", 0) or 0)
    net_worth_detail = str(getattr(overview, "net_worth_detail", "") or "")
    detail = _gap_detail(
        missing_balance_account_count=missing_balance_account_count,
        stale_account_count=stale_account_count,
        needs_refresh_count=needs_refresh_count,
        net_worth_detail=net_worth_detail,
    )

    return HouseholdNetWorthTrend(
        generated_at=datetime.now(UTC).isoformat(),
        as_of_date=current_date,
        status=str(getattr(overview, "net_worth_status", "unavailable")),
        detail=detail,
        methodology=_METHODOLOGY,
        points=points,
        holdings_symbol_count=len(symbols),
        holdings_position_count=len(positions),
        gap_count=int(getattr(overview, "gap_count", 0) or 0),
        needs_refresh_count=needs_refresh_count,
        missing_balance_account_count=missing_balance_account_count,
        stale_account_count=stale_account_count,
    )
