"""Private helper functions for watchlist scoring."""

from __future__ import annotations

from datetime import UTC, datetime

from .models import ScoreComponent, WatchlistScoreInputs
from .scoring_service.components import (
    PriceComponentInputs,
    compute_catalyst_component,
    compute_fundamental_component,
    compute_options_flow_component,
    compute_performance_factor_component,
    compute_price_component,
    compute_technical_component,
)


def ensure_timezone_aware(now: datetime) -> datetime:
    """Return timezone-aware datetime, defaulting to UTC if naive."""
    return now if now.tzinfo is not None else now.replace(tzinfo=UTC)


def build_price_component(
    inputs: WatchlistScoreInputs, weights: dict[str, float], now: datetime
) -> ScoreComponent:
    """Build price component with sub-scores and optional RVOL metadata."""
    component = compute_price_component(
        PriceComponentInputs(price_data=inputs.price, change_pct=inputs.price_change_pct, now=now),
        weight=weights["price"],
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )
    component.sub_scores = {"change_pct": component.score}
    if inputs.volume_relative is not None:
        component.metadata["rvol"] = round(inputs.volume_relative, 2)
    return component


def build_technical_component(
    inputs: WatchlistScoreInputs, weights: dict[str, float], now: datetime
) -> ScoreComponent:
    """Build technical component with RSI, trend, and MACD sub-scores."""
    component = compute_technical_component(
        inputs.technical,
        weight=weights["technical"],
        now=now,
        stale_ttl_minutes=inputs.stale_ttl_minutes,
    )
    meta = component.metadata
    component.sub_scores = {
        "rsi_14": float(meta.get("rsi_14", 0.0)) if isinstance(meta.get("rsi_14", 0.0), (int, float)) else 0.0,
        "trend": float(meta.get("trend_score", 0.0)) if isinstance(meta.get("trend_score", 0.0), (int, float)) else 0.0,
        "macd": float(meta.get("macd", 0.0)) if isinstance(meta.get("macd", 0.0), (int, float)) and meta.get("macd") else 0.0,
    }
    return component


def build_optional_components(
    inputs: WatchlistScoreInputs, weights: dict[str, float], now: datetime
) -> tuple[ScoreComponent | None, ScoreComponent | None, ScoreComponent | None, ScoreComponent | None]:
    """Build optional fundamental, catalyst, options flow, and performance components."""
    fundamental = (
        compute_fundamental_component(inputs.fundamental, weight=weights["fundamental"], now=now)
        if getattr(inputs, "fundamental", None)
        else None
    )
    catalyst = (
        compute_catalyst_component(
            symbol=inputs.price.symbol,
            news_articles=inputs.news_articles,
            weight=weights.get("catalyst", 0.0),
            now=now,
        )
        if getattr(inputs, "news_articles", None)
        else None
    )
    options_flow = (
        compute_options_flow_component(
            options_data=inputs.options_data,
            symbol_in_active_sector=getattr(inputs, "symbol_in_active_sector", False) or False,
            weight=weights.get("options_flow", 0.08),
        )
        if hasattr(inputs, "options_data")
        else None
    )
    performance_factor = (
        compute_performance_factor_component(
            strategy_sharpe=inputs.strategy_sharpe,
            weight=weights.get("performance_factor", 0.05),
        )
        if getattr(inputs, "strategy_sharpe", None) is not None
        else None
    )
    return fundamental, catalyst, options_flow, performance_factor


def select_active_components(
    price_component: ScoreComponent,
    technical_component: ScoreComponent,
    fundamental: ScoreComponent | None,
    catalyst: ScoreComponent | None,
    options_flow: ScoreComponent | None,
    performance_factor: ScoreComponent | None,
    weights: dict[str, float],
) -> list[tuple[ScoreComponent, float]]:
    """Return the list of (component, weight) pairs that are active and non-stale."""
    candidates: list[tuple[ScoreComponent | None, float, bool]] = [
        (price_component, weights["price"], True),
        (technical_component, weights["technical"], True),
        (fundamental, weights.get("fundamental", 0.0), fundamental is not None and not fundamental.stale),
        (catalyst, weights.get("catalyst", 0.0), catalyst is not None),
        (options_flow, weights.get("options_flow", 0.0), options_flow is not None and not options_flow.stale),
        (performance_factor, weights.get("performance_factor", 0.0), performance_factor is not None),
    ]
    return [(comp, w) for comp, w, active in candidates if active and comp]


def compute_overall_score(
    active_components: list[tuple[ScoreComponent, float]],
    price_component: ScoreComponent,
    technical_component: ScoreComponent,
    weights: dict[str, float],
) -> float:
    """Compute weighted overall score; falls back to 2-pillar when no active components."""
    if not active_components:
        total = weights["price"] + weights["technical"]
        return (
            price_component.score * weights["price"] / total
            + technical_component.score * weights["technical"] / total
        )
    total_weight = sum(w for _, w in active_components)
    if total_weight > 0:
        return sum(comp.score * w / total_weight for comp, w in active_components)
    return sum(comp.score for comp, _ in active_components) / len(active_components)
