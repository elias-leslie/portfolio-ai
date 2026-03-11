"""Portfolio analytics routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

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


def _empty_analytics_response(cash_balance_total: float) -> AnalyticsResponse:
    """Return an empty AnalyticsResponse when there are no positions."""
    return AnalyticsResponse(
        portfolio_value={
            "total_value": 0.0,
            "total_cost_basis": 0.0,
            "total_gain": 0.0,
            "total_gain_pct": 0.0,
        },
        cash_balance_total=cash_balance_total,
        cash_inclusive_total_value=cash_balance_total,
        portfolio_beta=None,
        portfolio_volatility=None,
        sharpe_ratio=None,
        sector_exposure={},
        concentration={
            "top_holding_pct": 0.0,
            "top_3_pct": 0.0,
            "top_10_pct": 0.0,
            "herfindahl_index": 0.0,
        },
        risk_profile=None,
        diversification_score=None,
        top_performers=[],
        bottom_performers=[],
        num_positions=0,
        num_symbols=0,
    )


def _to_risk_profile_response(analytics: Any) -> RiskProfileResponse | None:
    """Convert analytics risk profile to a RiskProfileResponse, or None."""
    if not analytics.risk_profile:
        return None
    return RiskProfileResponse(
        level=analytics.risk_profile.level,
        score=analytics.risk_profile.score,
        factors=analytics.risk_profile.factors,
    )


def _to_diversification_response(analytics: Any) -> DiversificationScoreResponse | None:
    """Convert analytics diversification score to a DiversificationScoreResponse, or None."""
    if not analytics.diversification_score:
        return None
    return DiversificationScoreResponse(
        score=analytics.diversification_score.score,
        level=analytics.diversification_score.level,
        num_holdings=analytics.diversification_score.num_holdings,
        num_sectors=analytics.diversification_score.num_sectors,
    )


def _to_performer_responses(performers: list[Any]) -> list[PositionPerformanceResponse]:
    """Convert a list of performer objects to PositionPerformanceResponse models."""
    return [
        PositionPerformanceResponse(
            symbol=p.symbol,
            gain_pct=p.gain_pct,
            gain_amount=p.gain_amount,
            current_value=p.current_value,
            weight_pct=p.weight_pct,
        )
        for p in performers
    ]


def _build_full_analytics_response(
    analytics: Any,
    cash_balance_total: float,
) -> AnalyticsResponse:
    """Build the full AnalyticsResponse from a computed analytics object."""
    return AnalyticsResponse(
        portfolio_value={
            "total_value": analytics.portfolio_value.total_value,
            "total_cost_basis": analytics.portfolio_value.total_cost_basis,
            "total_gain": analytics.portfolio_value.total_gain,
            "total_gain_pct": analytics.portfolio_value.total_gain_pct,
        },
        cash_balance_total=cash_balance_total,
        cash_inclusive_total_value=analytics.portfolio_value.total_value + cash_balance_total,
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
        risk_profile=_to_risk_profile_response(analytics),
        diversification_score=_to_diversification_response(analytics),
        top_performers=_to_performer_responses(analytics.top_performers),
        bottom_performers=_to_performer_responses(analytics.bottom_performers),
        num_positions=analytics.num_positions,
        num_symbols=analytics.num_symbols,
    )


@router.get("/analytics", response_model=AnalyticsResponse)
@cache_response(ttl=30)  # 30 seconds cache
async def get_analytics(request: Request, include_paper: bool = False) -> AnalyticsResponse:
    """Get portfolio analytics (value, beta, volatility, concentration, sector exposure).

    Args:
        include_paper: If False (default), excludes paper trading accounts.
    """
    all_accounts = await run_in_threadpool(portfolio_mgr.get_accounts)
    if not include_paper:
        accounts = [acc for acc in all_accounts if acc.account_type != "paper"]
    else:
        accounts = all_accounts

    account_ids = {acc.id for acc in accounts}
    cash_balance_total = sum(acc.cash_balance for acc in accounts)

    all_positions = await run_in_threadpool(portfolio_mgr.get_positions)
    positions = [p for p in all_positions if p.account_id in account_ids]

    if not positions:
        return _empty_analytics_response(cash_balance_total)

    symbols = list({p.symbol for p in positions})
    price_data = await run_in_threadpool(price_fetcher.fetch_price_data, symbols)

    _account_ids = list(account_ids)
    analytics = await run_in_threadpool(
        lambda: analytics_calculator.calculate_full_analytics(
            positions,
            price_data,
            storage=storage,
            account_ids=_account_ids,
        )
    )

    return _build_full_analytics_response(analytics, cash_balance_total)
