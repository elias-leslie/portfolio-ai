"""Portfolio position CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.logging_config import get_logger
from app.middleware.cache import invalidate_endpoint_cache
from app.portfolio.manager import PortfolioManager
from app.portfolio.models import Position
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage
from app.strategies.storage import get_strategy_storage

from .models import PositionCreate, PositionResponse

logger = get_logger(__name__)

# Initialize services
storage = get_storage()
portfolio_mgr = PortfolioManager(storage)
price_fetcher = PriceDataFetcher(storage)

router = APIRouter()


def _build_position_response(
    position: Position, include_strategy_name: bool = True
) -> PositionResponse:
    """Build a PositionResponse from a position object.

    Args:
        position: Position object from portfolio manager
        include_strategy_name: Whether to fetch and include strategy name

    Returns:
        PositionResponse with current price and gain calculations
    """
    # Get current price if available
    price_data = price_fetcher.fetch_price_data([position.symbol])
    price_info = price_data.get(position.symbol)
    current_price = price_info.price if price_info else None

    if current_price:
        current_value = position.shares * current_price
        gain = current_value - (position.shares * position.cost_basis)
        gain_pct = (gain / (position.shares * position.cost_basis)) * 100
    else:
        current_value = None
        gain = None
        gain_pct = None

    # Get strategy name if linked
    strategy_name = None
    if include_strategy_name and position.strategy_id:
        strategy_storage = get_strategy_storage()
        strategy = strategy_storage.get_strategy_by_id(position.strategy_id)
        strategy_name = strategy.name if strategy else None

    return PositionResponse(
        id=position.id,
        account_id=position.account_id,
        symbol=position.symbol,
        shares=position.shares,
        cost_basis=position.cost_basis,
        position_type=position.position_type,
        strategy_id=position.strategy_id,
        strategy_name=strategy_name,
        created_at=position.created_at.isoformat(),
        updated_at=position.updated_at.isoformat(),
        current_price=current_price,
        current_value=current_value,
        gain=gain,
        gain_pct=gain_pct,
    )


@router.post("/position", response_model=PositionResponse)
async def create_position(position: PositionCreate) -> PositionResponse:
    """Add or update a portfolio position."""
    # Check if account exists
    accounts = portfolio_mgr.get_accounts()
    if not any(acc.id == position.account_id for acc in accounts):
        raise HTTPException(status_code=404, detail="Account not found")

    # Create position
    created = portfolio_mgr.add_position(
        account_id=position.account_id,
        symbol=position.symbol,
        shares=position.shares,
        cost_basis=position.cost_basis,
        position_type=position.position_type,
        strategy_id=position.strategy_id,
    )

    # Invalidate portfolio cache
    invalidate_endpoint_cache("/api/portfolio/", method="GET")
    invalidate_endpoint_cache("/api/portfolio/analytics", method="GET")

    return _build_position_response(created, include_strategy_name=True)


@router.put("/position/{position_id}", response_model=PositionResponse)
async def update_position(position_id: str, position: PositionCreate) -> PositionResponse:
    """Update an existing portfolio position."""
    # Check if position exists
    positions = portfolio_mgr.get_positions()
    existing_pos = next((p for p in positions if p.id == position_id), None)
    if not existing_pos:
        raise HTTPException(status_code=404, detail="Position not found")

    # Check if account exists
    accounts = portfolio_mgr.get_accounts()
    if not any(acc.id == position.account_id for acc in accounts):
        raise HTTPException(status_code=404, detail="Account not found")

    # Update position
    updated = portfolio_mgr.update_position(
        position_id=position_id,
        account_id=position.account_id,
        symbol=position.symbol,
        shares=position.shares,
        cost_basis=position.cost_basis,
        position_type=position.position_type,
    )

    # Invalidate portfolio cache
    invalidate_endpoint_cache("/api/portfolio/", method="GET")
    invalidate_endpoint_cache("/api/portfolio/analytics", method="GET")

    return _build_position_response(updated, include_strategy_name=False)


@router.delete("/position/{position_id}")
async def delete_position(position_id: str) -> dict[str, str]:
    """Delete a portfolio position."""
    portfolio_mgr.delete_position(position_id)

    # Invalidate portfolio cache
    invalidate_endpoint_cache("/api/portfolio/", method="GET")
    invalidate_endpoint_cache("/api/portfolio/analytics", method="GET")

    return {"status": "deleted", "position_id": position_id}
