"""Response builder functions for core market endpoints."""

from __future__ import annotations

from app.models.market_intelligence import (
    FearGreedScore,
    SectorRotationSummary,
)
from app.models.market_intelligence import (
    MarketHealthScore as MarketHealthScoreResponse,
)


def build_market_health_response(health_score_data: object) -> MarketHealthScoreResponse:
    """Build MarketHealthScoreResponse from health score data."""
    return MarketHealthScoreResponse(
        overall_score=health_score_data.overall_score,
        overall_label=health_score_data.overall_label,
        components=health_score_data.components,
        sectors=health_score_data.sectors,
        last_updated=health_score_data.last_updated,
    )


def build_fear_greed_response(fg_reading: object) -> FearGreedScore:
    """Build FearGreedScore response from fear/greed reading."""
    return FearGreedScore(
        score=int(fg_reading.score),
        label=fg_reading.label,
        score_change=fg_reading.score_change,
        signal_count=fg_reading.signal_count,
        last_updated=fg_reading.date,
        is_stale=fg_reading.is_stale,
        age_days=fg_reading.age_days,
        trend=fg_reading.trend,
        trend_change=fg_reading.trend_change,
    )


def build_sector_rotation_response(
    leading_sectors: list[object],
    neutral_sectors: list[object],
    lagging_sectors: list[object],
) -> SectorRotationSummary:
    """Build SectorRotationSummary from grouped sectors."""
    return SectorRotationSummary(
        leading=leading_sectors,
        neutral=neutral_sectors,
        lagging=lagging_sectors,
        leading_count=len(leading_sectors),
        neutral_count=len(neutral_sectors),
        lagging_count=len(lagging_sectors),
    )
