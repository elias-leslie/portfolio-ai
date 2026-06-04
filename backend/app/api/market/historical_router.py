"""Historical market data endpoints (fear-greed, news sentiment, indicators, sectors)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.market._core_helpers import build_intelligence_response_data, fetch_core_market_data
from app.api.market_responses import (
    FearGreedHistoryResponse,
    IndicatorDataPoint,
    IndicatorHistoryResponse,
    NewsSentimentHistoryResponse,
    SectorHistory,
    SectorHistoryResponse,
)
from app.api.market_transformers import (
    build_indicator_data_points,
    build_sector_history,
    sort_sectors_by_performance,
)
from app.constants import CACHE_TTL_MEDIUM, CACHE_TTL_SHORT, SECTOR_ETFS
from app.logging_config import get_logger
from app.market.intraday_mood import calculate_intraday_mood_score, label_intraday_mood
from app.middleware.cache import cache_response
from app.repositories.market_repository import MarketRepository
from app.sources.yfinance_source import YFinanceSource
from app.storage import get_storage
from app.utils.formatters import format_db_date
from app.utils.market_hours import NY_TZ

router = APIRouter()
logger = get_logger(__name__)

_state: dict[str, MarketRepository] = {}


def _get_market_repo() -> MarketRepository:
    """Lazy singleton to avoid DB connection at import time."""
    if "repo" not in _state:
        _state["repo"] = MarketRepository(get_storage())
    return _state["repo"]


def _quote_market_date(value: object) -> date | None:
    if not isinstance(value, datetime):
        return None
    quote_ts = value if value.tzinfo else value.replace(tzinfo=UTC)
    return quote_ts.astimezone(NY_TZ).date()


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _last_history_date(dates: list[str]) -> date | None:
    if not dates:
        return None
    try:
        return date.fromisoformat(dates[-1].split("T")[0])
    except ValueError:
        return None


def _append_live_mood_point(
    *,
    dates: list[str],
    scores: list[float],
    labels: list[str],
    put_call_ratios: list[float | None],
) -> tuple[list[str], list[float], list[str], list[float | None], list[str], str, str | None]:
    market_data = fetch_core_market_data()
    current_timestamp = market_data.current_timestamp
    quote_date = _quote_market_date(_parse_iso_datetime(current_timestamp))
    latest_date = _last_history_date(dates)
    if quote_date is None or latest_date is None or quote_date <= latest_date:
        return dates, scores, labels, put_call_ratios, ["daily_close"] * len(dates), "daily_close", None

    built = build_intelligence_response_data(market_data, current_timestamp)
    sectors = [
        *list(built["leading_sectors"]),
        *list(built["neutral_sectors"]),
        *list(built["lagging_sectors"]),
    ]
    mood_score = calculate_intraday_mood_score(built["enriched_indicators"], sectors)
    putcall = built["enriched_indicators"].get("putcall")
    putcall_value = getattr(putcall, "value", None)
    return (
        [*dates, quote_date.isoformat()],
        [*scores, float(mood_score)],
        [*labels, label_intraday_mood(mood_score)],
        [
            *put_call_ratios,
            float(putcall_value) if isinstance(putcall_value, (int, float)) else None,
        ],
        [*(["daily_close"] * len(dates)), "live_proxy"],
        "live_proxy",
        current_timestamp,
    )


def _append_current_quote_row(rows: list[tuple[Any, ...]], quote: object | None) -> list[tuple[Any, ...]]:
    if not quote:
        return rows
    quote_date = _quote_market_date(getattr(quote, "cached_at", None))
    quote_price = getattr(quote, "price", None)
    if quote_date is None or not isinstance(quote_price, (int, float)) or quote_price <= 0:
        return rows
    latest_row_date = rows[-1][0] if rows else None
    latest_date = latest_row_date.date() if isinstance(latest_row_date, datetime) else latest_row_date
    if isinstance(latest_date, date) and quote_date == latest_date:
        return [*rows[:-1], (quote_date, float(quote_price))]
    if not isinstance(latest_date, date) or quote_date > latest_date:
        return [*rows, (quote_date, float(quote_price))]
    return rows

# Historical data limits
MAX_HISTORICAL_DAYS = 1825  # ~5 years

# Indicator symbol to key mapping
INDICATOR_SYMBOLS: dict[str, str] = {
    "vix": "^VIX",
    "sp500": "^GSPC",
    "tnx": "^TNX",
    "dxy": "DX-Y.NYB",
}

# Sector threshold constants for validation
SECTOR_MAX_LOSS_THRESHOLD = -60.0
SECTOR_MAX_GAIN_THRESHOLD = 200.0


def _validate_sector_price_change(rows: list[tuple[Any, float]], symbol: str) -> bool:
    """Validate that sector price change is within reasonable bounds.

    Checks if the percentage change between first and last price is realistic
    (not > 60% loss or > 200% gain), which could indicate data issues.

    Args:
        rows: List of (date, close_price) tuples
        symbol: Sector ETF symbol for logging

    Returns:
        True if price change is valid (within bounds), False if unrealistic
    """
    if len(rows) < 2:
        return True

    first_close = rows[0][1]
    last_close = rows[-1][1]
    pct_change = ((last_close - first_close) / first_close) * 100

    if pct_change < SECTOR_MAX_LOSS_THRESHOLD or pct_change > SECTOR_MAX_GAIN_THRESHOLD:
        logger.error(
            "sector_history_unrealistic_change",
            symbol=symbol,
            first_close=first_close,
            last_close=last_close,
            pct_change=pct_change,
        )
        return False

    return True


# API endpoints
@router.get("/fear-greed-history", response_model=FearGreedHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_fear_greed_history(
    request: Request,
    days: int = Query(365, ge=30, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
) -> FearGreedHistoryResponse:
    """Get Fear & Greed historical data for trend charts.

    Includes put/call ratio overlay data when available.
    """
    # Use repository for data access
    rows = _get_market_repo().get_fear_greed_history_data(days)

    dates: list[str] = []
    scores: list[float] = []
    labels: list[str] = []
    put_call_ratios: list[float | None] = []
    for row in rows:
        if row[0] and row[1] is not None:
            formatted_date = format_db_date(row[0])
            if formatted_date is None:
                continue  # Skip if not a valid date type
            dates.append(formatted_date)
            scores.append(float(row[1]))
            labels.append(str(row[2]) if row[2] else "Unknown")
            # P/C ratio may be null for dates before we started collecting
            put_call_ratios.append(float(row[3]) if row[3] is not None else None)
    (
        dates,
        scores,
        labels,
        put_call_ratios,
        sources,
        latest_source,
        latest_as_of,
    ) = _append_live_mood_point(
        dates=dates,
        scores=scores,
        labels=labels,
        put_call_ratios=put_call_ratios,
    )

    return FearGreedHistoryResponse(
        dates=dates,
        scores=scores,
        labels=labels,
        sources=sources,
        latest_source=latest_source,
        latest_as_of=latest_as_of,
        put_call_ratios=put_call_ratios,
    )


@router.get("/news-sentiment-history", response_model=NewsSentimentHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_news_sentiment_history(
    request: Request,
    days: int = Query(30, ge=1, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
    granularity: str = Query(
        "daily",
        description="Data granularity: 'daily' for day-level, 'hourly' for hour-level",
    ),
) -> NewsSentimentHistoryResponse:
    """Get news sentiment historical data for trend charts.

    Returns daily or hourly aggregated sentiment scores from news_summary_log.
    Scores range from -1 (very negative) to +1 (very positive).
    """
    if granularity == "hourly":
        rows = _get_market_repo().get_news_sentiment_hourly(days)
    else:
        rows = _get_market_repo().get_news_sentiment_daily(days)

    dates: list[str] = []
    scores: list[float] = []
    positive_counts: list[int] = []
    negative_counts: list[int] = []
    article_counts: list[int] = []

    for row in rows:
        period, avg_score, pos_count, neg_count, total_count = row
        if period and avg_score is not None:
            formatted_date = format_db_date(period)
            if formatted_date is None:
                continue
            dates.append(formatted_date)
            scores.append(float(avg_score))
            positive_counts.append(int(pos_count) if pos_count else 0)
            negative_counts.append(int(neg_count) if neg_count else 0)
            article_counts.append(int(total_count) if total_count else 0)

    return NewsSentimentHistoryResponse(
        dates=dates,
        scores=scores,
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        article_counts=article_counts,
    )


@router.get("/indicator-history", response_model=IndicatorHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_indicator_history(
    request: Request,
    days: int = Query(365, ge=30, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
) -> IndicatorHistoryResponse:
    """Get key indicator historical data for trend charts."""
    result_data: dict[str, list[dict[str, Any]]] = {}
    period_start = ""
    period_end = ""
    from app.api.market._core_helpers import _get_price_fetcher  # noqa: PLC0415

    current_prices = _get_price_fetcher().fetch_price_data(list(INDICATOR_SYMBOLS.values()))

    for key, symbol in INDICATOR_SYMBOLS.items():
        # Use repository for data access
        rows = _get_market_repo().get_indicator_history_data(symbol, days)
        rows = _append_current_quote_row(rows, current_prices.get(symbol))

        data_points, period_start, period_end = build_indicator_data_points(
            rows, period_start, period_end
        )
        result_data[key] = data_points

    return IndicatorHistoryResponse(
        sp500=[IndicatorDataPoint(**dp) for dp in result_data.get("sp500", [])],
        vix=[IndicatorDataPoint(**dp) for dp in result_data.get("vix", [])],
        tnx=[IndicatorDataPoint(**dp) for dp in result_data.get("tnx", [])],
        dxy=[IndicatorDataPoint(**dp) for dp in result_data.get("dxy", [])],
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/sector-history", response_model=SectorHistoryResponse)
@cache_response(ttl=CACHE_TTL_MEDIUM)
async def get_sector_history(
    request: Request,
    days: int = Query(365, ge=30, le=MAX_HISTORICAL_DAYS, description="Number of days of history"),
) -> SectorHistoryResponse:
    """Get sector ETF historical data for performance charts.

    Uses YFinanceSource to ensure adjusted prices (accounting for splits/dividends).
    This is necessary because DB stores prices at ingestion time which become stale
    after corporate actions like stock splits.
    """
    sectors: list[SectorHistory] = []
    period_start = ""
    period_end = ""

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # Use YFinanceSource for data access (layer separation)
    yf_source = YFinanceSource()
    from app.api.market._core_helpers import _get_price_fetcher  # noqa: PLC0415

    current_prices = _get_price_fetcher().fetch_price_data(list(SECTOR_ETFS.keys()))

    for symbol, name in SECTOR_ETFS.items():
        # Fetch fresh adjusted prices via YFinanceSource
        rows = yf_source.fetch_sector_history(symbol, start_date, end_date)

        if not rows:
            logger.warning("sector_history_no_data", symbol=symbol)
            continue

        # Skip this sector if price change is unrealistic (data quality issue)
        if not _validate_sector_price_change(rows, symbol):
            continue
        rows = _append_current_quote_row(rows, current_prices.get(symbol))

        sector_history, period_start, period_end = build_sector_history(
            symbol, name, rows, period_start, period_end
        )
        sectors.append(sector_history)

    # Sort by current performance descending
    sectors = sort_sectors_by_performance(sectors)

    return SectorHistoryResponse(
        sectors=sectors,
        period_start=period_start,
        period_end=period_end,
    )
