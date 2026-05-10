from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.utils.market_hours import NY_TZ, get_last_trading_day, is_market_hours

from ._facts import _price_fetcher, _watchlist_repo


@dataclass(slots=True)
class QuoteInfo:
    price: float | None
    updated_at: datetime | None
    is_fresh: bool
    tracked: bool
    is_held_symbol: bool


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
