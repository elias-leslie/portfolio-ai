"""Response builders for watchlist API endpoints.

This module provides helper functions to construct API response models from service layer data.
Centralizing response construction logic reduces duplication and ensures consistency.

All response models used by the watchlist API are defined here for organization and reusability.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .models import NarrativeBulletsDict, NewsIntelligenceDict, RecentNewsDict


# Helper functions
def _build_data_quality_response(data: dict[str, Any] | None) -> DataQualityResponse | None:
    """
    Build DataQualityResponse from dictionary.

    Args:
        data: Dictionary with overall_pct and pillars keys

    Returns:
        DataQualityResponse or None if data is invalid
    """
    if not data or "pillars" not in data:
        return None

    pillars = {}
    for pillar_name, pillar_data in data["pillars"].items():
        if isinstance(pillar_data, dict):
            pillars[pillar_name] = PillarQualityResponse(**pillar_data)

    return DataQualityResponse(overall_pct=data["overall_pct"], pillars=pillars)


# Data Quality models
class PillarQualityResponse(BaseModel):
    """Response model for individual pillar data quality."""

    status: str = Field(..., description="Quality status: complete, partial, stale, or n/a")
    score: float = Field(..., description="Quality score 0-100")
    details: str = Field(..., description="Human-readable quality details")


class DataQualityResponse(BaseModel):
    """Response model for overall data quality assessment."""

    overall_pct: float = Field(..., description="Overall data quality percentage 0-100")
    pillars: dict[str, PillarQualityResponse] = Field(
        ...,
        description="Quality breakdown by pillar (technical, fundamental, catalyst, options, price)",
    )


# Request models
class WatchlistItemCreate(BaseModel):
    """Request model for creating a watchlist item."""

    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    note: str | None = Field(None, description="Optional notes about this symbol")


class WatchlistItemUpdate(BaseModel):
    """Request model for updating a watchlist item."""

    note: str | None = Field(None, description="Optional notes about this symbol")


class RefreshRequest(BaseModel):
    """Request model for manual refresh.

    Note: Watchlist is now user-level (not account-level), so no account_id needed.
    """

    pass  # No fields needed - refresh applies to all user's watchlist items


class ScoreComponentResponse(BaseModel):
    """Response model for individual score component."""

    score: float
    weight: float
    stale: bool
    updated_at: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    sub_scores: dict[str, float] | None = None


class ScoreBreakdownResponse(BaseModel):
    """Response model for score breakdown."""

    price: ScoreComponentResponse
    technical: ScoreComponentResponse
    fundamental: ScoreComponentResponse | None = None
    catalyst: ScoreComponentResponse | None = None  # Fourth pillar (event-driven signals)
    options_flow: ScoreComponentResponse | None = None  # Fifth pillar (GAP-031)
    overall: float


class WatchlistItemResponse(BaseModel):
    """Response model for watchlist item with current scores."""

    id: str
    symbol: str
    note: str | None = None
    source: str = "manual"  # 'manual' or 'portfolio'
    created_at: str
    updated_at: str
    current_score: ScoreBreakdownResponse | None = None
    score_alert: bool = False  # True if score changed >10 points in last 7 days

    # Narrative intelligence fields
    signal_type: str | None = None
    signal_strength: int | None = None
    narrative_headline: str | None = None
    recommended_style: str | None = None
    style_confidence: int | None = None
    optimal_holding_period: str | None = None
    risk_level: str | None = None

    # Trade calculation fields
    entry_price: float | None = None
    stop_loss: float | None = None
    profit_target: float | None = None
    position_size_shares: int | None = None

    # Narrative text fields
    narrative_action_plan: str | None = None
    narrative_position_sizing: str | None = None
    narrative_company_health: NarrativeBulletsDict | None = None
    narrative_special_notes: str | None = None

    # Fundamental/earnings fields
    company_health: str | None = None
    earnings_date: str | None = None  # ISO date string
    earnings_days_away: int | None = None
    # News & sentiment fields
    news_sentiment_score: float | None = None
    recent_news: RecentNewsDict | None = None
    news_intelligence: NewsIntelligenceDict | None = None  # NewsIntelligence summary

    # Priority indicators (NO cap - show all relevant)
    priority_indicators: list[dict[str, str | int | float | bool]] = Field(
        default_factory=list,
        description="Priority indicators (🔥 hot, 📋 earnings, 📰 news, etc.)",
    )

    # Timeframe alignment fields (FEAT-183)
    timeframe_short_aligned: bool | None = Field(None, description="Price > SMA_20 > SMA_50")
    timeframe_long_aligned: bool | None = Field(None, description="SMA_50 > SMA_200")
    volume_relative: float | None = Field(None, description="Current volume / 50-day average")

    # Gap analysis / readiness fields (Task 5.1)
    readiness_score: float | None = Field(
        None, description="Analysis readiness score 0-100% (data completeness)"
    )
    confidence_level: str | None = Field(None, description="Confidence level: LOW/MEDIUM/HIGH")
    gap_warning: str | None = Field(None, description="Warning message if data gaps exist")

    # Data quality assessment
    data_quality: DataQualityResponse | None = Field(
        None, description="Data quality assessment by pillar"
    )

    @classmethod
    def from_service_dict(cls, item: dict[str, Any]) -> WatchlistItemResponse:
        """
        Construct WatchlistItemResponse from service layer dictionary.

        Args:
            item: Dictionary from service layer (e.g., from get_items_with_scores)

        Returns:
            WatchlistItemResponse instance with all fields populated

        Example:
            >>> item_dict = {
            ...     "id": "abc-123",
            ...     "symbol": "AAPL",
            ...     "note": "Watch for earnings",
            ...     "created_at": "2025-01-01T00:00:00Z",
            ...     "updated_at": "2025-01-01T00:00:00Z",
            ...     "score": {
            ...         "price": {"score": 75.0, "weight": 0.5, "stale": False},
            ...         "technical": {"score": 80.0, "weight": 0.5, "stale": False},
            ...         "overall": 77.5
            ...     }
            ... }
            >>> response = WatchlistItemResponse.from_service_dict(item_dict)
            >>> response.symbol
            'AAPL'
        """
        # Build score breakdown if score data is present
        current_score = None
        if item.get("score"):
            current_score = ScoreBreakdownResponse(
                price=ScoreComponentResponse(**item["score"]["price"]),
                technical=ScoreComponentResponse(**item["score"]["technical"]),
                fundamental=ScoreComponentResponse(**item["score"]["fundamental"])
                if item["score"].get("fundamental")
                else None,
                catalyst=ScoreComponentResponse(**item["score"]["catalyst"])
                if item["score"].get("catalyst")
                else None,
                options_flow=ScoreComponentResponse(**item["score"]["options_flow"])
                if item["score"].get("options_flow")
                else None,
                overall=item["score"]["overall"],
            )

        return cls(
            id=item["id"],
            symbol=item["symbol"],
            note=item.get("note"),
            source=item.get("source", "manual"),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            current_score=current_score,
            score_alert=item.get("score_alert", False),
            # Narrative intelligence fields
            signal_type=item.get("signal_type"),
            signal_strength=item.get("signal_strength"),
            narrative_headline=item.get("narrative_headline"),
            recommended_style=item.get("recommended_style"),
            style_confidence=item.get("style_confidence"),
            optimal_holding_period=item.get("optimal_holding_period"),
            risk_level=item.get("risk_level"),
            # Trade calculation fields
            entry_price=item.get("entry_price"),
            stop_loss=item.get("stop_loss"),
            profit_target=item.get("profit_target"),
            position_size_shares=item.get("position_size_shares"),
            # Narrative text fields
            narrative_action_plan=item.get("narrative_action_plan"),
            narrative_position_sizing=item.get("narrative_position_sizing"),
            narrative_company_health=item.get("narrative_company_health"),
            narrative_special_notes=item.get("narrative_special_notes"),
            # Fundamental/earnings fields
            company_health=item.get("company_health"),
            earnings_date=item.get("earnings_date"),
            earnings_days_away=item.get("earnings_days_away"),
            # News
            news_sentiment_score=item.get("news_sentiment_score"),
            recent_news=item.get("recent_news"),
            news_intelligence=item.get("news_intelligence"),
            # Priority indicators
            priority_indicators=item.get("priority_indicators", []),
            # Timeframe alignment (FEAT-183)
            timeframe_short_aligned=item.get("timeframe_short_aligned"),
            timeframe_long_aligned=item.get("timeframe_long_aligned"),
            volume_relative=item.get("volume_relative"),
            # Gap analysis / readiness (Task 5.1)
            readiness_score=item.get("readiness_score"),
            confidence_level=item.get("confidence_level"),
            gap_warning=item.get("gap_warning"),
            # Data quality
            data_quality=_build_data_quality_response(item.get("data_quality"))
            if item.get("data_quality")
            else None,
        )


def build_watchlist_item_responses(items: list[dict[str, Any]]) -> list[WatchlistItemResponse]:
    """
    Build list of WatchlistItemResponse from service layer dictionaries.

    Args:
        items: List of dictionaries from service layer

    Returns:
        List of WatchlistItemResponse instances

    Example:
        >>> items = [
        ...     {"id": "1", "symbol": "AAPL", ...},
        ...     {"id": "2", "symbol": "GOOGL", ...}
        ... ]
        >>> responses = build_watchlist_item_responses(items)
        >>> len(responses)
        2
    """
    return [WatchlistItemResponse.from_service_dict(item) for item in items]


class WatchlistListResponse(BaseModel):
    """Response model for list of watchlist items."""

    items: list[WatchlistItemResponse]
    total_count: int


class FailedTickerInfo(BaseModel):
    """Information about a failed symbol refresh."""

    symbol: str
    reason: str


class RefreshResponse(BaseModel):
    """Response model for manual refresh request."""

    status: str
    message: str
    refreshed_count: int
    failed_count: int = 0
    failed: list[FailedTickerInfo] = Field(default_factory=list)


class RefreshStatusResponse(BaseModel):
    """Response model for refresh status query."""

    is_refreshing: bool = Field(..., description="Whether a refresh is currently in progress")
    started_at: str | None = Field(None, description="ISO timestamp when refresh started")
    elapsed_seconds: float | None = Field(None, description="Seconds elapsed since start")
    total_items: int | None = Field(None, description="Total number of items to process")
    processed_items: int | None = Field(None, description="Number of items processed so far")
    current_symbol: str | None = Field(None, description="Currently processing symbol")
    percent_complete: float | None = Field(None, description="Percentage complete (0-100)")


class ScoreHistoryPoint(BaseModel):
    """Response model for a single score history point."""

    timestamp: str
    overall: float
    price_score: float
    technical_score: float


class ScoreHistoryResponse(BaseModel):
    """Response model for score history."""

    item_id: str
    symbol: str
    history: list[ScoreHistoryPoint]
