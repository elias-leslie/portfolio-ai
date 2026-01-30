"""Watchlist scoring utilities for price and technical components."""

from __future__ import annotations

from datetime import UTC

from ..logging_config import get_logger
from .models import ScoreBreakdown, WatchlistScoreInputs
from .scoring_service.components import (
    PriceComponentInputs,
    compute_catalyst_component,
    compute_fundamental_component,
    compute_options_flow_component,
    compute_performance_factor_component,
    compute_price_component,
    compute_technical_component,
)

logger = get_logger(__name__)

# Legacy exports for backward compatibility
PRICE_STALE_TTL_MINUTES = 15
TECHNICAL_STALE_TTL_MINUTES = 60


def calculate_watchlist_scores(inputs: WatchlistScoreInputs) -> ScoreBreakdown:
    """Compute watchlist price/technical/fundamental/catalyst/options_flow/performance scores (6-pillar).

    Args:
        inputs: All required scoring inputs (price, technical, fundamental, etc.)

    Returns:
        ScoreBreakdown with all component scores and overall weighted score
    """
    # Ensure timestamps are timezone-aware
    now = inputs.now if inputs.now.tzinfo is not None else inputs.now.replace(tzinfo=UTC)

    weights = inputs.weights.normalized()

    # Price component (with sub-scores)
    price_component = compute_price_component(
        PriceComponentInputs(
            price_data=inputs.price,
            change_pct=inputs.price_change_pct,
            now=now,
        ),
        weight=weights["price"],
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )
    price_component.sub_scores = {"change_pct": price_component.score}

    # Add RVOL to price metadata if available (FEAT-130)
    if inputs.volume_relative is not None:
        price_component.metadata["rvol"] = round(inputs.volume_relative, 2)

    # Technical component (with sub-scores)
    technical_component = compute_technical_component(
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
        fundamental_component = compute_fundamental_component(
            inputs.fundamental,
            weight=weights["fundamental"],
            now=now,
        )

    # Catalyst component (if news articles available)
    catalyst_component = None
    if hasattr(inputs, "news_articles") and inputs.news_articles:
        catalyst_component = compute_catalyst_component(
            symbol=inputs.price.symbol,
            news_articles=inputs.news_articles,
            weight=weights.get("catalyst", 0.0),
            now=now,
        )

    # Options flow component (GAP-031)
    options_flow_component = None
    if hasattr(inputs, "options_data"):
        symbol_in_active_sector = getattr(inputs, "symbol_in_active_sector", False) or False
        options_flow_component = compute_options_flow_component(
            options_data=inputs.options_data,
            symbol_in_active_sector=symbol_in_active_sector,
            weight=weights.get("options_flow", 0.08),  # Default 8% weight
        )

    # Performance factor component (auto-002)
    performance_factor_component = None
    if hasattr(inputs, "strategy_sharpe") and inputs.strategy_sharpe is not None:
        performance_factor_component = compute_performance_factor_component(
            strategy_sharpe=inputs.strategy_sharpe,
            weight=weights.get("performance_factor", 0.05),  # Default 5% weight
        )

    # Calculate overall score based on available components
    components_used = [
        (price_component, weights["price"], True),
        (technical_component, weights["technical"], True),
        (
            fundamental_component,
            weights.get("fundamental", 0.0),
            fundamental_component and not fundamental_component.stale,
        ),
        (catalyst_component, weights.get("catalyst", 0.0), catalyst_component is not None),
        (
            options_flow_component,
            weights.get("options_flow", 0.0),
            options_flow_component is not None and not options_flow_component.stale,
        ),
        (
            performance_factor_component,
            weights.get("performance_factor", 0.0),
            performance_factor_component is not None,
        ),
    ]

    # Filter to only active components
    active_components = [
        (comp, weight) for comp, weight, is_active in components_used if is_active and comp
    ]

    if active_components:
        # Renormalize weights for active components only
        total_weight = sum(weight for _, weight in active_components)
        if total_weight > 0:
            overall = sum(
                comp.score * (weight / total_weight) for comp, weight in active_components
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
        options_flow=options_flow_component,
        performance_factor=performance_factor_component,
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
        options_flow_score=breakdown.options_flow.score if breakdown.options_flow else None,
        performance_factor_score=breakdown.performance_factor.score
        if breakdown.performance_factor
        else None,
    )

    return breakdown
