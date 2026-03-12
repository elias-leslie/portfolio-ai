"""Symbol Intelligence API router.

Provides the main endpoint for comprehensive symbol data aggregation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.models.symbol_workflow import (
    SymbolWorkflow,
    SymbolWorkflowOutcomeRequest,
    SymbolWorkflowTransitionRequest,
)

from .builders import (
    build_alerts,
    build_company_section,
    build_market_section,
    build_news_section_fallback,
    build_news_section_from_watchlist,
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

if TYPE_CHECKING:
    from app.services.symbol_workflow_service import SymbolWorkflowService
    from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _watchlist_service() -> WatchlistService:
    return import_module("app.watchlist.watchlist_service").WatchlistService(_storage())


@lru_cache(maxsize=1)
def _workflow_service() -> SymbolWorkflowService:
    return import_module("app.services.symbol_workflow_service").SymbolWorkflowService()


def build_symbol_intelligence(
    symbol: str, include_market: bool, include_strategies: bool
) -> SymbolIntelligenceResponse:
    """Build the full intelligence response synchronously."""
    symbol = symbol.upper()

    # Fetch all data
    data = fetch_all_data(
        symbol, _storage(), _watchlist_service(), include_market, include_strategies
    )
    watchlist = data["watchlist"]
    portfolio = data["portfolio"]
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
        return await run_in_threadpool(build_symbol_intelligence, symbol, include_market, include_strategies)
    except Exception as e:
        logger.exception("symbol_intelligence_failed", symbol=symbol)
        return SymbolIntelligenceResponse(
            symbol=symbol.upper(), generated_at=datetime.now(UTC), error=str(e)
        )


@router.get("/{symbol}/workflow", response_model=SymbolWorkflow)
async def get_symbol_workflow(symbol: str) -> SymbolWorkflow:
    """Return the persisted operating workflow for a symbol."""
    payload = await run_in_threadpool(_workflow_service().get_workflow, symbol)
    return SymbolWorkflow.model_validate(payload)


@router.post("/{symbol}/workflow/transition", response_model=SymbolWorkflow)
async def transition_symbol_workflow(
    symbol: str,
    payload: SymbolWorkflowTransitionRequest,
) -> SymbolWorkflow:
    """Advance or reset a symbol inside the investing workflow loop."""
    workflow_service = _workflow_service()
    result = await run_in_threadpool(
        workflow_service.transition,
        symbol,
        payload.stage,
        payload.note,
    )
    return SymbolWorkflow.model_validate(result)


@router.post("/{symbol}/workflow/outcome", response_model=SymbolWorkflow)
async def record_symbol_workflow_outcome(
    symbol: str,
    payload: SymbolWorkflowOutcomeRequest,
) -> SymbolWorkflow:
    """Capture a live position decision with linked Jenny context."""
    workflow_service = _workflow_service()
    result = await run_in_threadpool(
        lambda: workflow_service.record_outcome(
            symbol,
            payload.action,
            payload.note,
            jenny_verdict=payload.jenny_verdict,
            management_action=payload.management_action,
        )
    )
    return SymbolWorkflow.model_validate(result)
