"""Watchlist scoring utilities for price and technical components."""

from __future__ import annotations

from ..logging_config import get_logger
from ._scoring_helpers import (
    build_optional_components,
    build_price_component,
    build_technical_component,
    compute_overall_score,
    ensure_timezone_aware,
    select_active_components,
)
from .models import ScoreBreakdown, WatchlistScoreInputs

logger = get_logger(__name__)

# Legacy exports for backward compatibility
PRICE_STALE_TTL_MINUTES = 15
TECHNICAL_STALE_TTL_MINUTES = 60


def calculate_watchlist_scores(inputs: WatchlistScoreInputs) -> ScoreBreakdown:
    """Compute watchlist scores across 6 pillars.

    Pillars: price, technical, fundamental, catalyst, options flow, performance.

    Args:
        inputs: All required scoring inputs (price, technical, fundamental, etc.)

    Returns:
        ScoreBreakdown with all component scores and overall weighted score
    """
    now = ensure_timezone_aware(inputs.now)
    weights = inputs.weights.normalized()

    price_component = build_price_component(inputs, weights, now)
    technical_component = build_technical_component(inputs, weights, now)
    fundamental, catalyst, options_flow, performance_factor = build_optional_components(
        inputs, weights, now
    )

    active = select_active_components(
        price_component, technical_component, fundamental, catalyst, options_flow, performance_factor, weights
    )
    overall = compute_overall_score(active, price_component, technical_component, weights)

    breakdown = ScoreBreakdown(
        price=price_component,
        technical=technical_component,
        fundamental=fundamental,
        catalyst=catalyst,
        options_flow=options_flow,
        performance_factor=performance_factor,
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
        performance_factor_score=breakdown.performance_factor.score if breakdown.performance_factor else None,
    )

    return breakdown
