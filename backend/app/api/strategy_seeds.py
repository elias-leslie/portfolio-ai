"""API endpoints for strategy seeds.

Provides REST API for:
- Listing strategy seeds with filtering
- Getting individual seed details

Seeds are AI-generated investment ideas that can evolve into strategies.
High-confidence seeds (>=7/10) automatically trigger strategy workflows.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.logging_config import get_logger
from app.strategies.storage import get_strategy_storage
from app.utils.formatters import format_db_date, parse_float

logger = get_logger(__name__)

router = APIRouter(prefix="/api/strategy-seeds", tags=["strategy-seeds"])


# ============================================================================
# Request/Response Models
# ============================================================================


class StrategySeedItem(BaseModel):
    """Strategy seed item."""

    id: str
    symbol: str
    thesis: str
    confidence: float
    status: Literal["pending", "processing", "converted", "rejected"]
    strategy_id: str | None = None
    created_at: str
    processed_at: str | None = None


class StrategySeedList(BaseModel):
    """List of strategy seeds."""

    seeds: list[StrategySeedItem]
    total: int


# ============================================================================
# Helper Functions
# ============================================================================


def _row_to_seed_item(row: tuple[object, ...]) -> StrategySeedItem:
    """Transform database row into StrategySeedItem.

    Args:
        row: Database row tuple with (id, symbol, thesis, confidence, status, strategy_id, created_at, processed_at)

    Returns:
        StrategySeedItem object
    """
    return StrategySeedItem(
        id=str(row[0]),
        symbol=str(row[1]),
        thesis=str(row[2]),
        confidence=parse_float(row[3]) or 0.0,
        status=str(row[4]),  # type: ignore[arg-type]
        strategy_id=str(row[5]) if row[5] else None,
        created_at=format_db_date(row[6]) or "",
        processed_at=format_db_date(row[7]),
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=StrategySeedList)
async def list_strategy_seeds(
    status: str | None = Query(default=None, description="Filter by status"),
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> StrategySeedList:
    """List strategy seeds with optional filtering.

    Seeds are AI-generated investment ideas that can evolve into strategies.
    High-confidence seeds (>=7/10) automatically trigger strategy workflows.
    """
    try:
        storage = get_strategy_storage()
        rows, total = storage.list_seeds(status=status, symbol=symbol, limit=limit, offset=offset)

        seeds = [_row_to_seed_item(row) for row in rows]
        return StrategySeedList(seeds=seeds, total=total)

    except Exception as e:
        logger.exception("Failed to list strategy seeds", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list strategy seeds: {e!s}") from e


@router.get("/{seed_id}", response_model=StrategySeedItem)
async def get_strategy_seed(seed_id: str) -> StrategySeedItem:
    """Get a specific strategy seed by ID."""
    try:
        storage = get_strategy_storage()
        row = storage.get_seed_by_id(seed_id)

        if not row:
            raise HTTPException(status_code=404, detail=f"Seed {seed_id} not found")

        return _row_to_seed_item(row)

    except Exception as e:
        logger.exception("Failed to get strategy seed", seed_id=seed_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy seed: {e!s}") from e
