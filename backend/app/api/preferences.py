"""User preferences API router."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

from fastapi import APIRouter
from pydantic import BaseModel, Field

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
    watchlist_refresh_minutes: int = Field(..., description="Watchlist refresh interval in minutes")
    watchlist_auto_expand: bool = Field(..., description="Auto-expand watchlist rows")
    watchlist_price_weight: float = Field(..., description="Weight for price score component")
    watchlist_technical_weight: float = Field(
        ..., description="Weight for technical score component"
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


def _get_or_create_preferences() -> dict[str, object]:
    """Get existing preferences or create default ones."""
    with storage.connection() as conn:
        result_df = conn.execute(
            "SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
        ).df()

    if not result_df.empty:
        row = result_df.iloc[0].to_dict()
        return dict(row)  # Explicitly cast to dict to satisfy mypy

    # Create default preferences
    user_id = str(uuid.uuid4())

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                watchlist_refresh_minutes, watchlist_auto_expand,
                watchlist_price_weight, watchlist_technical_weight,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                5,
                False,
                50.0,
                50.0,
                datetime.now(),
                datetime.now(),
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
        "watchlist_refresh_minutes": 5,
        "watchlist_auto_expand": False,
        "watchlist_price_weight": 50.0,
        "watchlist_technical_weight": 50.0,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }


@router.get("/", response_model=PreferencesResponse)
async def get_preferences() -> PreferencesResponse:
    """Get user's risk tolerance and trade preferences."""
    prefs = _get_or_create_preferences()

    return PreferencesResponse(
        risk_tolerance=cast(int, prefs["risk_tolerance"]),
        allow_long=cast(bool, prefs["allow_long"]),
        allow_short=cast(bool, prefs["allow_short"]),
        allow_options=cast(bool, prefs["allow_options"]),
        allow_crypto=cast(bool, prefs["allow_crypto"]),
        allow_futures=cast(bool, prefs["allow_futures"]),
        max_position_size_pct=cast(float, prefs["max_position_size_pct"]),
        watchlist_refresh_minutes=cast(int, prefs["watchlist_refresh_minutes"]),
        watchlist_auto_expand=cast(bool, prefs["watchlist_auto_expand"]),
        watchlist_price_weight=cast(float, prefs["watchlist_price_weight"]),
        watchlist_technical_weight=cast(float, prefs["watchlist_technical_weight"]),
    )


@router.post("/", response_model=PreferencesResponse)
async def update_preferences(update: PreferencesUpdate) -> PreferencesResponse:
    """Update user preferences."""
    # Get current preferences
    current = _get_or_create_preferences()

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
    if update.watchlist_refresh_minutes is not None:
        current["watchlist_refresh_minutes"] = update.watchlist_refresh_minutes
    if update.watchlist_auto_expand is not None:
        current["watchlist_auto_expand"] = update.watchlist_auto_expand
    if update.watchlist_price_weight is not None:
        current["watchlist_price_weight"] = update.watchlist_price_weight
    if update.watchlist_technical_weight is not None:
        current["watchlist_technical_weight"] = update.watchlist_technical_weight

    # Save to database
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET risk_tolerance = ?,
                allow_long = ?,
                allow_short = ?,
                allow_options = ?,
                allow_crypto = ?,
                allow_futures = ?,
                max_position_size_pct = ?,
                watchlist_refresh_minutes = ?,
                watchlist_auto_expand = ?,
                watchlist_price_weight = ?,
                watchlist_technical_weight = ?,
                updated_at = ?
            WHERE id = ?
            """,
            [
                current["risk_tolerance"],
                current["allow_long"],
                current["allow_short"],
                current["allow_options"],
                current["allow_crypto"],
                current["allow_futures"],
                current["max_position_size_pct"],
                current["watchlist_refresh_minutes"],
                current["watchlist_auto_expand"],
                current["watchlist_price_weight"],
                current["watchlist_technical_weight"],
                datetime.now(),
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
        watchlist_refresh_minutes=cast(int, current["watchlist_refresh_minutes"]),
        watchlist_auto_expand=cast(bool, current["watchlist_auto_expand"]),
        watchlist_price_weight=cast(float, current["watchlist_price_weight"]),
        watchlist_technical_weight=cast(float, current["watchlist_technical_weight"]),
    )
