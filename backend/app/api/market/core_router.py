"""Core market data endpoints (conditions, intelligence, trends, status, prices, movers)."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.api.market._core_helpers import (
    _extract_price,
    _extract_price_timestamp,
    build_intelligence_response_data,
    fetch_core_market_data,
)
from app.api.market._response_builders import (
    build_fear_greed_response,
    build_market_health_response,
    build_sector_rotation_response,
)
from app.api.market_responses import (
    MarketConditionsResponse,
    MarketMoverItem,
    MarketMoversResponse,
    MarketStatusResponse,
    PriceResponse,
    PricesResponse,
)
from app.constants import CACHE_TTL_LONG, CACHE_TTL_MEDIUM, CACHE_TTL_SHORT
from app.logging_config import get_logger
from app.market.sentiment import calculate_market_health
from app.middleware.cache import cache_response
from app.models.market_intelligence import (
    MarketIntelligenceResponse,
    MarketTrendsResponse,
)
from app.repositories.market_repository import MarketRepository
from app.storage import get_storage
from app.utils.market_hours import (
    NY_TZ,
    get_expected_data_date,
    get_last_trading_day,
    get_market_status,
    get_next_trading_day,
    is_early_close_day,
    is_market_holiday,
)

router = APIRouter()
logger = get_logger(__name__)

_state: dict[str, MarketRepository] = {}


def _get_market_repo() -> MarketRepository:
    """Lazy singleton to avoid DB connection at import time."""
    if "repo" not in _state:
        _state["repo"] = MarketRepository(get_storage())
    return _state["repo"]

# Historical data limits
MAX_SYMBOLS_PER_REQUEST = 50  # Prevent DoS with large symbol lists


@router.get("/conditions", response_model=MarketConditionsResponse)
@cache_response(ttl=CACHE_TTL_MEDIUM)
async def get_market_conditions(request: Request) -> MarketConditionsResponse:
    """Get current market conditions with health scoring."""
    market_data = await run_in_threadpool(fetch_core_market_data)

    health_score = calculate_market_health(
        vix_price=_extract_price(market_data.vix_data),
        sp500_price=_extract_price(market_data.sp500_data),
        tnx_yield=_extract_price(market_data.tnx_data),
        dxy_price=_extract_price(market_data.dxy_data),
        sector_data=market_data.sector_data,
        current_timestamp=market_data.current_timestamp,
    )

    return MarketConditionsResponse(
        sp500={
            "price": _extract_price(market_data.sp500_data),
            "change_pct": None,
            "last_updated": _extract_price_timestamp(market_data.sp500_data),
        },
        vix={
            "price": _extract_price(market_data.vix_data),
            "level": None,
            "last_updated": _extract_price_timestamp(market_data.vix_data),
        },
        tnx={
            "yield": _extract_price(market_data.tnx_data),
            "last_updated": _extract_price_timestamp(market_data.tnx_data),
        },
        dxy={
            "price": _extract_price(market_data.dxy_data),
            "last_updated": _extract_price_timestamp(market_data.dxy_data),
        },
        health=health_score,
    )


@router.get("/prices", response_model=PricesResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prices(
    request: Request,
    symbols: str = Query(..., description="Comma-separated symbols"),
) -> PricesResponse:
    """Get current prices for stock symbols."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    if len(symbol_list) > MAX_SYMBOLS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols allowed, got {len(symbol_list)}",
        )

    from app.api.market._core_helpers import _get_price_fetcher  # noqa: PLC0415

    price_data = await run_in_threadpool(
        lambda: _get_price_fetcher().fetch_cached_price_data(symbol_list)
    )

    prices = {
        symbol: PriceResponse(
            symbol=data.symbol,
            price=data.price,
            beta=data.beta,
            volatility=data.volatility,
            sector=data.sector,
        )
        for symbol, data in price_data.items()
    }

    return PricesResponse(prices=prices, count=len(prices))


@router.get("/intelligence", response_model=MarketIntelligenceResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_market_intelligence(_request: Request) -> MarketIntelligenceResponse:
    """Get unified market intelligence with narrative, dual scoring, and sector rotation."""
    market_data = await run_in_threadpool(fetch_core_market_data)

    current_timestamp = market_data.current_timestamp

    data = await run_in_threadpool(
        build_intelligence_response_data,
        market_data,
        current_timestamp,
    )

    return MarketIntelligenceResponse(
        market_health=build_market_health_response(data["health_score_data"]),
        fear_greed=build_fear_greed_response(data["fg_reading"]),
        indicators=data["enriched_indicators"],
        sector_rotation=build_sector_rotation_response(
            data["leading_sectors"],
            data["neutral_sectors"],
            data["lagging_sectors"],
        ),
        options_activity=data["options_activity"],
        last_updated=current_timestamp,
    )


@router.get("/trends", response_model=MarketTrendsResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_market_trends(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days of historical data"),
) -> MarketTrendsResponse:
    """Get market trends for sparkline charts."""
    rows = await run_in_threadpool(lambda: _get_market_repo().get_market_trends_data(days))

    dates: list[str] = []
    fear_greed_scores_list: list[float] = []
    for row in rows:
        date_val = row[0]
        score_val = row[1]
        if isinstance(date_val, (date, datetime)) and isinstance(score_val, (int, float)):
            dates.append(date_val.isoformat())
            fear_greed_scores_list.append(float(score_val))

    return MarketTrendsResponse(
        dates=dates,
        fear_greed_scores=fear_greed_scores_list,
        market_health_scores=[],
    )


@router.get("/status", response_model=MarketStatusResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_market_status_endpoint(request: Request) -> MarketStatusResponse:
    """Get current market status and trading day information."""
    now = datetime.now(NY_TZ)
    today = now.date()

    status = get_market_status(now)
    last_trading = get_last_trading_day(today)
    next_trading = get_next_trading_day(today)
    is_holiday, holiday_name = is_market_holiday(today)
    is_early, early_name = is_early_close_day(today)
    expected_data = get_expected_data_date(now)

    return MarketStatusResponse(
        status=status,
        is_open=status == "open",
        last_trading_day=last_trading.isoformat(),
        next_trading_day=next_trading.isoformat(),
        current_time_et=now.strftime("%Y-%m-%d %H:%M:%S ET"),
        expected_data_date=expected_data.isoformat(),
        is_holiday=is_holiday,
        holiday_name=holiday_name,
        is_early_close=is_early,
        early_close_name=early_name,
    )


@router.get("/movers", response_model=MarketMoversResponse)
@cache_response(ttl=CACHE_TTL_LONG)
async def get_market_movers(
    request: Request,
    count: int = Query(10, ge=1, le=25, description="Number of gainers/losers to return"),
) -> MarketMoversResponse:
    """Get top market movers (gainers and losers)."""
    from app.sources.market_movers_source import MarketMover, fetch_market_movers  # noqa: PLC0415

    result = await run_in_threadpool(lambda: fetch_market_movers(get_storage(), count=count))

    def to_item(m: MarketMover) -> MarketMoverItem:
        return MarketMoverItem(
            symbol=m.symbol,
            name=m.name,
            price=m.price,
            change_pct=m.change_pct,
            volume=m.volume,
            market_cap=m.market_cap,
            avg_volume=m.avg_volume,
            rvol=m.rvol,
            sector=m.sector,
        )

    return MarketMoversResponse(
        gainers=[to_item(m) for m in result.gainers],
        losers=[to_item(m) for m in result.losers],
        most_active=[to_item(m) for m in result.most_active],
        top_rvol=[to_item(m) for m in result.top_rvol],
        source=result.source,
        last_updated=result.last_updated,
    )
