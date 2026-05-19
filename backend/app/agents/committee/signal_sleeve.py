"""Multi-factor signal sleeve for committee Tier-1 scoring."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class SignalSleeve:
    score_adjustment: float
    top_factor: str
    factors: dict[str, float]
    gates: dict[str, str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": "signal-sleeve-v1",
            "score_adjustment": self.score_adjustment,
            "top_factor": self.top_factor,
            "factors": self.factors,
            "gates": self.gates,
        }


def build_signal_sleeve(
    *,
    scanner_factors: dict[str, Any],
    context_bundle: dict[str, Any] | None = None,
) -> SignalSleeve:
    """Build additive signal overlay from scanner + context inputs."""
    context_bundle = context_bundle or {}
    momentum = _pct_score(scanner_factors.get("mom_xover_pct"))
    trend = _first_score(
        scanner_factors.get("rs_vs_spy_pct"),
        context_bundle.get("technical_pillar"),
    )
    volume = _pct_score(scanner_factors.get("vol_surge_pct"))
    session = _session_score(context_bundle)
    leadership = _leadership_score(context_bundle)
    oil = _oil_score(context_bundle)
    gating = _gating_score(context_bundle)
    factors = {
        "momentum_crossover": momentum,
        "trend_strength": trend,
        "volume_confirmation": volume,
        "sessions": session,
        "leadership": leadership,
        "oil": oil,
        "gating": gating,
    }
    core = 0.4 * momentum + 0.3 * trend + 0.2 * volume + 0.1 * leadership
    overlay = 0.05 * session + 0.05 * oil + 0.1 * gating
    adjustment = _clamp(0.25 * (core + overlay), -0.25, 0.25)
    return SignalSleeve(
        score_adjustment=adjustment,
        top_factor=_top_factor(factors),
        factors=factors,
        gates={
            "sessions": _gate_label(session),
            "leadership": _gate_label(leadership),
            "oil": _gate_label(oil),
            "gating": _gate_label(gating),
        },
    )


def apply_signal_sleeve(base_score: float, sleeve: SignalSleeve) -> float:
    return _clamp(base_score + sleeve.score_adjustment, -1.0, 1.0)


def _pct_score(value: Any) -> float:
    number = _float(value)
    if number is None:
        return 0.0
    return _clamp((number - 50.0) / 50.0, -1.0, 1.0)


def _first_score(*values: Any) -> float:
    for value in values:
        if isinstance(value, dict):
            for key in ("score", "value", "pct"):
                if key in value:
                    score = _pct_score(value[key]) if key == "pct" else _unit_score(value[key])
                    if score != 0.0:
                        return score
        score = _pct_score(value)
        if score != 0.0:
            return score
    return 0.0


def _unit_score(value: Any) -> float:
    number = _float(value)
    if number is None:
        return 0.0
    if -1.0 <= number <= 1.0:
        return number
    return _pct_score(number)


def _percent_change_score(value: Any) -> float:
    number = _float(value)
    if number is None:
        return 0.0
    return _clamp(number / 100.0, -1.0, 1.0)


def _session_score(context: dict[str, Any]) -> float:
    sleeve = _cluster(context, "overnight_premarket_afterhours_futures_news")
    return _percent_change_score(sleeve.get("spy_gap_proxy_pct"))


def _leadership_score(context: dict[str, Any]) -> float:
    sleeve = _cluster(context, "mag7_sector_leadership")
    return _percent_change_score(sleeve.get("average_change_pct"))


def _oil_score(context: dict[str, Any]) -> float:
    sleeve = _cluster(context, "oil_shock_overlay")
    gate_state = str(sleeve.get("gate_state") or "").lower()
    change = abs(_percent_change_score(sleeve.get("daily_change_pct")))
    return -change if gate_state == "active" else 0.0


def _gating_score(context: dict[str, Any]) -> float:
    sleeve = _cluster(context, "holiday_turn_of_month")
    return 0.25 if str(sleeve.get("gate_state") or "").lower() == "active" else 0.0


def _cluster(context: dict[str, Any], key: str) -> dict[str, Any]:
    source_snapshot = context.get("source_snapshot") if isinstance(context.get("source_snapshot"), dict) else {}
    clusters = source_snapshot.get("clusters") if isinstance(source_snapshot.get("clusters"), dict) else {}
    value = clusters.get(key) if isinstance(clusters, dict) else None
    return value if isinstance(value, dict) else {}


def _top_factor(factors: dict[str, float]) -> str:
    key, value = max(factors.items(), key=lambda item: abs(item[1]))
    if abs(value) < 0.05:
        return "other"
    return {
        "momentum_crossover": "mom_xover",
        "trend_strength": "rs_vs_spy",
        "volume_confirmation": "vol_surge",
    }.get(key, key)


def _gate_label(value: float) -> str:
    if value >= 0.05:
        return "bullish"
    if value <= -0.05:
        return "bearish"
    return "neutral"


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
