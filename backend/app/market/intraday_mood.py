"""Intraday market mood proxy from live quote inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any


def _get_value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _maybe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _number(source: Any, key: str) -> float | None:
    return _maybe_float(_get_value(source, key))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def label_intraday_mood(score: int) -> str:
    if score < 25:
        return "Fearful"
    if score < 45:
        return "Cautious"
    if score < 58:
        return "Mixed"
    if score < 75:
        return "Constructive"
    return "Risk-on"


def tone_intraday_mood(score: int) -> str:
    if score < 45:
        return "warning"
    if score >= 70:
        return "positive"
    return "neutral"


def calculate_intraday_mood_score(
    indicators: Mapping[str, Any],
    sectors: Sequence[Any],
) -> int:
    """Score live market mood from quote-driven inputs."""
    sp500 = indicators.get("sp500", {})
    vix = indicators.get("vix", {})
    tnx = indicators.get("tnx", {})
    dxy = indicators.get("dxy", {})
    sector_changes = [
        value
        for value in (_number(sector, "change_pct") for sector in sectors)
        if value is not None
    ]

    score = 50.0
    if (sp500_change := _number(sp500, "change_pct")) is not None:
        score += _clamp(sp500_change * 8, -18, 18)
    if (vix_value := _number(vix, "value")) is not None:
        score += 12 if vix_value < 15 else 4 if vix_value < 20 else -8 if vix_value < 25 else -18
    if (vix_change := _number(vix, "change_pct")) is not None:
        score -= _clamp(vix_change * 0.8, -12, 12)
    if (tnx_change := _number(tnx, "change_pct")) is not None:
        score -= _clamp(tnx_change * 1.5, -8, 8)
    if (dxy_change := _number(dxy, "change_pct")) is not None:
        score -= _clamp(dxy_change * 0.8, -6, 6)
    if sector_changes:
        average = sum(sector_changes) / len(sector_changes)
        breadth = sum(1 if value > 0 else -1 if value < 0 else 0 for value in sector_changes)
        score += _clamp(average * 5, -8, 8)
        score += _clamp((breadth / len(sector_changes)) * 10, -10, 10)

    return round(_clamp(score, 0, 100))
