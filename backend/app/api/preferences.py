"""User preferences API router."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

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


def _get_or_create_preferences() -> dict[str, object]:
    """Get existing preferences or create default ones."""
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()

    if result:
        return {
            "id": result[0],
            "risk_tolerance": result[1],
            "allow_long": result[2],
            "allow_short": result[3],
            "allow_options": result[4],
            "allow_crypto": result[5],
            "allow_futures": result[6],
            "max_position_size_pct": result[7],
            "created_at": result[8],
            "updated_at": result[9],
        }

    # Create default preferences
    user_id = str(uuid.uuid4())

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                datetime.now(),
                datetime.now(),
            ],
        )

    return {
        "id": user_id,
        "risk_tolerance": 5,
        "allow_long": True,
        "allow_short": False,
        "allow_options": False,
        "allow_crypto": False,
        "allow_futures": False,
        "max_position_size_pct": 10.0,
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
                datetime.now(),
                current["id"],
            ],
        )

    return PreferencesResponse(
        risk_tolerance=cast(int, current["risk_tolerance"]),
        allow_long=cast(bool, current["allow_long"]),
        allow_short=cast(bool, current["allow_short"]),
        allow_options=cast(bool, current["allow_options"]),
        allow_crypto=cast(bool, current["allow_crypto"]),
        allow_futures=cast(bool, current["allow_futures"]),
        max_position_size_pct=cast(float, current["max_position_size_pct"]),
    )
