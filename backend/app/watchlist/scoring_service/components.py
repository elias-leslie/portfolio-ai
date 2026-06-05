"""Individual score component calculators for watchlist scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ...logging_config import get_logger
from ...portfolio.models import PriceData
from ...services.catalyst_scoring import (
    aggregate_catalyst_scores,
    get_active_catalysts_for_symbol,
)
from ...services.options_flow_service import OptionsFlowData
from ..fundamentals import FundamentalData
from ..models import ScoreComponent, TechnicalSnapshot
from .helpers import (
    is_stale,
    score_from_change_percent,
    score_from_rsi,
    score_from_trend,
    score_from_vwap_distance,
)

logger = get_logger(__name__)


@dataclass
class PriceComponentInputs:
    """Inputs for price component calculation."""

    price_data: PriceData
    change_pct: float | None
    now: datetime


def compute_price_component(
    inputs: PriceComponentInputs, weight: float, stale_ttl_minutes: int = 15
) -> ScoreComponent:
    """Compute price momentum score component.

    Args:
        inputs: Price component input data
        weight: Weight for this component (0.0-1.0)
        stale_ttl_minutes: Staleness threshold in minutes

    Returns:
        ScoreComponent with price momentum score
    """
    now = inputs.now
    price_data = inputs.price_data
    change_pct = inputs.change_pct

    cached_at = price_data.cached_at
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)

    stale = is_stale(cached_at, stale_ttl_minutes, now)
    metadata: dict[str, Any] = {
        "source": price_data.source,
        "cached_at": cached_at.isoformat(),
    }

    if change_pct is None:
        metadata["reason"] = "missing_change_pct"
        return ScoreComponent(score=0.0, weight=weight, stale=True, metadata=metadata)

    score = score_from_change_percent(change_pct)
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


def compute_technical_component(
    technical: TechnicalSnapshot,
    weight: float,
    now: datetime,
    stale_ttl_minutes: int = 15,
) -> ScoreComponent:
    """Compute technical indicators score component.

    Args:
        technical: Technical snapshot data
        weight: Weight for this component (0.0-1.0)
        now: Current timestamp
        stale_ttl_minutes: Staleness threshold in minutes

    Returns:
        ScoreComponent with aggregated technical score
    """
    if technical.calculated_at is None:
        stale = True
    else:
        stale = is_stale(technical.calculated_at, stale_ttl_minutes, now)

    component_scores: list[float] = []
    metadata: dict[str, Any] = {}

    if technical.rsi_14 is not None:
        rsi_score = score_from_rsi(technical.rsi_14)
        component_scores.append(rsi_score)
        metadata["rsi_14"] = technical.rsi_14
        metadata["rsi_score"] = rsi_score

    trend_score = score_from_trend(technical.price, technical.sma_50, technical.sma_200)
    if trend_score is not None:
        component_scores.append(trend_score)
        metadata["trend_score"] = trend_score

    if technical.macd is not None and technical.macd_signal is not None:
        delta = technical.macd - technical.macd_signal
        macd_score = max(-2.0, min(2.0, delta)) / 4.0 * 100.0 + 50.0
        component_scores.append(macd_score)
        metadata["macd"] = technical.macd
        metadata["macd_signal"] = technical.macd_signal
        metadata["macd_score"] = macd_score

    if technical.price is not None and technical.vwap is not None and technical.vwap > 0:
        vwap_distance_pct = ((technical.price - technical.vwap) / technical.vwap) * 100.0
        vwap_score = score_from_vwap_distance(vwap_distance_pct)
        component_scores.append(vwap_score)
        metadata["vwap"] = technical.vwap
        metadata["vwap_date"] = technical.vwap_date.isoformat() if technical.vwap_date else None
        metadata["vwap_distance_pct"] = vwap_distance_pct
        metadata["vwap_score"] = vwap_score
    elif technical.price is not None and component_scores:
        component_scores.append(0.0)
        metadata["vwap_missing"] = True
        metadata["vwap_score"] = 0.0

    if technical.price is not None:
        metadata["price"] = technical.price

    # Bollinger Bands data for UI display
    if technical.bb_upper is not None:
        metadata["bb_upper"] = technical.bb_upper
    if technical.bb_middle is not None:
        metadata["bb_middle"] = technical.bb_middle
    if technical.bb_lower is not None:
        metadata["bb_lower"] = technical.bb_lower

    # Stochastic Oscillator data for UI display
    if technical.stoch_k is not None:
        metadata["stoch_k"] = technical.stoch_k
    if technical.stoch_d is not None:
        metadata["stoch_d"] = technical.stoch_d

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


def compute_fundamental_component(
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


def compute_catalyst_component(
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
        # Filter out None values to ensure dict[str, float] contract
        sub_scores = {}
        for i, catalyst in enumerate(active_catalysts[:3], 1):
            if catalyst.score is not None:
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


def compute_options_flow_component(
    options_data: OptionsFlowData | None,
    symbol_in_active_sector: bool,
    weight: float,
) -> ScoreComponent:
    """Compute options flow score component (GAP-031).

    Scoring (0-100 scale):
    - Base: 50 (neutral)
    - Call % > 55%: Add points (bullish sentiment)
    - Call % < 45%: Subtract points (bearish sentiment)
    - Symbol in active sector: Bonus points

    Args:
        options_data: Latest options flow metrics
        symbol_in_active_sector: Whether symbol's sector has high options activity
        weight: Weight for this component (0.0-1.0)

    Returns:
        ScoreComponent with options flow score
    """
    if options_data is None or options_data.is_stale:
        return ScoreComponent(
            score=50.0,  # Neutral when no data
            weight=weight,
            stale=True,
            metadata={"reason": "no_data" if options_data is None else "stale_data"},
            sub_scores={},
        )

    call_pct = options_data.call_pct

    # Base score: 50 (neutral)
    # Map call_pct from 0.0-1.0 to 0-100 range
    # 0.45 (45%) = 40, 0.50 (50%) = 50, 0.55 (55%) = 60, 0.60 (60%) = 70
    # Linear mapping: score = (call_pct - 0.5) * 200 + 50
    # This gives: 45% -> 40, 50% -> 50, 55% -> 60, 60% -> 70
    base_score = (call_pct - 0.5) * 200 + 50

    # Sector activity bonus: +5 if symbol's sector is highly active
    sector_bonus = 5.0 if symbol_in_active_sector else 0.0

    score = base_score + sector_bonus
    score = max(0.0, min(100.0, score))

    # Sub-scores for breakdown
    sub_scores = {
        "call_sentiment": base_score,
        "sector_bonus": sector_bonus,
    }

    metadata: dict[str, str | int | float | bool | None] = {
        "call_pct": call_pct,
        "near_term_pct": options_data.near_term_pct,
        "concentration_pct": options_data.concentration_pct,
        "symbol_in_active_sector": symbol_in_active_sector,
        "as_of_date": str(options_data.as_of_date) if options_data.as_of_date else None,
    }

    return ScoreComponent(
        score=score,
        weight=weight,
        stale=False,
        metadata=metadata,
        sub_scores=sub_scores,
    )


def compute_performance_factor_component(
    strategy_sharpe: float | None,
    weight: float,
) -> ScoreComponent | None:
    """Compute performance_factor pillar based on active strategy's 30-day Sharpe (auto-002).

    Score formula: min(strategy_sharpe / 2.0, 1.0) * 100
    - Sharpe 0.0 → score 0
    - Sharpe 1.0 → score 50
    - Sharpe 2.0+ → score 100

    Args:
        strategy_sharpe: 30-day rolling Sharpe ratio from active strategy (None = no strategy)
        weight: Weight for this component (0.0-1.0)

    Returns:
        ScoreComponent with performance factor score, or None if no strategy exists
    """
    if strategy_sharpe is None:
        # No strategy for this symbol - return None (pillar excluded from overall calc)
        return None

    # Score formula: min(sharpe / 2.0, 1.0) * 100
    # This maps Sharpe 0.0-2.0 to score 0-100
    normalized_sharpe = max(0.0, min(strategy_sharpe / 2.0, 1.0))
    score = normalized_sharpe * 100.0

    # Sub-scores for breakdown
    sub_scores = {
        "sharpe_30d": round(strategy_sharpe, 3),
    }

    metadata: dict[str, str | int | float | bool | None] = {
        "strategy_sharpe": round(strategy_sharpe, 3),
        "formula": "min(sharpe / 2.0, 1.0) * 100",
    }

    return ScoreComponent(
        score=score,
        weight=weight,
        stale=False,
        metadata=metadata,
        sub_scores=sub_scores,
    )
