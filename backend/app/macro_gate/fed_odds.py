"""FedWatch-style rate odds from fed-funds futures (ZQ on CBOT, via Yahoo).

A ZQ contract settles to 100 minus the average daily EFFR over its delivery
month, so its price carries the market's blended rate expectation for that
month. With the current EFFR as the pre-meeting anchor we can solve the
meeting-month contract for the implied post-meeting rate (CME FedWatch's core
identity) and bucket the implied move into cut / hold / hike odds, assuming
the move, if any, is 25bp.

Deliberately lean (v1): next-meeting odds plus a year-end implied rate
("~N cuts priced by Dec") — not the full conditional meeting tree. The
year-end read uses the January contract of the following year, which is a
clean post-December-meeting month for most of its days (the late-January
meeting blends only its last few days; accepted approximation). Display-only:
this module never feeds caution scoring.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date, datetime

import structlog

from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage.facade import get_storage
from app.utils._market_calendar import NY_TZ
from app.utils.db_helpers import ensure_symbols_exist

logger = structlog.get_logger(__name__)

# CME futures month codes, Jan..Dec.
_MONTH_CODES = "FGHJKMNQUVXZ"

# Assumed size of a single Fed move (percentage points).
_MOVE_SIZE = 0.25

# If the meeting leaves fewer post-decision days than this in its month, the
# blended-average algebra divides by a tiny day count and amplifies quote
# noise; use the following month's contract (a clean post-meeting month) instead.
_MIN_POST_MEETING_DAYS = 5


@dataclass(frozen=True, slots=True)
class FedOdds:
    meeting_date: str  # ISO date of the next FOMC decision
    effr: float  # current effective fed funds rate (%), the pre-meeting anchor
    implied_post_rate: float  # market-implied rate after the meeting (%)
    p_cut: int  # 0-100
    p_hold: int  # 0-100
    p_hike: int  # 0-100
    year_end_rate: float | None  # implied rate after the December meeting (%)
    cuts_priced_by_year_end: float | None  # (effr - year_end_rate) / 25bp
    as_of: str | None  # latest quote timestamp backing the read


def _zq_symbol(year: int, month: int) -> str:
    return f"ZQ{_MONTH_CODES[month - 1]}{year % 100:02d}.CBT"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _latest_effr() -> float | None:
    rows = get_storage().query(
        """
        SELECT value FROM macro_indicators
        WHERE series_id = 'EFFR' AND value IS NOT NULL
        ORDER BY observation_date DESC LIMIT 1
        """
    )
    for row in rows.iter_rows(named=True):
        value = row.get("value")
        return float(value) if value is not None else None
    return None


def _next_fomc_date(today: date) -> date | None:
    rows = get_storage().query(
        """
        SELECT event_date FROM market_events
        WHERE event_type::text = 'fomc_decision' AND event_date >= %s
        ORDER BY event_date ASC LIMIT 1
        """,
        [today],
    )
    for row in rows.iter_rows(named=True):
        value = row.get("event_date")
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
    return None


def _quote_prices(symbols: list[str]) -> dict[str, tuple[float, str | None]]:
    """Fetch ZQ prices, returning {symbol: (price, cached_at_iso)}.

    ZQ contracts are not part of any ingestion universe, so register them in
    the symbols table first (price_cache has an FK on it).
    """
    storage = get_storage()
    ensure_symbols_exist(storage, symbols)
    quotes = PriceDataFetcher(storage).fetch_price_data(symbols)
    prices: dict[str, tuple[float, str | None]] = {}
    for symbol in symbols:
        quote = quotes.get(symbol)
        price = getattr(quote, "price", None)
        if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            continue
        cached_at = getattr(quote, "cached_at", None)
        as_of = cached_at.isoformat() if isinstance(cached_at, datetime) else None
        prices[symbol] = (float(price), as_of)
    return prices


def _solve_post_meeting_rate(
    *,
    meeting: date,
    effr: float,
    meeting_month_price: float | None,
    next_month_price: float | None,
) -> float | None:
    """Implied post-meeting rate from the meeting-month contract average.

    The contract's implied month-average rate blends pre-meeting days at the
    current EFFR with post-meeting days at the unknown new rate (decision
    effective the day after the meeting). Late-month meetings leave too few
    post days to solve cleanly, so fall back to the next month's contract,
    which prices the new rate directly.
    """
    days_in_month = calendar.monthrange(meeting.year, meeting.month)[1]
    pre_days = meeting.day  # meeting day itself still accrues at the old rate
    post_days = days_in_month - pre_days

    if post_days >= _MIN_POST_MEETING_DAYS and meeting_month_price is not None:
        month_avg = 100.0 - meeting_month_price
        return (month_avg * days_in_month - pre_days * effr) / post_days
    if next_month_price is not None:
        return 100.0 - next_month_price
    return None


def _move_odds(implied_post_rate: float, effr: float) -> tuple[int, int, int]:
    """Bucket the implied move into (p_cut, p_hold, p_hike), percent."""
    delta = implied_post_rate - effr
    p_cut = min(100, round(max(0.0, -delta) / _MOVE_SIZE * 100))
    p_hike = min(100, round(max(0.0, delta) / _MOVE_SIZE * 100))
    return p_cut, 100 - p_cut - p_hike, p_hike


def get_fed_odds(now: datetime | None = None) -> FedOdds | None:
    """Best-effort FedWatch read; returns None when any required input is missing."""
    try:
        today = (now or datetime.now(NY_TZ)).astimezone(NY_TZ).date()
        effr = _latest_effr()
        meeting = _next_fomc_date(today)
        if effr is None or meeting is None:
            logger.debug("fed_odds_inputs_missing", effr=effr, meeting=meeting)
            return None

        next_year, next_month = _next_month(meeting.year, meeting.month)
        meeting_symbol = _zq_symbol(meeting.year, meeting.month)
        fallback_symbol = _zq_symbol(next_year, next_month)
        year_end_symbol = _zq_symbol(today.year + 1, 1)
        symbols = list(dict.fromkeys([meeting_symbol, fallback_symbol, year_end_symbol]))

        prices = _quote_prices(symbols)
        implied_post_rate = _solve_post_meeting_rate(
            meeting=meeting,
            effr=effr,
            meeting_month_price=(prices.get(meeting_symbol) or (None,))[0],
            next_month_price=(prices.get(fallback_symbol) or (None,))[0],
        )
        if implied_post_rate is None:
            logger.debug("fed_odds_no_zq_quotes", symbols=symbols)
            return None

        p_cut, p_hold, p_hike = _move_odds(implied_post_rate, effr)

        year_end_price = (prices.get(year_end_symbol) or (None,))[0]
        year_end_rate = 100.0 - year_end_price if year_end_price is not None else None
        cuts_priced = (
            round((effr - year_end_rate) / _MOVE_SIZE, 1) if year_end_rate is not None else None
        )

        stamps = [as_of for _, as_of in prices.values() if as_of]
        return FedOdds(
            meeting_date=meeting.isoformat(),
            effr=round(effr, 2),
            implied_post_rate=round(implied_post_rate, 2),
            p_cut=p_cut,
            p_hold=p_hold,
            p_hike=p_hike,
            year_end_rate=round(year_end_rate, 2) if year_end_rate is not None else None,
            cuts_priced_by_year_end=cuts_priced,
            as_of=max(stamps) if stamps else None,
        )
    except Exception:  # pragma: no cover - display-only, never break conditions
        logger.warning("fed_odds_failed", exc_info=True)
        return None
