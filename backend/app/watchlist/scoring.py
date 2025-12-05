"""Watchlist scoring utilities for price and technical components."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..portfolio.models import PriceData
from ..services.catalyst_scoring import (
    aggregate_catalyst_scores,
    get_active_catalysts_for_symbol,
)
from .fundamentals import FundamentalData
from .models import (
    ScoreBreakdown,
    ScoreComponent,
    TechnicalSnapshot,
    WatchlistScoreInputs,
)

logger = get_logger(__name__)

PRICE_STALE_TTL_MINUTES = 15
TECHNICAL_STALE_TTL_MINUTES = 60


@dataclass
class PriceComponentInputs:
    price_data: PriceData
    change_pct: float | None
    now: datetime


def _is_stale(timestamp: datetime | None, ttl_minutes: int, now: datetime) -> bool:
    if timestamp is None:
        return True
    cutoff = now - timedelta(minutes=ttl_minutes)
    return timestamp < cutoff


def _score_from_change_percent(change_pct: float) -> float:
    """Map price change percent (-20% to +20%) into 0-100 range."""
    clamped = max(-20.0, min(20.0, change_pct))
    return (clamped + 20.0) / 40.0 * 100.0


def _score_from_rsi(rsi: float) -> float:
    """Reward balanced RSI; penalise overbought/oversold extremes."""
    clamped = max(0.0, min(100.0, rsi))
    distance = abs(clamped - 50.0)
    # Distance 0 => score 100, distance 50 => score 0
    return max(0.0, 100.0 - (distance * 2.0))


def _score_from_trend(
    price: float | None, sma_50: float | None, sma_200: float | None
) -> float | None:
    """Blend moving average crossover into a 0-100 score."""
    if price is None or sma_50 is None or sma_200 is None:
        return None

    # Positive spread if price > averages; clamp to [-20%, 20%]
    spread_short = (price - sma_50) / sma_50 if sma_50 else 0.0
    spread_long = (price - sma_200) / sma_200 if sma_200 else 0.0

    composite = (spread_short * 0.6) + (spread_long * 0.4)
    composite = max(-0.2, min(0.2, composite))

    return (composite + 0.2) / 0.4 * 100.0


def _compute_price_component(
    inputs: PriceComponentInputs, weight: float, stale_ttl_minutes: int = 15
) -> ScoreComponent:
    now = inputs.now
    price_data = inputs.price_data
    change_pct = inputs.change_pct

    cached_at = price_data.cached_at
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)

    stale = _is_stale(cached_at, stale_ttl_minutes, now)
    metadata: dict[str, Any] = {
        "source": price_data.source,
        "cached_at": cached_at.isoformat(),
    }

    if change_pct is None:
        metadata["reason"] = "missing_change_pct"
        return ScoreComponent(score=0.0, weight=weight, stale=True, metadata=metadata)

    score = _score_from_change_percent(change_pct)
    metadata["raw_change_pct"] = change_pct
    metadata["beta"] = price_data.beta
    metadata["volatility"] = price_data.volatility
    metadata["price"] = price_data.price

    return ScoreComponent(
        score=score,
        weight=weight,
        stale=stale,
        updated_at=cached_at,
        metadata=metadata,
    )


def _compute_technical_component(
    technical: TechnicalSnapshot,
    weight: float,
    now: datetime,
    stale_ttl_minutes: int = 15,
) -> ScoreComponent:
    if technical.calculated_at is None:
        stale = True
    else:
        stale = _is_stale(technical.calculated_at, stale_ttl_minutes, now)

    component_scores: list[float] = []
    metadata: dict[str, Any] = {}

    if technical.rsi_14 is not None:
        rsi_score = _score_from_rsi(technical.rsi_14)
        component_scores.append(rsi_score)
        metadata["rsi_14"] = technical.rsi_14

    trend_score = _score_from_trend(technical.price, technical.sma_50, technical.sma_200)
    if trend_score is not None:
        component_scores.append(trend_score)
        metadata["trend_score"] = trend_score

    if technical.macd is not None and technical.macd_signal is not None:
        delta = technical.macd - technical.macd_signal
        macd_score = max(-2.0, min(2.0, delta)) / 4.0 * 100.0 + 50.0
        component_scores.append(macd_score)
        metadata["macd"] = technical.macd
        metadata["macd_signal"] = technical.macd_signal

    if technical.price is not None:
        metadata["price"] = technical.price

    if not component_scores:
        metadata["reason"] = "missing_indicators"
        return ScoreComponent(
            score=0.0,
            weight=weight,
            stale=True,
            metadata=metadata,
        )

    score = sum(component_scores) / len(component_scores)

    return ScoreComponent(
        score=score,
        weight=weight,
        stale=stale,
        updated_at=technical.calculated_at,
        metadata=metadata,
    )


def _compute_fundamental_component(
    fundamental_data: FundamentalData | None,
    weight: float,
    now: datetime,
) -> ScoreComponent:
    """Compute fundamental score component from FundamentalData.

    Args:
        fundamental_data: FundamentalData object with calculated scores
        weight: Weight for this component (0.0-1.0)
        now: Current timestamp

    Returns:
        ScoreComponent with fundamental score and sub-scores
    """
    if not fundamental_data or not fundamental_data.fundamental_score:
        return ScoreComponent(
            score=0.0,
            weight=weight,
            stale=True,
            metadata={"reason": "missing_fundamental_data"},
            sub_scores={},
        )

    score = fundamental_data.fundamental_score

    # Sub-scores breakdown (4 pillars)
    sub_scores = {
        "valuation": fundamental_data.valuation_score or 0.0,
        "growth": fundamental_data.growth_score or 0.0,
        "health": fundamental_data.health_score or 0.0,
        "sentiment": fundamental_data.sentiment_score or 0.0,
    }

    metadata: dict[str, str | int | float | bool | None] = {
        "profit_margin": fundamental_data.profit_margin,
        "revenue_growth": fundamental_data.revenue_growth,
        "debt_to_equity": fundamental_data.debt_to_equity,
        "recommendation_mean": fundamental_data.recommendation_mean,
    }

    component = ScoreComponent(
        score=score,
        weight=weight,
        stale=False,  # Fundamental data cached for 24h
        metadata=metadata,
        sub_scores=sub_scores,
    )

    return component


def _compute_catalyst_component(
    symbol: str,
    news_articles: list[dict[str, str | datetime | float | None]],
    weight: float,
    now: datetime,
) -> ScoreComponent:
    """Compute catalyst score component from recent news events.

    Args:
        symbol: Stock symbol
        news_articles: List of news article dicts with headline, summary, published_at, filing_type
        weight: Weight for this component (0.0-1.0)
        now: Current timestamp

    Returns:
        ScoreComponent with catalyst score (0-100 scale, mapped from -5 to +5)
    """
    if not news_articles:
        return ScoreComponent(
            score=50.0,  # Neutral score when no news
            weight=weight,
            stale=False,
            metadata={"reason": "no_news_articles", "catalyst_count": 0},
            sub_scores={},
        )

    try:
        # Get active catalysts (non-expired events)
        active_catalysts = get_active_catalysts_for_symbol(
            symbol=symbol,
            news_articles=news_articles,
            current_date=now,
        )

        if not active_catalysts:
            return ScoreComponent(
                score=50.0,  # Neutral score when no active catalysts
                weight=weight,
                stale=False,
                metadata={"reason": "no_active_catalysts", "catalyst_count": 0},
                sub_scores={},
            )

        # Aggregate catalyst scores (-5 to +5 range)
        catalyst_impact = aggregate_catalyst_scores(active_catalysts)

        # Map -5 to +5 range to 0-100 scale
        # -5 => 0, 0 => 50, +5 => 100
        score = (catalyst_impact + 5.0) / 10.0 * 100.0
        score = max(0.0, min(100.0, score))

        # Extract sub-scores for top 3 catalysts
        sub_scores = {}
        for i, catalyst in enumerate(active_catalysts[:3], 1):
            sub_scores[f"catalyst_{i}"] = catalyst.score

        metadata: dict[str, str | int | float | bool | None] = {
            "catalyst_count": len(active_catalysts),
            "raw_impact": catalyst_impact,
            "top_category": active_catalysts[0].event_category if active_catalysts else None,
            "top_score": active_catalysts[0].score if active_catalysts else None,
        }

        return ScoreComponent(
            score=score,
            weight=weight,
            stale=False,
            metadata=metadata,
            sub_scores=sub_scores,
        )

    except Exception as e:
        logger.error(
            "catalyst_scoring_error",
            symbol=symbol,
            error=str(e),
            exc_info=True,
        )
        return ScoreComponent(
            score=50.0,  # Neutral score on error
            weight=weight,
            stale=True,
            metadata={"reason": "error", "error": str(e)},
            sub_scores={},
        )


def calculate_watchlist_scores(inputs: WatchlistScoreInputs) -> ScoreBreakdown:
    """Compute watchlist price/technical/fundamental/catalyst scores and overall composite (4-pillar)."""
    # Ensure timestamps are timezone-aware
    now = inputs.now if inputs.now.tzinfo is not None else inputs.now.replace(tzinfo=UTC)

    weights = inputs.weights.normalized()

    # Price component (with sub-scores)
    price_component = _compute_price_component(
        PriceComponentInputs(
            price_data=inputs.price,
            change_pct=inputs.price_change_pct,
            now=now,
        ),
        weight=weights["price"],
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )
    price_component.sub_scores = {"change_pct": price_component.score}

    # Technical component (with sub-scores)
    technical_component = _compute_technical_component(
        inputs.technical,
        weight=weights["technical"],
        now=now,
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )

    # Extract technical sub-scores from metadata
    rsi_val = technical_component.metadata.get("rsi_14", 0.0)
    trend_val = technical_component.metadata.get("trend_score", 0.0)
    macd_val = technical_component.metadata.get("macd", 0.0)
    technical_component.sub_scores = {
        "rsi_14": float(rsi_val) if isinstance(rsi_val, (int, float)) else 0.0,
        "trend": float(trend_val) if isinstance(trend_val, (int, float)) else 0.0,
        "macd": float(macd_val) if isinstance(macd_val, (int, float)) and macd_val else 0.0,
    }

    # Fundamental component (if available)
    fundamental_component = None
    if hasattr(inputs, "fundamental") and inputs.fundamental:
        fundamental_component = _compute_fundamental_component(
            inputs.fundamental,
            weight=weights["fundamental"],
            now=now,
        )

    # Catalyst component (if news articles available)
    catalyst_component = None
    if hasattr(inputs, "news_articles") and inputs.news_articles:
        catalyst_component = _compute_catalyst_component(
            symbol=inputs.price.symbol,
            news_articles=inputs.news_articles,
            weight=weights.get("catalyst", 0.0),
            now=now,
        )

    # Calculate overall score based on available components
    components_used = [
        (price_component, weights["price"], True),
        (technical_component, weights["technical"], True),
        (fundamental_component, weights.get("fundamental", 0.0), fundamental_component and not fundamental_component.stale),
        (catalyst_component, weights.get("catalyst", 0.0), catalyst_component is not None),
    ]

    # Filter to only active components
    active_components = [(comp, weight) for comp, weight, is_active in components_used if is_active and comp]

    if active_components:
        # Renormalize weights for active components only
        total_weight = sum(weight for _, weight in active_components)
        if total_weight > 0:
            overall = sum(
                comp.score * (weight / total_weight)
                for comp, weight in active_components
            )
        else:
            # Fallback: equal weights if all weights are 0
            overall = sum(comp.score for comp, _ in active_components) / len(active_components)
    else:
        # Fallback to 2-pillar (price + technical)
        price_weight = weights["price"] / (weights["price"] + weights["technical"])
        technical_weight = weights["technical"] / (weights["price"] + weights["technical"])
        overall = (
            price_component.score * price_weight + technical_component.score * technical_weight
        )

    breakdown = ScoreBreakdown(
        price=price_component,
        technical=technical_component,
        fundamental=fundamental_component,
        catalyst=catalyst_component,
        overall=overall,
    )

    logger.info(
        "watchlist_scores_computed",
        symbol=inputs.price.symbol,
        overall=breakdown.overall,
        price_score=breakdown.price.score,
        technical_score=breakdown.technical.score,
        fundamental_score=breakdown.fundamental.score if breakdown.fundamental else None,
        catalyst_score=breakdown.catalyst.score if breakdown.catalyst else None,
    )

    return breakdown
