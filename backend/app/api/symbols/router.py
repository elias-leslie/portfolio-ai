"""Symbol Intelligence API router.

Provides the main endpoint for comprehensive symbol data aggregation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.storage import get_storage
from app.watchlist.watchlist_service import WatchlistService

from .builders import (
    build_alerts,
    build_company_section,
    build_market_section,
    build_news_section_fallback,
    build_news_section_from_watchlist,
    build_paper_trades_section,
    build_portfolio_section,
    build_scores_section,
    build_signal_section,
    build_strategies_section,
    build_trading_section,
    build_trends_section,
)
from .data_fetchers import fetch_all_data
from .models import RecommendationSection, SymbolIntelligenceResponse
from .recommendations import generate_recommendation

logger = get_logger(__name__)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])
storage = get_storage()
watchlist_service = WatchlistService(storage)


def _build_response(
    symbol: str, include_market: bool, include_paper_trades: bool, include_strategies: bool
) -> SymbolIntelligenceResponse:
    """Build the full intelligence response synchronously."""
    symbol = symbol.upper()

    # Fetch all data
    data = fetch_all_data(
        symbol, storage, watchlist_service, include_market, include_paper_trades, include_strategies
    )
    watchlist = data["watchlist"]
    portfolio = data["portfolio"]
    paper_trades = data["paper_trades"]
    strategies = data["strategies"]
    news = data["news"]
    market = data["market"]

    # Build response
    response = SymbolIntelligenceResponse(symbol=symbol, generated_at=datetime.now(UTC))

    # Build sections from watchlist data
    if watchlist:
        response.scores = build_scores_section(watchlist)
        response.signal = build_signal_section(watchlist)
        response.trading = build_trading_section(watchlist)
        response.company = build_company_section(watchlist)
        response.trends = build_trends_section(watchlist)
        response.alerts = build_alerts(watchlist)
        response.news = build_news_section_from_watchlist(watchlist)

    # Portfolio section
    pos = portfolio.get("position") if portfolio else None
    summary = portfolio.get("summary") if portfolio else None
    response.portfolio = build_portfolio_section(pos, summary)

    # Paper trades section
    if paper_trades:
        response.paper_trades = build_paper_trades_section(paper_trades)

    # Strategies section
    if strategies:
        response.strategies = build_strategies_section(strategies)

    # News section fallback
    if news and not response.news:
        response.news = build_news_section_fallback(news)

    # Market section
    if market:
        response.market = build_market_section(market)

    # Generate recommendation
    response.recommendation = RecommendationSection(
        **generate_recommendation(watchlist, portfolio, market)
    )

    return response


@router.get("/{symbol}/intelligence", response_model=SymbolIntelligenceResponse)
async def get_symbol_intelligence(
    symbol: str,
    include_market: bool = True,
    include_paper_trades: bool = True,
    include_strategies: bool = True,
) -> SymbolIntelligenceResponse:
    """Get comprehensive intelligence for a symbol.

    Returns all relevant data in one call:
    - Watchlist scores and signals
    - Portfolio position (if held)
    - Paper trading history
    - Active strategies
    - News sentiment
    - Market context
    - Personalized recommendation
    """
    try:
        return await run_in_threadpool(
            _build_response, symbol, include_market, include_paper_trades, include_strategies
        )
    except Exception as e:
        logger.exception(f"Error getting symbol intelligence for {symbol}")
        return SymbolIntelligenceResponse(
            symbol=symbol.upper(), generated_at=datetime.now(UTC), error=str(e)
        )
