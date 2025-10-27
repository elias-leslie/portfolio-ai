"""Portfolio API router."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Initialize services
storage = get_storage()
portfolio_mgr = PortfolioManager(storage)
price_fetcher = PriceDataFetcher(storage)
analytics_calculator = PortfolioAnalytics()


# Request/Response models
class AccountCreate(BaseModel):
    """Request model for creating an account."""

    name: str = Field(..., description="Account name")
    account_type: Literal["IRA", "Taxable", "401k", "Roth", "HSA"] = Field(
        ..., description="Account type"
    )


class AccountResponse(BaseModel):
    """Response model for account."""

    id: str
    name: str
    account_type: str
    created_at: str
    updated_at: str


class PositionCreate(BaseModel):
    """Request model for creating/updating a position."""

    account_id: str = Field(..., description="Account ID")
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    shares: float = Field(..., description="Number of shares", gt=0)
    cost_basis: float = Field(..., description="Cost basis per share", gt=0)
    position_type: Literal["long", "short"] = Field(
        default="long", description="Position type"
    )


class PositionResponse(BaseModel):
    """Response model for position."""

    id: str
    account_id: str
    symbol: str
    shares: float
    cost_basis: float
    position_type: str
    created_at: str
    updated_at: str
    current_price: float | None = None
    current_value: float | None = None
    gain: float | None = None
    gain_pct: float | None = None


class PortfolioResponse(BaseModel):
    """Response model for portfolio with positions and current values."""

    positions: list[PositionResponse]
    total_value: float
    total_cost_basis: float
    total_gain: float
    total_gain_pct: float


class AnalyticsResponse(BaseModel):
    """Response model for portfolio analytics."""

    portfolio_value: dict[str, float]
    portfolio_beta: float | None
    portfolio_volatility: float | None
    sector_exposure: dict[str, float]
    concentration_metrics: dict[str, float]
    num_positions: int
    num_symbols: int


@router.get("/", response_model=PortfolioResponse)
async def get_portfolio() -> PortfolioResponse:
    """Get all portfolio positions with current values."""
    positions = portfolio_mgr.get_positions()

    if not positions:
        return PortfolioResponse(
            positions=[],
            total_value=0.0,
            total_cost_basis=0.0,
            total_gain=0.0,
            total_gain_pct=0.0,
        )

    # Get current prices
    symbols = list({p.symbol for p in positions})
    price_data = price_fetcher.fetch_price_data(symbols)

    # Calculate analytics
    analytics = analytics_calculator.calculate_full_analytics(positions, price_data)

    # Build position responses with current values
    position_responses = []
    for pos in positions:
        price_info = price_data.get(pos.symbol)
        current_price = price_info.price if price_info else None

        if current_price:
            current_value = pos.shares * current_price
            gain = current_value - (pos.shares * pos.cost_basis)
            gain_pct = (gain / (pos.shares * pos.cost_basis)) * 100
        else:
            current_value = None
            gain = None
            gain_pct = None

        position_responses.append(
            PositionResponse(
                id=pos.id,
                account_id=pos.account_id,
                symbol=pos.symbol,
                shares=pos.shares,
                cost_basis=pos.cost_basis,
                position_type=pos.position_type,
                created_at=pos.created_at.isoformat(),
                updated_at=pos.updated_at.isoformat(),
                current_price=current_price,
                current_value=current_value,
                gain=gain,
                gain_pct=gain_pct,
            )
        )

    return PortfolioResponse(
        positions=position_responses,
        total_value=analytics.portfolio_value.total_value,
        total_cost_basis=analytics.portfolio_value.total_cost_basis,
        total_gain=analytics.portfolio_value.total_gain,
        total_gain_pct=analytics.portfolio_value.total_gain_pct,
    )


@router.post("/account", response_model=AccountResponse)
async def create_account(account: AccountCreate) -> AccountResponse:
    """Create a new portfolio account."""
    created = portfolio_mgr.add_account(account.name, account.account_type)

    return AccountResponse(
        id=created.id,
        name=created.name,
        account_type=created.account_type,
        created_at=created.created_at.isoformat(),
        updated_at=created.updated_at.isoformat(),
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
    )

    # Get current price if available
    price_data = price_fetcher.fetch_price_data([created.symbol])
    price_info = price_data.get(created.symbol)
    current_price = price_info.price if price_info else None

    if current_price:
        current_value = created.shares * current_price
        gain = current_value - (created.shares * created.cost_basis)
        gain_pct = (gain / (created.shares * created.cost_basis)) * 100
    else:
        current_value = None
        gain = None
        gain_pct = None

    return PositionResponse(
        id=created.id,
        account_id=created.account_id,
        symbol=created.symbol,
        shares=created.shares,
        cost_basis=created.cost_basis,
        position_type=created.position_type,
        created_at=created.created_at.isoformat(),
        updated_at=created.updated_at.isoformat(),
        current_price=current_price,
        current_value=current_value,
        gain=gain,
        gain_pct=gain_pct,
    )


@router.delete("/position/{position_id}")
async def delete_position(position_id: str) -> dict[str, str]:
    """Delete a portfolio position."""
    portfolio_mgr.delete_position(position_id)
    return {"status": "deleted", "position_id": position_id}


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics() -> AnalyticsResponse:
    """Get portfolio analytics (value, beta, volatility, concentration, sector exposure)."""
    positions = portfolio_mgr.get_positions()

    if not positions:
        raise HTTPException(status_code=404, detail="No positions in portfolio")

    # Get price data
    symbols = list({p.symbol for p in positions})
    price_data = price_fetcher.fetch_price_data(symbols)

    # Calculate analytics
    analytics = analytics_calculator.calculate_full_analytics(positions, price_data)

    return AnalyticsResponse(
        portfolio_value={
            "total_value": analytics.portfolio_value.total_value,
            "total_cost_basis": analytics.portfolio_value.total_cost_basis,
            "total_gain": analytics.portfolio_value.total_gain,
            "total_gain_pct": analytics.portfolio_value.total_gain_pct,
        },
        portfolio_beta=analytics.portfolio_beta,
        portfolio_volatility=analytics.portfolio_volatility,
        sector_exposure=analytics.sector_exposure,
        concentration_metrics={
            "top_holding_pct": analytics.concentration_metrics.top_holding_pct,
            "top_3_pct": analytics.concentration_metrics.top_3_pct,
            "top_10_pct": analytics.concentration_metrics.top_10_pct,
            "herfindahl_index": analytics.concentration_metrics.herfindahl_index,
        },
        num_positions=analytics.num_positions,
        num_symbols=analytics.num_symbols,
    )
