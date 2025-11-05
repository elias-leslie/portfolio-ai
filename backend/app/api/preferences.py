"""User preferences API router."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from app.storage import get_storage

router = APIRouter(prefix="/api/preferences", tags=["preferences"])

# Initialize services
storage = get_storage()


# Request/Response models
class PreferencesResponse(BaseModel):
    """Response model for user preferences."""

    risk_tolerance: int = Field(..., description="Risk tolerance (1-10)")
    allow_long: bool = Field(..., description="Allow long positions")
    allow_short: bool = Field(..., description="Allow short positions")
    allow_options: bool = Field(..., description="Allow options trading")
    allow_crypto: bool = Field(..., description="Allow crypto trading")
    allow_futures: bool = Field(..., description="Allow futures trading")
    max_position_size_pct: float = Field(..., description="Maximum position size as % of portfolio")
    # Refresh control fields
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
    frontend_poll_interval: int = Field(..., description="Frontend polling interval in seconds")
    # Legacy watchlist fields (kept for backward compatibility)
    watchlist_refresh_minutes: int = Field(..., description="Watchlist refresh interval in minutes")
    watchlist_auto_expand: bool = Field(..., description="Auto-expand watchlist rows")
    watchlist_price_weight: float = Field(..., description="Weight for price score component")
    watchlist_technical_weight: float = Field(
        ..., description="Weight for technical score component"
    )
    display_timezone: str = Field(..., description="User's preferred display timezone")
    watchlist_show_news: bool = Field(..., description="Show news sentiment in watchlist UI")


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
    # Refresh control fields
    default_refresh_minutes: int | None = Field(
        None, ge=1, le=1440, description="Global default refresh interval (1-1440 minutes)"
    )
    watchlist_refresh_override: int | None = Field(
        None,
        ge=1,
        le=1440,
        description="Watchlist-specific refresh override (1-1440 minutes, NULL = use default)",
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
    frontend_poll_interval: int | None = Field(
        None, ge=10, le=300, description="Frontend polling interval (10-300 seconds)"
    )
    # Legacy watchlist fields (kept for backward compatibility)
    watchlist_refresh_minutes: int | None = Field(
        None, ge=1, le=1440, description="Watchlist refresh interval (1-1440 minutes)"
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


def _get_or_create_preferences() -> dict[str, object]:
    """Get existing preferences or create default ones."""
    with storage.connection() as conn:
        result_df = conn.execute(
            "SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
        ).df()

    if not result_df.empty:
        row = result_df.iloc[0].to_dict()
        if "watchlist_show_news" not in row:
            row["watchlist_show_news"] = True
        return dict(row)  # Explicitly cast to dict to satisfy mypy

    # Create default preferences
    user_id = "default"

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                default_refresh_minutes, watchlist_refresh_override,
                portfolio_refresh_override, news_refresh_override,
                frontend_poll_interval,
                watchlist_refresh_minutes, watchlist_auto_expand,
                watchlist_price_weight, watchlist_technical_weight,
                watchlist_show_news,
                display_timezone,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                user_id,
                5,
                True,
                False,
                False,
                False,
                False,
                10.0,
                15,  # default_refresh_minutes
                None,  # watchlist_refresh_override
                None,  # portfolio_refresh_override
                None,  # news_refresh_override
                30,  # frontend_poll_interval
                15,  # watchlist_refresh_minutes (legacy)
                False,
                50.0,
                50.0,
                True,
                "America/New_York",
                datetime.now(UTC),
                datetime.now(UTC),
            ],
        )
        conn.commit()  # Commit the insert

    return {
        "id": user_id,
        "risk_tolerance": 5,
        "allow_long": True,
        "allow_short": False,
        "allow_options": False,
        "allow_crypto": False,
        "allow_futures": False,
        "max_position_size_pct": 10.0,
        # Refresh control fields
        "default_refresh_minutes": 15,
        "watchlist_refresh_override": None,
        "portfolio_refresh_override": None,
        "news_refresh_override": None,
        "frontend_poll_interval": 30,
        # Legacy watchlist fields
        "watchlist_refresh_minutes": 15,
        "watchlist_auto_expand": False,
        "watchlist_price_weight": 50.0,
        "watchlist_technical_weight": 50.0,
        "watchlist_show_news": True,
        "display_timezone": "America/New_York",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


@router.get("/", response_model=PreferencesResponse)
async def get_preferences() -> PreferencesResponse:
    """Get user's risk tolerance and trade preferences."""
    prefs = await run_in_threadpool(_get_or_create_preferences)

    return PreferencesResponse(
        risk_tolerance=cast(int, prefs["risk_tolerance"]),
        allow_long=cast(bool, prefs["allow_long"]),
        allow_short=cast(bool, prefs["allow_short"]),
        allow_options=cast(bool, prefs["allow_options"]),
        allow_crypto=cast(bool, prefs["allow_crypto"]),
        allow_futures=cast(bool, prefs["allow_futures"]),
        max_position_size_pct=cast(float, prefs["max_position_size_pct"]),
        # Refresh control fields
        default_refresh_minutes=cast(int, prefs["default_refresh_minutes"]),
        watchlist_refresh_override=cast(int | None, prefs.get("watchlist_refresh_override")),
        portfolio_refresh_override=cast(int | None, prefs.get("portfolio_refresh_override")),
        news_refresh_override=cast(int | None, prefs.get("news_refresh_override")),
        frontend_poll_interval=cast(int, prefs["frontend_poll_interval"]),
        # Legacy watchlist fields
        watchlist_refresh_minutes=cast(int, prefs["watchlist_refresh_minutes"]),
        watchlist_auto_expand=cast(bool, prefs["watchlist_auto_expand"]),
        watchlist_price_weight=cast(float, prefs["watchlist_price_weight"]),
        watchlist_technical_weight=cast(float, prefs["watchlist_technical_weight"]),
        display_timezone=cast(str, prefs["display_timezone"]),
        watchlist_show_news=cast(bool, prefs.get("watchlist_show_news", True)),
    )


