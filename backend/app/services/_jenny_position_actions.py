"""Position action map builder and action logic for Jenny reviews."""

from __future__ import annotations

from typing import Any

from app.models.thesis import Thesis
from app.portfolio.analytics_returns import calculate_position_performances


def build_position_action_map(
    service: Any,
    review_map: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not review_map or not hasattr(service, "portfolio_mgr") or not hasattr(service, "price_fetcher"):
        return {}

    positions = [
        position
        for position in service.portfolio_mgr.get_positions()
        if position.position_type != "paper" and position.symbol in review_map
    ]
    if not positions:
        return {}

    price_data = service.price_fetcher.fetch_price_data([position.symbol for position in positions])
    performances = {
        performance.symbol: performance
        for performance in calculate_position_performances(positions, price_data)
    }

    action_map: dict[str, dict[str, Any]] = {}
    for position in positions:
        performance = performances.get(position.symbol)
        if performance is None:
            continue
        thesis = service.thesis_service.get_thesis(position.symbol)
        invalidation_triggers = (
            service.thesis_service.check_invalidation_triggers(position.symbol) if thesis else []
        )
        action_map[position.symbol] = get_position_action(
            symbol=position.symbol,
            gain_pct=performance.gain_pct,
            weight_pct=performance.weight_pct,
            thesis=thesis,
            invalidation_triggers=invalidation_triggers,
            aggregated_review=review_map[position.symbol],
        )
    return action_map


def get_position_action(
    *,
    symbol: str,
    gain_pct: float,
    weight_pct: float,
    thesis: Thesis | None,
    invalidation_triggers: list[str],
    aggregated_review: Any,
) -> dict[str, Any]:
    if invalidation_triggers:
        return {
            "action": "exit",
            "severity": "critical",
            "title": f"{symbol}: Exit this position",
            "detail": " ".join(invalidation_triggers),
            "recommendation": "Sell or reduce immediately unless you have a very specific reason to ignore the break.",
            "gain_pct": gain_pct,
            "weight_pct": weight_pct,
        }
    if aggregated_review.final_verdict == "exit":
        return {
            "action": "exit",
            "severity": "critical",
            "title": f"{symbol}: Exit this position",
            "detail": " ".join(aggregated_review.reasons)
            or f"Jenny thinks {symbol} should come out of the portfolio.",
            "recommendation": (
                aggregated_review.evaluations[0].recommendation
                if aggregated_review.evaluations
                else "Review why the trade no longer belongs in the portfolio."
            ),
            "gain_pct": gain_pct,
            "weight_pct": weight_pct,
        }
    if gain_pct >= 20 and weight_pct >= 15:
        return {
            "action": "trim",
            "severity": "warning",
            "title": f"{symbol}: Trim this position",
            "detail": f"{symbol} is up {gain_pct:.1f}% and now makes up {weight_pct:.1f}% of the portfolio.",
            "recommendation": "Take partial profits so one winner does not become oversized.",
            "gain_pct": gain_pct,
            "weight_pct": weight_pct,
        }
    if weight_pct >= 18:
        return {
            "action": "de_risk",
            "severity": "warning",
            "title": f"{symbol}: De-risk this position",
            "detail": f"{symbol} now represents {weight_pct:.1f}% of the portfolio, which is more concentration than Jenny wants for one idea.",
            "recommendation": "Scale it back to a size you can tolerate.",
            "gain_pct": gain_pct,
            "weight_pct": weight_pct,
        }
    if gain_pct <= -8 or aggregated_review.final_verdict == "review":
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
    return {
        "action": "hold",
        "severity": "info",
        "title": f"{symbol}: Hold steady",
        "detail": "Nothing in the current position data or thesis says you need to act right now.",
        "recommendation": "Do nothing unless new facts change the thesis.",
        "gain_pct": gain_pct,
        "weight_pct": weight_pct,
    }
