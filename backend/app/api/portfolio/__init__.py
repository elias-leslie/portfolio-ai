"""Portfolio API module."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

from .analytics_routes import router as analytics_router
from .models import AccountCreate, AccountResponse, PortfolioResponse, PositionResponse
from .position_routes import router as position_router

logger = get_logger(__name__)

# Create main router
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Initialize services
storage = get_storage()
portfolio_mgr = PortfolioManager(storage)
price_fetcher = PriceDataFetcher(storage)


@router.get("", response_model=PortfolioResponse)
@cache_response(ttl=30)  # 30 seconds cache
async def get_portfolio(request: Request, include_paper: bool = False) -> PortfolioResponse:
    """Get all portfolio positions with current values.

    Args:
        include_paper: If False (default), excludes paper trading accounts.
    """
    all_positions = portfolio_mgr.get_positions()

    # Filter out paper accounts unless explicitly requested
    if not include_paper:
        paper_account_ids = {
            acc.id for acc in portfolio_mgr.get_accounts() if acc.account_type == "paper"
        }
        positions = [p for p in all_positions if p.account_id not in paper_account_ids]
    else:
        positions = all_positions

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

    # Sync portfolio symbols to watchlist
    try:
        portfolio_mgr.sync_portfolio_to_watchlist(symbols)
    except Exception as e:
        # Log error but don't fail the request
        logger.error(f"Failed to sync portfolio to watchlist: {e}")

    price_data = price_fetcher.fetch_price_data(symbols)

    # Calculate analytics
    analytics_calculator = PortfolioAnalytics()
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


@router.get("/accounts", response_model=list[AccountResponse])
async def get_accounts(include_paper: bool = False) -> list[AccountResponse]:
    """Get all portfolio accounts.

    Args:
        include_paper: If False (default), excludes paper trading accounts.
    """
    accounts = portfolio_mgr.get_accounts()

    # Filter out paper accounts unless explicitly requested
    if not include_paper:
        accounts = [acc for acc in accounts if acc.account_type != "paper"]

    return [
        AccountResponse(
            id=acc.id,
            name=acc.name,
            account_type=acc.account_type,
            created_at=acc.created_at.isoformat(),
            updated_at=acc.updated_at.isoformat(),
        )
        for acc in accounts
    ]


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


@router.delete("/account/{account_id}")
async def delete_account(account_id: str) -> dict[str, str]:
    """Delete a portfolio account and all its positions."""
    accounts = portfolio_mgr.get_accounts()
    if not any(acc.id == account_id for acc in accounts):
        raise HTTPException(status_code=404, detail="Account not found")

    # Delete all positions in this account
    positions = portfolio_mgr.get_positions()
    for pos in positions:
        if pos.account_id == account_id:
            portfolio_mgr.delete_position(pos.id)

    # Delete the account
    with storage.connection() as conn:
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", (account_id,))
        conn.commit()

    return {"status": "deleted", "account_id": account_id}


# Include sub-routers
router.include_router(position_router)
router.include_router(analytics_router)
