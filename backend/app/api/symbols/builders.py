"""Response builders for symbol intelligence.

Transforms raw data into typed response sections.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.portfolio.current_facts import calculate_current_position_fact

from .models import (
    AlertIndicator,
    CompanySection,
    KeyEvent,
    MarketSection,
    NewsArticle,
    NewsSection,
    PillarScore,
    PortfolioContext,
    PortfolioSection,
    PositionInfo,
    QuoteSection,
    ScoresSection,
    SignalSection,
    StrategiesSection,
    StrategyInfo,
    TradingSection,
    TrendSection,
)

# Scoring pillar weights - must sum to 1.0
PILLAR_WEIGHTS = {
    "price": 0.22,
    "technical": 0.22,
    "fundamental": 0.26,
    "catalyst": 0.17,
    "options_flow": 0.08,
    "performance": 0.05,
}


def _finite_float(value: Any) -> float | None:
    """Return a JSON-safe float or None for invalid numeric inputs."""
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def build_scores_section(watchlist: dict[str, Any]) -> ScoresSection:
    """Build the scores section from watchlist data."""
    pillars = {}
    for pillar, weight in PILLAR_WEIGHTS.items():
        score_key = f"{pillar}_score"
        pillars[pillar] = PillarScore(
            score=watchlist.get(score_key),
            weight=weight,
            sub_scores=watchlist.get(f"{pillar}_sub_scores"),
            metadata=watchlist.get(f"{pillar}_metadata"),
            stale=watchlist.get(f"{pillar}_stale", False) or False,
        )

    return ScoresSection(
        overall=watchlist.get("overall_score"),
        signal_type=watchlist.get("signal_type"),
        signal_strength=watchlist.get("signal_strength"),
        pillars=pillars,
        data_quality={
            "overall_pct": watchlist.get("data_quality_overall_pct"),
            "pillars": watchlist.get("data_quality_pillars"),
        },
    )


def build_signal_section(watchlist: dict[str, Any]) -> SignalSection:
    """Build the signal section from watchlist data."""
    return SignalSection(
        type=watchlist.get("signal_type"),
        strength=watchlist.get("signal_strength"),
        reasons={
            "bullish": watchlist.get("signal_reasons_bullish") or [],
            "bearish": watchlist.get("signal_reasons_bearish") or [],
        },
        avoid_flags=watchlist.get("avoid_flag_count") or 0,
    )


def build_trading_section(watchlist: dict[str, Any]) -> TradingSection:
    """Build the trading section from watchlist data."""
    return TradingSection(
        style=watchlist.get("recommended_style"),
        confidence=watchlist.get("style_confidence"),
        holding_period=watchlist.get("optimal_holding_period"),
        risk_level=watchlist.get("risk_level"),
        entry_price=watchlist.get("entry_price"),
        stop_loss=watchlist.get("stop_loss"),
        profit_target=watchlist.get("profit_target"),
        position_size_shares=watchlist.get("position_size_shares"),
        position_size_dollars=(
            watchlist.get("position_size_shares", 0) * watchlist.get("entry_price", 0)
            if watchlist.get("position_size_shares") and watchlist.get("entry_price")
            else None
        ),
    )


def build_quote_section(quote: dict[str, Any] | None) -> QuoteSection | None:
    """Build the canonical quote section from price_cache data."""
    if not quote:
        return None

    price = _finite_float(quote.get("price"))
    cached_at = quote.get("cached_at")
    if isinstance(cached_at, datetime):
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=UTC)
        age_seconds = max(
            0.0,
            (datetime.now(UTC) - cached_at.astimezone(UTC)).total_seconds(),
        )
    else:
        age_seconds = None

    if price is None:
        status = "missing"
        label = "Quote unavailable"
    elif age_seconds is None:
        status = "unknown"
        label = "Quote time unavailable"
    elif age_seconds <= 90:
        status = "fresh"
        label = "Fresh quote"
    elif age_seconds <= 300:
        status = "aging"
        label = "Aging quote"
    else:
        status = "stale"
        label = "Stale quote"

    return QuoteSection(
        price=price,
        source=quote.get("source"),
        cached_at=cached_at if isinstance(cached_at, datetime) else None,
        session=quote.get("session"),
        freshness_status=status,
        freshness_label=label,
        error=quote.get("error"),
    )


def build_company_section(watchlist: dict[str, Any]) -> CompanySection:
    """Build the company section from watchlist data."""
    earnings_date = watchlist.get("earnings_date")
    return CompanySection(
        health=watchlist.get("company_health"),
        earnings_date=str(earnings_date) if earnings_date else None,
        earnings_days_away=watchlist.get("earnings_days_away"),
    )


def build_trends_section(watchlist: dict[str, Any]) -> TrendSection:
    """Build the trends section from watchlist data."""
    return TrendSection(
        short_term_aligned=watchlist.get("timeframe_short_aligned"),
        long_term_aligned=watchlist.get("timeframe_long_aligned"),
        volume_relative=watchlist.get("volume_relative"),
    )


def build_alerts(watchlist: dict[str, Any]) -> list[AlertIndicator]:
    """Build the alerts list from watchlist data."""
    priority_indicators = watchlist.get("priority_indicators") or []
    return [
        AlertIndicator(
            icon=ind.get("icon", ""),
            label=ind.get("label", ""),
            tooltip=ind.get("tooltip"),
            priority=ind.get("priority", 0),
            category=ind.get("category"),
        )
        for ind in priority_indicators
        if isinstance(ind, dict)
    ]


def build_news_section_from_watchlist(watchlist: dict[str, Any]) -> NewsSection | None:
    """Build the news section from watchlist news intelligence."""
    news_intel = watchlist.get("news_intelligence") or {}
    recent_news = watchlist.get("recent_news") or {}
    recent_news_summary = recent_news.get("summary") if isinstance(recent_news, dict) else {}
    recent_news_articles = recent_news.get("articles") if isinstance(recent_news, dict) else []

    if not news_intel and not recent_news_articles:
        return None

    recent_articles_raw = news_intel.get("recent_articles") or recent_news_articles or []
    headline = (
        news_intel.get("headline")
        or (recent_news_summary.get("headline") if isinstance(recent_news_summary, dict) else None)
        or (
            recent_articles_raw[0].get("headline")
            if recent_articles_raw and isinstance(recent_articles_raw[0], dict)
            else None
        )
    )
    article_count = (
        news_intel.get("article_count_24h")
        or (
            recent_news_summary.get("article_count")
            if isinstance(recent_news_summary, dict)
            else None
        )
        or len([article for article in recent_articles_raw if isinstance(article, dict)])
    )
    return NewsSection(
        sentiment_score=news_intel.get("sentiment_score"),
        sentiment_label=news_intel.get("sentiment_label"),
        article_count_24h=article_count,
        headline=headline,
        key_events=[
            KeyEvent(
                icon=e.get("icon", "") if isinstance(e, dict) else "",
                text=e.get("text", "") if isinstance(e, dict) else str(e),
                time_ago=e.get("time_ago", "") if isinstance(e, dict) else "",
            )
            for e in (news_intel.get("key_events") or [])[:3]
        ],
        recent_articles=[
            NewsArticle(
                headline=a.get("headline", ""),
                source=a.get("source"),
                published_at=a.get("published_at"),
            )
            for a in recent_articles_raw[:5]
            if isinstance(a, dict)
        ],
    )


def build_news_section_fallback(news: dict[str, Any]) -> NewsSection:
    """Build a fallback news section from news summary data."""
    return NewsSection(
        sentiment_score=news.get("sentiment_score"),
        article_count_24h=news.get("article_count") or 0,
    )


def build_portfolio_section(
    position: dict[str, Any] | None, summary: dict[str, Any] | None
) -> PortfolioSection:
    """Build the portfolio section from position and summary data."""
    if position:
        summary_total_value = summary.get("total_value") if summary else None
        current_fact = calculate_current_position_fact(
            symbol=str(position.get("symbol") or ""),
            shares=position.get("shares", 0),
            cost_basis=position.get("cost_basis", 0),
            position_type=position.get("position_type") or "long",
            current_price=position.get("current_price"),
            invested_total_value=summary_total_value,
        )
        total_value = summary_total_value or current_fact.current_value or 0

        return PortfolioSection(
            held=True,
            position=PositionInfo(
                shares=current_fact.shares,
                cost_basis=current_fact.cost_basis,
                current_value=current_fact.current_value,
                gain=current_fact.gain,
                gain_pct=current_fact.gain_pct,
                weight_pct=current_fact.weight_pct,
                concentration_weight_pct=_finite_float(
                    position.get("concentration_weight_pct")
                ),
                concentration_method=(
                    str(position.get("concentration_method"))
                    if position.get("concentration_method")
                    else None
                ),
                top_exposure_name=(
                    str(position.get("top_exposure_name"))
                    if position.get("top_exposure_name")
                    else None
                ),
            ),
            context=PortfolioContext(
                total_value=total_value,
                num_holdings=summary.get("num_holdings", 0) if summary else 0,
            ),
        )

    return PortfolioSection(
        held=False,
        context=PortfolioContext(
            total_value=(summary.get("total_value") or 0) if summary else 0,
            num_holdings=(summary.get("num_holdings") or 0) if summary else 0,
        )
        if summary
        else None,
    )


def build_strategies_section(strategies: dict[str, Any]) -> StrategiesSection | None:
    """Build the strategies section from strategies data."""
    strats = strategies.get("strategies")
    if not strats:
        return None

    best = strategies.get("best")

    return StrategiesSection(
        active_count=strategies["active_count"],
        strategies=[
            StrategyInfo(
                id=str(s["id"]),
                name=s["name"],
                strategy_type=s["strategy_type"],
                expected_sharpe=s.get("expected_sharpe"),
                live_sharpe=s.get("live_sharpe_ratio"),
                win_rate=s.get("live_win_rate"),
            )
            for s in strats[:3]
        ],
        best_strategy=StrategyInfo(
            id=str(best["id"]),
            name=best["name"],
            strategy_type=best["strategy_type"],
            expected_sharpe=best.get("expected_sharpe"),
            live_sharpe=best.get("live_sharpe_ratio"),
            win_rate=best.get("live_win_rate"),
        )
        if best
        else None,
    )


def build_market_section(market: dict[str, Any]) -> MarketSection | None:
    """Build the market section from market data."""
    if not market:
        return None

    fg = market.get("fear_greed") or {}
    return MarketSection(
        fear_greed_score=fg.get("score"),
        fear_greed_label=fg.get("label"),
        fear_greed_as_of_date=fg.get("as_of_date"),
        vix=_finite_float(market.get("vix")),
        vix_as_of_date=market.get("vix_as_of_date"),
        sp500_change=_finite_float(market.get("sp500_change")),
        sp500_as_of_date=market.get("sp500_as_of_date"),
    )
