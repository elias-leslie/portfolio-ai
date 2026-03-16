"""Pydantic models for user preferences."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# Constants
ALLOWED_NEWS_LOOKBACK_HOURS = (6, 12, 24, 48)
DEFAULT_NEWS_LOOKBACK_HOURS = 6
ALLOWED_NEWS_MAX_ARTICLES = (5, 10, 15, 20)
DEFAULT_NEWS_MAX_ARTICLES = 10
MIN_WATCHLIST_REFRESH_MINUTES = 15

# Default preferences values
DEFAULT_PREFERENCES = {
    "risk_tolerance": 5,
    "allow_long": True,
    "allow_short": False,
    "allow_options": False,
    "allow_crypto": False,
    "allow_futures": False,
    "max_position_size_pct": 10.0,
    "default_refresh_minutes": 15,
    "watchlist_refresh_override": None,
    "portfolio_refresh_override": None,
    "news_refresh_override": None,
    "news_lookback_hours": DEFAULT_NEWS_LOOKBACK_HOURS,
    "news_max_articles": DEFAULT_NEWS_MAX_ARTICLES,
    "frontend_poll_interval": 30,
    "watchlist_refresh_minutes": 15,
    "watchlist_auto_expand": False,
    "watchlist_price_weight": 50.0,
    "watchlist_technical_weight": 50.0,
    "watchlist_show_news": True,
    "display_timezone": "America/New_York",
    "thesis_generation_enabled": None,
    "auto_remove_on_invalidation": None,
    "auto_trim_enabled": None,
}


def clamp_watchlist_refresh_minutes(value: int | None) -> int:
    """Clamp any required watchlist refresh interval to the supported floor."""
    if value is None:
        return MIN_WATCHLIST_REFRESH_MINUTES
    return max(int(value), MIN_WATCHLIST_REFRESH_MINUTES)


def clamp_optional_watchlist_refresh_minutes(value: int | None) -> int | None:
    """Clamp an optional watchlist refresh interval while preserving NULL semantics."""
    if value is None:
        return None
    return clamp_watchlist_refresh_minutes(value)


class PreferencesResponse(BaseModel):
    """Response model for user preferences."""

    risk_tolerance: int = Field(..., description="Risk tolerance (1-10)")
    allow_long: bool = Field(..., description="Allow long positions")
    allow_short: bool = Field(..., description="Allow short positions")
    allow_options: bool = Field(..., description="Allow options trading")
    allow_crypto: bool = Field(..., description="Allow crypto trading")
    allow_futures: bool = Field(..., description="Allow futures trading")
    max_position_size_pct: float = Field(..., description="Maximum position size as % of portfolio")
    default_refresh_minutes: int = Field(
        ..., description="Global default refresh interval in minutes"
    )
    watchlist_refresh_override: int | None = Field(
        None, description="Watchlist-specific refresh override (NULL = use default)"
    )
    portfolio_refresh_override: int | None = Field(
        None, description="Portfolio-specific refresh override (NULL = use default)"
    )
    news_refresh_override: int | None = Field(
        None, description="News-specific refresh override (NULL = use default)"
    )
    news_lookback_hours: int = Field(
        ..., description="Lookback window (hours) used for news aggregation and summaries"
    )
    news_max_articles: int = Field(
        ..., description="Default maximum number of headlines per symbol/market view"
    )
    frontend_poll_interval: int = Field(..., description="Frontend polling interval in seconds")
    watchlist_refresh_minutes: int = Field(..., description="Watchlist refresh interval in minutes")
    watchlist_auto_expand: bool = Field(..., description="Auto-expand watchlist rows")
    watchlist_price_weight: float = Field(..., description="Weight for price score component")
    watchlist_technical_weight: float = Field(
        ..., description="Weight for technical score component"
    )
    display_timezone: str = Field(..., description="User's preferred display timezone")
    watchlist_show_news: bool = Field(..., description="Show news sentiment in watchlist UI")
    thesis_generation_enabled: bool = Field(
        ..., description="Allow Jenny and related tasks to auto-generate or refresh theses"
    )
    auto_remove_on_invalidation: bool = Field(
        ..., description="Auto-remove invalidated theses from the active loop"
    )
    auto_trim_enabled: bool = Field(
        ..., description="Allow automatic watchlist trimming for weak names"
    )


class PreferencesUpdate(BaseModel):
    """Request model for updating preferences."""

    risk_tolerance: int | None = Field(None, ge=1, le=10, description="Risk tolerance (1-10)")
    allow_long: bool | None = Field(None, description="Allow long positions")
    allow_short: bool | None = Field(None, description="Allow short positions")
    allow_options: bool | None = Field(None, description="Allow options trading")
    allow_crypto: bool | None = Field(None, description="Allow crypto trading")
    allow_futures: bool | None = Field(None, description="Allow futures trading")
    max_position_size_pct: float | None = Field(
        None, gt=0, le=100, description="Maximum position size as % of portfolio"
    )
    default_refresh_minutes: int | None = Field(
        None,
        ge=MIN_WATCHLIST_REFRESH_MINUTES,
        le=1440,
        description="Global default refresh interval (15-1440 minutes)",
    )
    watchlist_refresh_override: int | None = Field(
        None,
        ge=MIN_WATCHLIST_REFRESH_MINUTES,
        le=1440,
        description="Watchlist-specific refresh override (15-1440 minutes, NULL = use default)",
    )
    portfolio_refresh_override: int | None = Field(
        None,
        ge=1,
        le=1440,
        description="Portfolio-specific refresh override (1-1440 minutes, NULL = use default)",
    )
    news_refresh_override: int | None = Field(
        None,
        ge=1,
        le=1440,
        description="News-specific refresh override (1-1440 minutes, NULL = use default)",
    )
    news_lookback_hours: int | None = Field(
        None,
        description="Lookback window (hours) used for news aggregation (allowed: 6, 12, 24, 48)",
    )
    news_max_articles: int | None = Field(
        None,
        description="Maximum headlines returned per symbol bundle (allowed: 5, 10, 15, 20)",
    )
    frontend_poll_interval: int | None = Field(
        None, ge=10, le=300, description="Frontend polling interval (10-300 seconds)"
    )
    watchlist_refresh_minutes: int | None = Field(
        None,
        ge=MIN_WATCHLIST_REFRESH_MINUTES,
        le=1440,
        description="Watchlist refresh interval (15-1440 minutes)",
    )
    watchlist_auto_expand: bool | None = Field(None, description="Auto-expand watchlist rows")
    watchlist_price_weight: float | None = Field(
        None, ge=0, le=100, description="Weight for price score component (0-100)"
    )
    watchlist_technical_weight: float | None = Field(
        None, ge=0, le=100, description="Weight for technical score component (0-100)"
    )
    display_timezone: str | None = Field(
        None, description="User's preferred display timezone (USA timezones only)"
    )
    watchlist_show_news: bool | None = Field(
        None, description="Show news sentiment and headlines within the watchlist UI"
    )
    thesis_generation_enabled: bool | None = Field(
        None, description="Allow Jenny and related tasks to auto-generate or refresh theses"
    )
    auto_remove_on_invalidation: bool | None = Field(
        None, description="Auto-remove invalidated theses from the active loop"
    )
    auto_trim_enabled: bool | None = Field(
        None, description="Allow automatic watchlist trimming for weak names"
    )

    @field_validator("display_timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        """Validate timezone is one of the 6 supported USA timezones."""
        if v is None:
            return v

        valid_timezones = {
            "America/New_York",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/Anchorage",
            "Pacific/Honolulu",
        }

        if v not in valid_timezones:
            msg = f"Invalid timezone. Must be one of: {', '.join(sorted(valid_timezones))}"
            raise ValueError(msg)

        return v

    @field_validator("news_lookback_hours")
    @classmethod
    def validate_news_lookback(cls, v: int | None) -> int | None:
        """Validate news lookback window is within the allowed presets."""
        if v is None:
            return v
        if v not in ALLOWED_NEWS_LOOKBACK_HOURS:
            allowed = ", ".join(str(val) for val in ALLOWED_NEWS_LOOKBACK_HOURS)
            msg = f"Invalid news lookback hours. Must be one of: {allowed}"
            raise ValueError(msg)
        return v

    @field_validator("news_max_articles")
    @classmethod
    def validate_news_max_articles(cls, v: int | None) -> int | None:
        """Validate the default max-headline count stays within supported options."""
        if v is None:
            return v
        if v not in ALLOWED_NEWS_MAX_ARTICLES:
            allowed = ", ".join(str(val) for val in ALLOWED_NEWS_MAX_ARTICLES)
            msg = f"Invalid news max articles. Must be one of: {allowed}"
            raise ValueError(msg)
        return v


class ScoringWeightsUpdate(BaseModel):
    """Request model for updating scoring weights."""

    price: float = Field(..., ge=0, le=100, description="Price component weight (0-100)")
    technical: float = Field(..., ge=0, le=100, description="Technical component weight (0-100)")
    fundamental: float = Field(
        ..., ge=0, le=100, description="Fundamental component weight (0-100)"
    )
    catalyst: float = Field(..., ge=0, le=100, description="Catalyst component weight (0-100)")

    @field_validator("catalyst")
    @classmethod
    def validate_weights_sum(cls, v: float, info: Any) -> float:
        """Validate that all weights sum to 100."""
        if not info.data:
            return v

        total = (
            info.data.get("price", 0)
            + info.data.get("technical", 0)
            + info.data.get("fundamental", 0)
            + v
        )

        if abs(total - 100.0) > 0.01:  # Allow small floating point errors
            msg = f"Weights must sum to 100 (got {total})"
            raise ValueError(msg)

        return v
