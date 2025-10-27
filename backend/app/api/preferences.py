"""User preferences API router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
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
    max_position_size_pct: float = Field(
        ..., description="Maximum position size as % of portfolio"
    )
    preferred_sectors: list[str] = Field(..., description="Preferred sectors")
    excluded_sectors: list[str] = Field(..., description="Excluded sectors")


class PreferencesUpdate(BaseModel):
    """Request model for updating preferences."""

    risk_tolerance: int | None = Field(None, ge=1, le=10, description="Risk tolerance (1-10)")
    allow_long: bool | None = Field(None, description="Allow long positions")
    allow_short: bool | None = Field(None, description="Allow short positions")
    allow_options: bool | None = Field(None, description="Allow options trading")
    max_position_size_pct: float | None = Field(
        None, gt=0, le=100, description="Maximum position size as % of portfolio"
    )
    preferred_sectors: list[str] | None = Field(None, description="Preferred sectors")
    excluded_sectors: list[str] | None = Field(None, description="Excluded sectors")


def _get_or_create_preferences() -> dict:
    """Get existing preferences or create default ones."""
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()

    if result:
        return {
            "user_id": result[0],
            "risk_tolerance": result[1],
            "allow_long": result[2],
            "allow_short": result[3],
            "allow_options": result[4],
            "max_position_size_pct": result[5],
            "preferred_sectors": result[6].split(",") if result[6] else [],
            "excluded_sectors": result[7].split(",") if result[7] else [],
            "created_at": result[8],
            "updated_at": result[9],
        }

    # Create default preferences
    import uuid

    user_id = str(uuid.uuid4())
    default_prefs = {
        "user_id": user_id,
        "risk_tolerance": 5,
        "allow_long": True,
        "allow_short": False,
        "allow_options": False,
        "max_position_size_pct": 10.0,
        "preferred_sectors": "",
        "excluded_sectors": "",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    storage.insert_dict("user_preferences", default_prefs)

    # Return as expected format
    return {
        **default_prefs,
        "preferred_sectors": [],
        "excluded_sectors": [],
    }


@router.get("/", response_model=PreferencesResponse)
async def get_preferences() -> PreferencesResponse:
    """Get user's risk tolerance and trade preferences."""
    prefs = _get_or_create_preferences()

    return PreferencesResponse(
        risk_tolerance=prefs["risk_tolerance"],
        allow_long=prefs["allow_long"],
        allow_short=prefs["allow_short"],
        allow_options=prefs["allow_options"],
        max_position_size_pct=prefs["max_position_size_pct"],
        preferred_sectors=prefs["preferred_sectors"],
        excluded_sectors=prefs["excluded_sectors"],
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
    if update.max_position_size_pct is not None:
        current["max_position_size_pct"] = update.max_position_size_pct
    if update.preferred_sectors is not None:
        current["preferred_sectors"] = update.preferred_sectors
    if update.excluded_sectors is not None:
        current["excluded_sectors"] = update.excluded_sectors

    # Save to database
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE user_preferences
            SET risk_tolerance = ?,
                allow_long = ?,
                allow_short = ?,
                allow_options = ?,
                max_position_size_pct = ?,
                preferred_sectors = ?,
                excluded_sectors = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            [
                current["risk_tolerance"],
                current["allow_long"],
                current["allow_short"],
                current["allow_options"],
                current["max_position_size_pct"],
                ",".join(current["preferred_sectors"]),
                ",".join(current["excluded_sectors"]),
                datetime.now(),
                current["user_id"],
            ],
        )

    return PreferencesResponse(
        risk_tolerance=current["risk_tolerance"],
        allow_long=current["allow_long"],
        allow_short=current["allow_short"],
        allow_options=current["allow_options"],
        max_position_size_pct=current["max_position_size_pct"],
        preferred_sectors=current["preferred_sectors"],
        excluded_sectors=current["excluded_sectors"],
    )
