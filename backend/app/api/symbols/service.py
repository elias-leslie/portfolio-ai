"""Shared symbol intelligence assembly."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

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
from .models import (
    RecommendationSection,
    SymbolIntelligenceResponse,
    SymbolSectionIssue,
)
from .recommendations import generate_recommendation

if TYPE_CHECKING:
    from app.services.jenny_operator_service import JennyOperatorService
    from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

_SECTION_BUILD_FAILURE_MESSAGES = {
    "quote": "Current quote could not be prepared for display.",
    "scores": "Scores could not be prepared for display.",
    "signal": "Signal evidence could not be prepared for display.",
    "trading": "Trading guidance could not be prepared for display.",
    "company": "Company context could not be prepared for display.",
    "trends": "Trend context could not be prepared for display.",
    "alerts": "Alert indicators could not be prepared for display.",
    "news": "News context could not be prepared for display.",
    "portfolio": "Portfolio position context could not be prepared for display.",
    "strategies": "Strategy context could not be prepared for display.",
    "market": "Market context could not be prepared for display.",
    "recommendation": "The live recommendation is temporarily unavailable.",
    "decision": "The current decision is temporarily unavailable.",
}


def _add_section_issue(
    response: SymbolIntelligenceResponse,
    *,
    section: str,
    message: str,
) -> None:
    if any(issue.section == section for issue in response.section_issues):
        return
    response.section_issues.append(SymbolSectionIssue(section=section, message=message))


def _build_section(
    response: SymbolIntelligenceResponse,
    *,
    symbol: str,
    section: str,
    build: Callable[[], Any],
) -> Any:
    """Build one response section without discarding independent valid data."""
    try:
        return build()
    except Exception as exc:
        logger.warning(
            "symbol_intelligence_section_failed",
            symbol=symbol,
            section=section,
            error=str(exc),
        )
        _add_section_issue(
            response,
            section=section,
            message=_SECTION_BUILD_FAILURE_MESSAGES[section],
        )
        return None


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

    response = SymbolIntelligenceResponse(
        symbol=symbol,
        generated_at=datetime.now(UTC),
        section_issues=[
            SymbolSectionIssue(**issue) for issue in data.get("section_issues", [])
        ],
    )
    source_failures = {issue.section for issue in response.section_issues}
    response.quote = _build_section(
        response,
        symbol=symbol,
        section="quote",
        build=lambda: build_quote_section(quote),
    )

    if watchlist:
        response.scores = _build_section(
            response,
            symbol=symbol,
            section="scores",
            build=lambda: build_scores_section(watchlist),
        )
        response.signal = _build_section(
            response,
            symbol=symbol,
            section="signal",
            build=lambda: build_signal_section(watchlist),
        )
        response.trading = _build_section(
            response,
            symbol=symbol,
            section="trading",
            build=lambda: build_trading_section(watchlist),
        )
        response.company = _build_section(
            response,
            symbol=symbol,
            section="company",
            build=lambda: build_company_section(watchlist),
        )
        response.trends = _build_section(
            response,
            symbol=symbol,
            section="trends",
            build=lambda: build_trends_section(watchlist),
        )
        alerts = _build_section(
            response,
            symbol=symbol,
            section="alerts",
            build=lambda: build_alerts(watchlist),
        )
        if alerts is not None:
            response.alerts = alerts
        response.news = _build_section(
            response,
            symbol=symbol,
            section="news",
            build=lambda: build_news_section_from_watchlist(watchlist),
        )

    pos = portfolio.get("position") if portfolio else None
    summary = portfolio.get("summary") if portfolio else None
    if "portfolio" not in source_failures:
        response.portfolio = _build_section(
            response,
            symbol=symbol,
            section="portfolio",
            build=lambda: build_portfolio_section(pos, summary),
        )

    if strategies:
        response.strategies = _build_section(
            response,
            symbol=symbol,
            section="strategies",
            build=lambda: build_strategies_section(strategies),
        )

    if news and not response.news:
        response.news = _build_section(
            response,
            symbol=symbol,
            section="news",
            build=lambda: build_news_section_fallback(news),
        )

    if market:
        response.market = _build_section(
            response,
            symbol=symbol,
            section="market",
            build=lambda: build_market_section(market),
        )

    recommendation_payload: dict[str, Any] | None = None
    if not {"watchlist", "portfolio"}.intersection(source_failures):
        recommendation_payload = _build_section(
            response,
            symbol=symbol,
            section="recommendation",
            build=lambda: generate_recommendation(watchlist, portfolio, market),
        )
        if recommendation_payload is not None:
            response.recommendation = _build_section(
                response,
                symbol=symbol,
                section="recommendation",
                build=lambda: RecommendationSection(**recommendation_payload),
            )
    else:
        _add_section_issue(
            response,
            section="recommendation",
            message=(
                "The live recommendation is unavailable because required signal or "
                "portfolio inputs did not load."
            ),
        )

    if include_decision:
        try:
            notifications = _jenny_service()._get_open_notifications_for_symbol(symbol, limit=5)
            latest_review = _jenny_service()._get_latest_symbol_review(symbol)
        except Exception as exc:
            logger.warning("symbol_decision_context_failed", symbol=symbol, error=str(exc))
            notifications = []
            latest_review = None
        if recommendation_payload is not None or notifications or latest_review is not None:
            response.decision = _build_section(
                response,
                symbol=symbol,
                section="decision",
                build=lambda: build_symbol_decision(
                    symbol=symbol,
                    recommendation=recommendation_payload,
                    generated_at=response.generated_at,
                    notifications=notifications,
                    latest_review=latest_review,
                    portfolio_position=(
                        response.portfolio.position if response.portfolio else None
                    ),
                ),
            )
        else:
            _add_section_issue(
                response,
                section="decision",
                message=(
                    "The current decision is unavailable because its live inputs did "
                    "not load."
                ),
            )

    if response.section_issues and not any(
        (
            response.quote,
            response.scores,
            response.signal,
            response.trading,
            response.company,
            response.trends,
            response.portfolio,
            response.strategies,
            response.news,
            response.market,
            response.alerts,
            response.recommendation,
            response.decision,
        )
    ):
        response.error = "Symbol intelligence is temporarily unavailable."

    return response
