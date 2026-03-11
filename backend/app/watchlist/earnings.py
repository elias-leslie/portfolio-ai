"""Earnings calendar fetching and warning system (YFinance + Finnhub multi-source)."""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta

import requests

from app.logging_config import get_logger
from app.storage.types import DatabaseConnection

logger = get_logger(__name__)

try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

_CACHE_MISS = object()  # sentinel for "no cache row found"


def _fetch_from_yfinance(symbol: str) -> datetime | None:
    """Fetch earnings date from YFinance."""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        calendar = yf.Ticker(symbol).calendar
        if not calendar or "Earnings Date" not in calendar:
            return None
        earnings_dates = calendar["Earnings Date"]
        if not earnings_dates:
            return None
        earnings_str = earnings_dates[0]
        if isinstance(earnings_str, str):
            return datetime.strptime(earnings_str, "%Y-%m-%d")
        if isinstance(earnings_str, datetime):
            return earnings_str
    except Exception as e:
        logger.debug("yfinance_earnings_fetch_failed", symbol=symbol, error=str(e))
    return None


def _fetch_from_finnhub(symbol: str) -> datetime | None:
    """Fetch earnings date from Finnhub API."""
    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if not finnhub_key:
        return None
    try:
        response = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"symbol": symbol, "token": finnhub_key},
            timeout=10,
        )
        response.raise_for_status()
        entries = response.json().get("earningsCalendar", [])
        if not entries:
            return None
        date_str = entries[0].get("date")
        if date_str:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception as e:
        logger.debug("finnhub_earnings_fetch_failed", symbol=symbol, error=str(e))
    return None


def fetch_earnings_date(symbol: str) -> datetime | None:
    """Fetch next earnings date with multi-source failover (YFinance then Finnhub)."""
    return _fetch_from_yfinance(symbol) or _fetch_from_finnhub(symbol)


def generate_earnings_warning(earnings_date: datetime | None) -> str | None:
    """Generate earnings warning based on proximity (0-5d red, 6-14d caution, 15-30d info)."""
    if earnings_date is None:
        return None
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    normalized = earnings_date.replace(hour=0, minute=0, second=0, microsecond=0)
    days_away = (normalized - now).days
    if days_away < 0 or days_away > 30:
        return None
    if days_away <= 5:
        if days_away == 0:
            return "🔴 EARNINGS TODAY - High volatility expected"
        return f"🔴 EARNINGS IN {days_away} DAYS - High volatility expected"
    if days_away <= 14:
        return f"⚠ Earnings in {days_away} days - approach with caution"
    weeks = days_away // 7
    return f"💡 Earnings in {days_away} days ({weeks} weeks) - plan ahead"


def _read_cache_row(conn: DatabaseConnection, symbol: str, cache_cutoff: date) -> object:
    """Return cached payload dict, None (cached null), or _CACHE_MISS sentinel."""
    row = conn.execute(
        "SELECT payload FROM reference_cache"
        " WHERE symbol = %s AND source = %s AND as_of_date >= %s"
        " ORDER BY as_of_date DESC LIMIT 1",
        [symbol, "earnings", cache_cutoff.isoformat()],
    ).fetchone()
    if row is None:
        return _CACHE_MISS
    payload = row[0]
    return payload if isinstance(payload, dict) else None


def _write_cache_row(
    conn: DatabaseConnection, symbol: str, fresh_data: datetime | None
) -> None:
    """Write earnings date to cache (stores None to avoid repeated failed lookups)."""
    payload_data = {"earnings_date": fresh_data.isoformat() if fresh_data else None}
    conn.execute(
        "INSERT INTO reference_cache (symbol, as_of_date, payload, source)"
        " VALUES (%s, %s, %s, %s)"
        " ON CONFLICT (symbol, as_of_date, source) DO UPDATE SET payload = EXCLUDED.payload",
        [symbol, date.today().isoformat(), json.dumps(payload_data), "earnings"],
    )
    conn.commit()


def fetch_earnings_date_cached(
    conn: DatabaseConnection, symbol: str, ttl_days: int = 30
) -> datetime | None:
    """Fetch earnings date with caching (default TTL: 30 days).

    Checks reference_cache first; fetches and caches fresh data on miss or expiry.
    """
    cache_cutoff = date.today() - timedelta(days=ttl_days)
    cached = _read_cache_row(conn, symbol, cache_cutoff)
    if cached is not _CACHE_MISS:
        if isinstance(cached, dict):
            earnings_date_str = cached.get("earnings_date")
            if earnings_date_str:
                return datetime.fromisoformat(earnings_date_str)
        return None
    fresh_data = fetch_earnings_date(symbol)
    _write_cache_row(conn, symbol, fresh_data)
    return fresh_data
