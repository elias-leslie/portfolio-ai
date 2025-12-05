"""Centralized user preferences loader to eliminate duplicate queries.

This module provides a single-query approach to load all user preferences,
replacing multiple individual queries scattered across the codebase.

BEFORE (Issue #3):
- 5 separate queries to user_preferences table
- Each query fetches 1-2 fields
- Total: 5 queries per refresh

AFTER (Fix):
- 1 query fetches ALL preferences
- Single dataclass with all fields
- Total: 1 query per refresh (80% reduction)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

from app.watchlist.models import ScoreWeights


@dataclass
class UserPreferences:
    """User preferences loaded in a single query.

    All preferences are loaded at once to avoid N separate queries.
    Provides convenient access to all user settings with sensible defaults.
    """

    # News preferences
    news_lookback_hours: int
    news_max_articles: int

    # Watchlist scoring weights (legacy 2-pillar)
    watchlist_price_weight: float
    watchlist_technical_weight: float

    # Refresh timing
    watchlist_refresh_override: int | None
    default_refresh_minutes: int

    # Risk management
    watchlist_risk_budget: float

    @classmethod
    def load_all(cls, storage: PortfolioStorage) -> UserPreferences:
        """Load all user preferences in a single query.

        This replaces 5 individual queries with 1 comprehensive query,
        eliminating redundant database round-trips.

        Args:
            storage: PortfolioStorage instance

        Returns:
            UserPreferences with all fields populated (uses defaults if DB empty)
        """
        df = storage.query(
            """
            SELECT
                news_lookback_hours,
                news_max_articles,
                watchlist_price_weight,
                watchlist_technical_weight,
                watchlist_refresh_override,
                default_refresh_minutes,
                watchlist_risk_budget
            FROM user_preferences
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )

        if df.is_empty():
            # Return defaults if no preferences exist
            return cls(
                news_lookback_hours=24,
                news_max_articles=10,
                watchlist_price_weight=50.0,
                watchlist_technical_weight=50.0,
                watchlist_refresh_override=None,
                default_refresh_minutes=15,
                watchlist_risk_budget=500.0,
            )

        row = df.to_dicts()[0]
        return cls(
            news_lookback_hours=row.get("news_lookback_hours") or 24,
            news_max_articles=row.get("news_max_articles") or 10,
            watchlist_price_weight=row.get("watchlist_price_weight") or 50.0,
            watchlist_technical_weight=row.get("watchlist_technical_weight") or 50.0,
            watchlist_refresh_override=row.get("watchlist_refresh_override"),
            default_refresh_minutes=row.get("default_refresh_minutes") or 15,
            watchlist_risk_budget=row.get("watchlist_risk_budget") or 500.0,
        )

    def get_stale_ttl_minutes(self) -> int:
        """Calculate stale TTL from preferences (3x refresh interval).

        Returns:
            TTL in minutes for stale score detection
        """
        refresh_minutes = (
            self.watchlist_refresh_override
            if self.watchlist_refresh_override is not None
            else self.default_refresh_minutes
        )
        return refresh_minutes * 3


def get_user_scoring_weights(storage: PortfolioStorage, user_id: str | None = None) -> ScoreWeights:
    """Get user scoring weights from preferences or defaults.

    Args:
        storage: PortfolioStorage instance
        user_id: User ID to fetch preferences for (defaults to 'default')

    Returns:
        ScoreWeights object with user preferences or default weights
    """
    # Default weights (from ScoreWeights defaults)
    default_weights = ScoreWeights()

    # Use 'default' user if not specified
    if user_id is None:
        user_id = "default"

    # Query user preferences for score weights
    df = storage.query(
        """
        SELECT watchlist_score_weights
        FROM user_preferences
        WHERE id = %s
        LIMIT 1
        """,
        [user_id],
    )

    if df.is_empty():
        # No preferences found, return defaults
        return default_weights

    row = df.to_dicts()[0]
    weights_json = row.get("watchlist_score_weights")

    if not weights_json:
        # No custom weights, return defaults
        return default_weights

    # Extract weights from JSONB column
    # watchlist_score_weights has structure: {"price": 25, "technical": 25, "fundamental": 30, "catalyst": 20}
    return ScoreWeights(
        price=float(weights_json.get("price", default_weights.price)),
        technical=float(weights_json.get("technical", default_weights.technical)),
        fundamental=float(weights_json.get("fundamental", default_weights.fundamental)),
        catalyst=float(weights_json.get("catalyst", default_weights.catalyst)),
    )
