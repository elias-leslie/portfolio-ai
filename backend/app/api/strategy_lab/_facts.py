from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal
from functools import lru_cache
from importlib import import_module
from typing import Any

from app.utils.market_hours import NY_TZ, get_last_trading_day
from app.watchlist.watchlist_repository import WatchlistRepository


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _watchlist_repo() -> WatchlistRepository:
    return WatchlistRepository(_storage())


@lru_cache(maxsize=1)
def _price_fetcher():
    return import_module("app.portfolio.price_fetcher").PriceDataFetcher(_storage())


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


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _floor_dollars(value: float | None) -> float:
    if value is None or value <= 0:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_DOWN))
