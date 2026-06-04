"""Shared symbol intelligence assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from app.logging_config import get_logger

from .builders import (
    build_alerts,
    build_company_section,
    build_market_section,
    build_news_section_fallback,
    build_news_section_from_watchlist,
    build_portfolio_section,
    build_quote_section,
    build_scores_section,
    build_signal_section,
    build_strategies_section,
    build_trading_section,
    build_trends_section,
)
from .data_fetchers import fetch_all_data
from .decisions import build_symbol_decision
from .models import RecommendationSection, SymbolIntelligenceResponse
from .recommendations import generate_recommendation

if TYPE_CHECKING:
    from app.services.jenny_operator_service import JennyOperatorService
    from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _watchlist_service() -> WatchlistService:
    return import_module("app.watchlist.watchlist_service").WatchlistService(_storage())


@lru_cache(maxsize=1)
def _jenny_service() -> JennyOperatorService:
    return import_module("app.services.jenny_operator_service").JennyOperatorService()


def build_symbol_intelligence(
    symbol: str,
    include_market: bool = True,
    include_strategies: bool = True,
    include_decision: bool = True,
    force_quote_refresh: bool = False,
) -> SymbolIntelligenceResponse:
    """Build the full intelligence response synchronously."""
    symbol = symbol.upper()
    data = fetch_all_data(
        symbol,
        _storage(),
        _watchlist_service(),
        include_market,
        include_strategies,
        force_quote_refresh=force_quote_refresh,
    )
    quote = data.get("quote")
    watchlist = data["watchlist"]
    portfolio = data["portfolio"]
    strategies = data["strategies"]
    news = data["news"]
    market = data["market"]

    response = SymbolIntelligenceResponse(symbol=symbol, generated_at=datetime.now(UTC))
    response.quote = build_quote_section(quote)

    if watchlist:
        response.scores = build_scores_section(watchlist)
        response.signal = build_signal_section(watchlist)
        response.trading = build_trading_section(watchlist)
        response.company = build_company_section(watchlist)
        response.trends = build_trends_section(watchlist)
        response.alerts = build_alerts(watchlist)
        response.news = build_news_section_from_watchlist(watchlist)

    pos = portfolio.get("position") if portfolio else None
    summary = portfolio.get("summary") if portfolio else None
    response.portfolio = build_portfolio_section(pos, summary)

    if strategies:
        response.strategies = build_strategies_section(strategies)

    if news and not response.news:
        response.news = build_news_section_fallback(news)

    if market:
        response.market = build_market_section(market)

    recommendation_payload = generate_recommendation(watchlist, portfolio, market)
    response.recommendation = RecommendationSection(**recommendation_payload)

    if include_decision:
        try:
            notifications = _jenny_service()._get_open_notifications_for_symbol(symbol, limit=5)
            latest_review = _jenny_service()._get_latest_symbol_review(symbol)
        except Exception as exc:
            logger.warning("symbol_decision_context_failed", symbol=symbol, error=str(exc))
            notifications = []
            latest_review = None
        response.decision = build_symbol_decision(
            symbol=symbol,
            recommendation=recommendation_payload,
            generated_at=response.generated_at,
            notifications=notifications,
            latest_review=latest_review,
            portfolio_position=response.portfolio.position if response.portfolio else None,
        )

    return response
