"""Response builders for watchlist API endpoints.

This module provides helper functions to construct API response models from service layer data.
Centralizing response construction logic reduces duplication and ensures consistency.

All response models used by the watchlist API are defined here for organization and reusability.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# Request models
class WatchlistItemCreate(BaseModel):
    """Request model for creating a watchlist item."""

    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    note: str | None = Field(None, description="Optional notes about this ticker")


class WatchlistItemUpdate(BaseModel):
    """Request model for updating a watchlist item."""

    note: str | None = Field(None, description="Optional notes about this ticker")


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
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoreBreakdownResponse(BaseModel):
    """Response model for score breakdown."""

    price: ScoreComponentResponse
    technical: ScoreComponentResponse
    overall: float


class WatchlistItemResponse(BaseModel):
    """Response model for watchlist item with current scores."""

    id: str
    symbol: str
    note: str | None = None
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
    narrative_company_health: dict[str, Any] | None = None
    narrative_special_notes: str | None = None

    # Fundamental/earnings fields
    company_health: str | None = None
    earnings_date: str | None = None  # ISO date string
    earnings_days_away: int | None = None
    # News & sentiment fields
    news_sentiment_score: float | None = None
    recent_news: dict[str, Any] | None = None
    news_intelligence: dict[str, Any] | None = None  # NewsIntelligence summary

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
                overall=item["score"]["overall"],
            )

        return cls(
            id=item["id"],
            symbol=item["symbol"],
            note=item.get("note"),
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
    """Information about a failed ticker refresh."""

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
