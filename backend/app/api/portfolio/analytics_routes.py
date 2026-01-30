"""Portfolio analytics routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

from .models import (
    AnalyticsResponse,
    DiversificationScoreResponse,
    PositionPerformanceResponse,
    RiskProfileResponse,
)

logger = get_logger(__name__)

# Initialize services
storage = get_storage()
portfolio_mgr = PortfolioManager(storage)
price_fetcher = PriceDataFetcher(storage)
analytics_calculator = PortfolioAnalytics()

router = APIRouter()


@router.get("/analytics", response_model=AnalyticsResponse)
@cache_response(ttl=30)  # 30 seconds cache
async def get_analytics(request: Request, include_paper: bool = False) -> AnalyticsResponse:
    """Get portfolio analytics (value, beta, volatility, concentration, sector exposure).

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
        raise HTTPException(status_code=404, detail="No positions in portfolio")

    # Get price data
    symbols = list({p.symbol for p in positions})
    price_data = price_fetcher.fetch_price_data(symbols)

    # Calculate analytics
    analytics = analytics_calculator.calculate_full_analytics(positions, price_data)

    # Convert risk profile to response model
    risk_profile_response = None
    if analytics.risk_profile:
        risk_profile_response = RiskProfileResponse(
            level=analytics.risk_profile.level,
            score=analytics.risk_profile.score,
            factors=analytics.risk_profile.factors,
        )

    # Convert diversification score to response model
    diversification_response = None
    if analytics.diversification_score:
        diversification_response = DiversificationScoreResponse(
            score=analytics.diversification_score.score,
            level=analytics.diversification_score.level,
            num_holdings=analytics.diversification_score.num_holdings,
            num_sectors=analytics.diversification_score.num_sectors,
        )

    # Convert top/bottom performers to response models
    top_performers_response = [
        PositionPerformanceResponse(
            symbol=p.symbol,
            gain_pct=p.gain_pct,
            gain_amount=p.gain_amount,
            current_value=p.current_value,
            weight_pct=p.weight_pct,
        )
        for p in analytics.top_performers
    ]

    bottom_performers_response = [
        PositionPerformanceResponse(
            symbol=p.symbol,
            gain_pct=p.gain_pct,
            gain_amount=p.gain_amount,
            current_value=p.current_value,
            weight_pct=p.weight_pct,
        )
        for p in analytics.bottom_performers
    ]

    return AnalyticsResponse(
        portfolio_value={
            "total_value": analytics.portfolio_value.total_value,
            "total_cost_basis": analytics.portfolio_value.total_cost_basis,
            "total_gain": analytics.portfolio_value.total_gain,
            "total_gain_pct": analytics.portfolio_value.total_gain_pct,
        },
        portfolio_beta=analytics.portfolio_beta,
        portfolio_volatility=analytics.portfolio_volatility,
        sharpe_ratio=analytics.sharpe_ratio,
        sector_exposure=analytics.sector_exposure,
        concentration={
            "top_holding_pct": analytics.concentration_metrics.top_holding_pct,
            "top_3_pct": analytics.concentration_metrics.top_3_pct,
            "top_10_pct": analytics.concentration_metrics.top_10_pct,
            "herfindahl_index": analytics.concentration_metrics.herfindahl_index,
        },
        risk_profile=risk_profile_response,
        diversification_score=diversification_response,
        top_performers=top_performers_response,
        bottom_performers=bottom_performers_response,
        num_positions=analytics.num_positions,
        num_symbols=analytics.num_symbols,
    )
