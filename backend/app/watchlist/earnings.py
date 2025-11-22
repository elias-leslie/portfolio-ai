"""Earnings calendar fetching and warning system.

This module fetches upcoming earnings dates from multiple sources (YFinance, Finnhub)
and generates warnings based on proximity to earnings events.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import requests

from app.storage.types import DatabaseConnection

if TYPE_CHECKING:
    pass

try:
    import yfinance as yf  # type: ignore[import-untyped]

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False


def fetch_earnings_date(symbol: str) -> datetime | None:
    """Fetch next earnings date with multi-source failover.

    Sources (in priority order):
    1. YFinance (free)
    2. Finnhub (if API key available)

    Args:
        symbol: Stock ticker symbol

    Returns:
        datetime object for next earnings date, or None if not found
    """
    # Try YFinance first
    if YFINANCE_AVAILABLE:
        try:
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar

            if calendar and "Earnings Date" in calendar:
                earnings_dates = calendar["Earnings Date"]
                if earnings_dates and len(earnings_dates) > 0:
                    # YFinance returns date as string or datetime
                    earnings_str = earnings_dates[0]
                    if isinstance(earnings_str, str):
                        # Parse string date (format: YYYY-MM-DD)
                        return datetime.strptime(earnings_str, "%Y-%m-%d")
                    if isinstance(earnings_str, datetime):
                        return earnings_str
        except Exception:
            pass  # Try next source

    # Try Finnhub if API key available
    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if finnhub_key:
        try:
            url = "https://finnhub.io/api/v1/calendar/earnings"
            params = {
                "symbol": symbol,
                "token": finnhub_key,
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            earnings_calendar = data.get("earningsCalendar", [])

            if earnings_calendar and len(earnings_calendar) > 0:
                # Take first (most recent) earnings date
                date_str = earnings_calendar[0].get("date")
                if date_str:
                    return datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            pass  # All sources failed

    return None


def generate_earnings_warning(earnings_date: datetime | None) -> str | None:  # noqa: PLR0911
    """Generate earnings warning based on proximity.

    Warning levels:
    - 🔴 (0-5 days): High volatility expected
    - ⚠ (6-14 days): Caution - earnings approaching
    - 💡 (15-30 days): FYI - earnings in 2-4 weeks
    - None (>30 days or past): No warning

    Args:
        earnings_date: Next earnings date

    Returns:
        Warning string or None if no warning needed
    """
    if earnings_date is None:
        return None

    # Calculate days away (compare dates only, not datetime to avoid time precision issues)
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    earnings_date_normalized = earnings_date.replace(hour=0, minute=0, second=0, microsecond=0)
    days_away = (earnings_date_normalized - now).days

    # No warning for past earnings
    if days_away < 0:
        return None

    # No warning for earnings >30 days away
    if days_away > 30:
        return None

    # Generate appropriate warning
    if days_away <= 5:
        if days_away == 0:
            return "🔴 EARNINGS TODAY - High volatility expected"
        return f"🔴 EARNINGS IN {days_away} DAYS - High volatility expected"
    if days_away <= 14:
        return f"⚠ Earnings in {days_away} days - approach with caution"
    # 15-30 days
    weeks = days_away // 7
    return f"💡 Earnings in {days_away} days ({weeks} weeks) - plan ahead"


def fetch_earnings_date_cached(
    conn: DatabaseConnection, symbol: str, ttl_days: int = 30
) -> datetime | None:
    """Fetch earnings date with caching support (default TTL: 30 days).

    This function checks the reference_cache table first. If valid cached data
    exists (within TTL), it returns the cached data without calling external APIs.
    If cache is stale or missing, it fetches fresh data and caches it.

    Earnings dates change infrequently, so TTL is longer than news (30 days vs 6 hours).

    Args:
        conn: Database connection
        symbol: Stock ticker symbol
        ttl_days: Cache TTL in days (default: 30 days)

    Returns:
        datetime object for next earnings date, or None if not found

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     earnings_date = fetch_earnings_date_cached(conn, "NVDA")
        >>> # First call fetches from API and caches
        >>> # Second call within 30 days uses cache
    """
    # Check cache first
    cache_cutoff = date.today() - timedelta(days=ttl_days)

    cached_row = conn.execute(
        """
        SELECT payload
        FROM reference_cache
        WHERE ticker = %s
          AND source = %s
          AND as_of_date >= %s
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        [symbol, "earnings", cache_cutoff.isoformat()],
    ).fetchone()

    # Cache hit - return cached data
    if cached_row is not None:
        payload = cached_row[0]
        # Payload is a dict with earnings_date as ISO string
        if isinstance(payload, dict):
            earnings_date_str = payload.get("earnings_date")
            if earnings_date_str:
                return datetime.fromisoformat(earnings_date_str)
        return None

    # Cache miss or stale - fetch fresh data
    fresh_data = fetch_earnings_date(symbol)

    # Cache the fresh data (even if None, to avoid repeated failed lookups)
    payload_data = {
        "earnings_date": fresh_data.isoformat() if fresh_data else None,
    }

    conn.execute(
        """
        INSERT INTO reference_cache (ticker, as_of_date, payload, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ticker, as_of_date, source)
        DO UPDATE SET payload = EXCLUDED.payload
        """,
        [
            symbol,
            date.today().isoformat(),
            json.dumps(payload_data),
            "earnings",
        ],
    )
    conn.commit()

    return fresh_data