@router.post("/", response_model=PreferencesResponse)
async def update_preferences(update: PreferencesUpdate) -> PreferencesResponse:
    """Update user preferences."""
    # Get current preferences
    current = await run_in_threadpool(_get_or_create_preferences)

    # Update fields
    if update.risk_tolerance is not None:
        current["risk_tolerance"] = update.risk_tolerance
    if update.allow_long is not None:
        current["allow_long"] = update.allow_long
    if update.allow_short is not None:
        current["allow_short"] = update.allow_short
    if update.allow_options is not None:
        current["allow_options"] = update.allow_options
    if update.allow_crypto is not None:
        current["allow_crypto"] = update.allow_crypto
    if update.allow_futures is not None:
        current["allow_futures"] = update.allow_futures
    if update.max_position_size_pct is not None:
        current["max_position_size_pct"] = update.max_position_size_pct
    # Refresh control fields
    if update.default_refresh_minutes is not None:
        current["default_refresh_minutes"] = update.default_refresh_minutes
    if update.watchlist_refresh_override is not None:
        current["watchlist_refresh_override"] = update.watchlist_refresh_override
    if update.portfolio_refresh_override is not None:
        current["portfolio_refresh_override"] = update.portfolio_refresh_override
    if update.news_refresh_override is not None:
        current["news_refresh_override"] = update.news_refresh_override
    if update.frontend_poll_interval is not None:
        current["frontend_poll_interval"] = update.frontend_poll_interval
    # Legacy watchlist fields
    if update.watchlist_refresh_minutes is not None:
        current["watchlist_refresh_minutes"] = update.watchlist_refresh_minutes
    if update.watchlist_auto_expand is not None:
        current["watchlist_auto_expand"] = update.watchlist_auto_expand
    if update.watchlist_price_weight is not None:
        current["watchlist_price_weight"] = update.watchlist_price_weight
    if update.watchlist_technical_weight is not None:
        current["watchlist_technical_weight"] = update.watchlist_technical_weight
    if update.display_timezone is not None:
        current["display_timezone"] = update.display_timezone
    if update.watchlist_show_news is not None:
        current["watchlist_show_news"] = update.watchlist_show_news

    # Save to database
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET risk_tolerance = %s,
                allow_long = %s,
                allow_short = %s,
                allow_options = %s,
                allow_crypto = %s,
                allow_futures = %s,
                max_position_size_pct = %s,
                default_refresh_minutes = %s,
                watchlist_refresh_override = %s,
                portfolio_refresh_override = %s,
                news_refresh_override = %s,
                frontend_poll_interval = %s,
                watchlist_refresh_minutes = %s,
                watchlist_auto_expand = %s,
                watchlist_price_weight = %s,
                watchlist_technical_weight = %s,
                watchlist_show_news = %s,
                display_timezone = %s,
                updated_at = %s
            WHERE id = %s
            """,
            [
                current["risk_tolerance"],
                current["allow_long"],
                current["allow_short"],
                current["allow_options"],
                current["allow_crypto"],
                current["allow_futures"],
                current["max_position_size_pct"],
                current["default_refresh_minutes"],
                current["watchlist_refresh_override"],
                current["portfolio_refresh_override"],
                current["news_refresh_override"],
                current["frontend_poll_interval"],
                current["watchlist_refresh_minutes"],
                current["watchlist_auto_expand"],
                current["watchlist_price_weight"],
                current["watchlist_technical_weight"],
                current.get("watchlist_show_news", True),
                current["display_timezone"],
                datetime.now(UTC),
                current["id"],
            ],
        )
        conn.commit()  # Commit the update

    return PreferencesResponse(
        risk_tolerance=cast(int, current["risk_tolerance"]),
        allow_long=cast(bool, current["allow_long"]),
        allow_short=cast(bool, current["allow_short"]),
        allow_options=cast(bool, current["allow_options"]),
        allow_crypto=cast(bool, current["allow_crypto"]),
        allow_futures=cast(bool, current["allow_futures"]),
        max_position_size_pct=cast(float, current["max_position_size_pct"]),
        # Refresh control fields
        default_refresh_minutes=cast(int, current["default_refresh_minutes"]),
        watchlist_refresh_override=cast(int | None, current.get("watchlist_refresh_override")),
        portfolio_refresh_override=cast(int | None, current.get("portfolio_refresh_override")),
        news_refresh_override=cast(int | None, current.get("news_refresh_override")),
        frontend_poll_interval=cast(int, current["frontend_poll_interval"]),
        # Legacy watchlist fields
        watchlist_refresh_minutes=cast(int, current["watchlist_refresh_minutes"]),
        watchlist_auto_expand=cast(bool, current["watchlist_auto_expand"]),
        watchlist_price_weight=cast(float, current["watchlist_price_weight"]),
        watchlist_technical_weight=cast(float, current["watchlist_technical_weight"]),
        display_timezone=cast(str, current["display_timezone"]),
        watchlist_show_news=cast(bool, current.get("watchlist_show_news", True)),
    )
