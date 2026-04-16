"""Position action map builder and action logic for Jenny reviews."""

from __future__ import annotations

from typing import Any

from app.models.thesis import Thesis
from app.portfolio.analytics_returns import calculate_position_performances
from app.portfolio.fund_lookthrough import get_fund_lookthroughs

# Scoring thresholds for position action determination
TRIM_GAIN_THRESHOLD = 20  # % gain for trim action
TRIM_WEIGHT_THRESHOLD = 15  # % portfolio weight threshold for trim
DERISK_WEIGHT_THRESHOLD = 18  # % portfolio weight threshold for de-risk
REVIEW_LOSS_THRESHOLD = -8  # % loss threshold for review action


def build_position_action_map(
    service: Any,
    review_map: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not review_map or not hasattr(service, "portfolio_mgr") or not hasattr(service, "price_fetcher"):
        return {}

    all_live_positions = [
        position
        for position in service.portfolio_mgr.get_positions()
        if position.position_type != "paper"
    ]
    positions = [position for position in all_live_positions if position.symbol in review_map]
    if not positions:
        return {}

    price_data = service.price_fetcher.fetch_price_data(
        [position.symbol for position in all_live_positions]
    )
    performances = {
        performance.symbol: performance
        for performance in calculate_position_performances(all_live_positions, price_data)
    }
    explicit_storage = getattr(service, "__dict__", {}).get("storage")
    fund_profiles = get_fund_lookthroughs(
        [position.symbol for position in positions],
        explicit_storage,
    )

    action_map: dict[str, dict[str, Any]] = {}
    for position in positions:
        performance = performances.get(position.symbol)
        if performance is None:
            continue
        lookthrough_profile = fund_profiles.get(position.symbol.upper())
        risk_weight_pct = performance.weight_pct
        if lookthrough_profile is not None and performance.weight_pct is not None:
            max_single_name_weight = max(
                (holding.weight for holding in lookthrough_profile.top_holdings),
                default=0.0,
            )
            if max_single_name_weight > 0:
                risk_weight_pct = performance.weight_pct * max_single_name_weight
        thesis = service.thesis_service.get_thesis(position.symbol)
        invalidation_triggers = (
            service.thesis_service.check_invalidation_triggers(position.symbol) if thesis else []
        )
        action_map[position.symbol] = get_position_action(
            symbol=position.symbol,
            gain_pct=performance.gain_pct,
            weight_pct=performance.weight_pct,
            concentration_weight_pct=risk_weight_pct,
            thesis=thesis,
            invalidation_triggers=invalidation_triggers,
            aggregated_review=review_map[position.symbol],
        )
    return action_map


def _build_exit_action(
    symbol: str,
    gain_pct: float,
    weight_pct: float,
    detail: str,
    recommendation: str,
) -> dict[str, Any]:
    """Build an exit action response."""
    return {
        "action": "exit",
        "severity": "critical",
        "title": f"{symbol}: Exit this position",
        "detail": detail,
        "recommendation": recommendation,
        "gain_pct": gain_pct,
        "weight_pct": weight_pct,
    }


def _build_trim_action(
    symbol: str,
    gain_pct: float,
    weight_pct: float,
    concentration_weight_pct: float,
) -> dict[str, Any]:
    """Build a trim action response."""
    detail = (
        f"{symbol} is up {gain_pct:.1f}% and now makes up {weight_pct:.1f}% of the portfolio."
        if abs(concentration_weight_pct - weight_pct) < 0.05
        else f"{symbol} is up {gain_pct:.1f}% and now makes up {weight_pct:.1f}% of the portfolio; top look-through exposure is about {concentration_weight_pct:.1f}%."
    )
    return {
        "action": "trim",
        "severity": "warning",
        "title": f"{symbol}: Trim this position",
        "detail": detail,
        "recommendation": "Take partial profits so one winner does not become oversized.",
        "gain_pct": gain_pct,
        "weight_pct": weight_pct,
    }


def _build_derisk_action(
    symbol: str,
    gain_pct: float,
    weight_pct: float,
    concentration_weight_pct: float,
) -> dict[str, Any]:
    """Build a de-risk action response."""
    detail = (
        f"{symbol} now represents {weight_pct:.1f}% of the portfolio, which is more concentration than Jenny wants for one idea."
        if abs(concentration_weight_pct - weight_pct) < 0.05
        else f"{symbol} is {weight_pct:.1f}% of the portfolio, but its largest look-through exposure is about {concentration_weight_pct:.1f}%."
    )
    return {
        "action": "de_risk",
        "severity": "warning",
        "title": f"{symbol}: De-risk this position",
        "detail": detail,
        "recommendation": "Scale it back to a size you can tolerate.",
        "gain_pct": gain_pct,
        "weight_pct": weight_pct,
    }


def _build_review_action(
    symbol: str,
    gain_pct: float,
    weight_pct: float,
    thesis: Thesis | None,
) -> dict[str, Any]:
    """Build a review action response."""
    thesis_hint = "The thesis is missing." if thesis is None else "The thesis needs a fresh check."
    return {
        "action": "review",
        "severity": "warning",
        "title": f"{symbol}: Recheck this position",
        "detail": f"{symbol} is down {abs(gain_pct):.1f}% from cost basis. {thesis_hint}",
        "recommendation": "Review the thesis before adding or deciding to hold through more weakness.",
        "gain_pct": gain_pct,
        "weight_pct": weight_pct,
    }


def _build_hold_action(
    symbol: str,
    gain_pct: float,
    weight_pct: float,
) -> dict[str, Any]:
    """Build a hold action response."""
    return {
        "action": "hold",
        "severity": "info",
        "title": f"{symbol}: Hold steady",
        "detail": "Nothing in the current position data or thesis says you need to act right now.",
        "recommendation": "Do nothing unless new facts change the thesis.",
        "gain_pct": gain_pct,
        "weight_pct": weight_pct,
    }


def get_position_action(
    *,
    symbol: str,
    gain_pct: float,
    weight_pct: float,
    concentration_weight_pct: float | None = None,
    thesis: Thesis | None,
    invalidation_triggers: list[str],
    aggregated_review: Any,
) -> dict[str, Any]:
    """Determine position action based on performance and thesis metrics."""
    effective_concentration_weight = (
        concentration_weight_pct if concentration_weight_pct is not None else weight_pct
    )
    if invalidation_triggers:
        return _build_exit_action(
            symbol,
            gain_pct,
            weight_pct,
            " ".join(invalidation_triggers),
            "Sell or reduce immediately unless you have a very specific reason to ignore the break.",
        )
    if aggregated_review.final_verdict == "exit":
        return _build_exit_action(
            symbol,
            gain_pct,
            weight_pct,
            " ".join(aggregated_review.reasons)
            or f"Jenny thinks {symbol} should come out of the portfolio.",
            (
                aggregated_review.evaluations[0].recommendation
                if aggregated_review.evaluations
                else "Review why the trade no longer belongs in the portfolio."
            ),
        )
    if gain_pct >= TRIM_GAIN_THRESHOLD and effective_concentration_weight >= TRIM_WEIGHT_THRESHOLD:
        return _build_trim_action(
            symbol,
            gain_pct,
            weight_pct,
            effective_concentration_weight,
        )
    if effective_concentration_weight >= DERISK_WEIGHT_THRESHOLD:
        return _build_derisk_action(
            symbol,
            gain_pct,
            weight_pct,
            effective_concentration_weight,
        )
    if gain_pct <= REVIEW_LOSS_THRESHOLD:
        return _build_review_action(symbol, gain_pct, weight_pct, thesis)
    return _build_hold_action(symbol, gain_pct, weight_pct)
