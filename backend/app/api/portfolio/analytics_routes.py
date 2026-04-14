"""Portfolio analytics routes."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.portfolio.account_valuation import (
    calculate_account_valuations,
    summarize_quote_freshness,
)
from app.services.household_portfolio_totals import get_effective_portfolio_totals

from .models import (
    AnalyticsResponse,
    DiversificationScoreResponse,
    PositionPerformanceResponse,
    RiskProfileResponse,
)

logger = get_logger(__name__)

router = APIRouter()


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _portfolio_mgr():
    return import_module("app.portfolio.manager").PortfolioManager(_storage())


@lru_cache(maxsize=1)
def _price_fetcher():
    return import_module("app.portfolio.price_fetcher").PriceDataFetcher(_storage())


@lru_cache(maxsize=1)
def _analytics_calculator():
    return import_module("app.portfolio.analytics").PortfolioAnalytics()


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
    *,
    effective_total_value: float | None,
    household_total_value: float | None,
    household_invested_total_value: float | None,
    household_cash_reserve: float | None,
    household_investment_accounts_count: int | None,
    quotes_updated_at: str | None,
    quote_freshness_status: str | None,
    quote_freshness_label: str | None,
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
        effective_total_value=effective_total_value,
        household_total_value=household_total_value,
        household_invested_total_value=household_invested_total_value,
        household_cash_reserve=household_cash_reserve,
        household_investment_accounts_count=household_investment_accounts_count,
        quotes_updated_at=quotes_updated_at,
        quote_freshness_status=quote_freshness_status,
        quote_freshness_label=quote_freshness_label,
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


def get_analytics_payload(include_paper: bool) -> AnalyticsResponse:
    portfolio_mgr = _portfolio_mgr()
    all_accounts = portfolio_mgr.get_accounts()
    household_dashboard = None
    household_service = None
    try:
        household_service = import_module("app.services.household_finance_service").HouseholdFinanceService()
        household_dashboard = household_service.get_dashboard()
    except Exception as exc:
        logger.warning("portfolio_analytics_household_dashboard_unavailable", error=str(exc))
    effective_totals = get_effective_portfolio_totals(
        _storage(),
        include_paper=include_paper,
        household_service=household_service,
        dashboard=household_dashboard,
    )
    if not include_paper:
        accounts = [acc for acc in all_accounts if acc.account_type != "paper"]
    else:
        accounts = all_accounts

    account_ids = {acc.id for acc in accounts}
    cash_overrides = {}
    if household_dashboard is not None:
        for account in list(getattr(household_dashboard, "accounts", []) or []):
            linked_portfolio_account_id = getattr(account, "linked_portfolio_account_id", None)
            cash_balance = getattr(account, "cash_balance", None)
            if linked_portfolio_account_id and cash_balance is not None:
                cash_overrides[str(linked_portfolio_account_id)] = float(cash_balance)

    cash_balance_total = sum(
        float(cash_overrides.get(acc.id, float(getattr(acc, "cash_balance", 0.0) or 0.0)))
        for acc in accounts
    )

    all_positions = portfolio_mgr.get_positions()
    positions = [p for p in all_positions if p.account_id in account_ids]

    if not positions:
        response = _empty_analytics_response(cash_balance_total)
        return response.model_copy(
            update={
                "effective_total_value": effective_totals.effective_total_value,
                "household_total_value": effective_totals.household_total_value,
                "household_invested_total_value": effective_totals.household_invested_total_value,
                "household_cash_reserve": effective_totals.household_cash_reserve,
                "household_investment_accounts_count": effective_totals.household_investment_accounts_count,
                "quotes_updated_at": None,
                "quote_freshness_status": None,
                "quote_freshness_label": None,
            }
        )

    symbols = list({p.symbol for p in positions})
    price_data = _price_fetcher().fetch_price_data(symbols)
    account_valuations = calculate_account_valuations(
        accounts,
        positions,
        price_data,
        cash_overrides=cash_overrides,
    )
    quotes_updated_at, quote_freshness_status, quote_freshness_label = summarize_quote_freshness(
        account_valuations
    )
    analytics = _analytics_calculator().calculate_full_analytics(
        positions,
        price_data,
        storage=_storage(),
        account_ids=list(account_ids),
    )

    return _build_full_analytics_response(
        analytics,
        cash_balance_total,
        effective_total_value=effective_totals.effective_total_value,
        household_total_value=effective_totals.household_total_value,
        household_invested_total_value=effective_totals.household_invested_total_value,
        household_cash_reserve=effective_totals.household_cash_reserve,
        household_investment_accounts_count=effective_totals.household_investment_accounts_count,
        quotes_updated_at=quotes_updated_at.isoformat() if quotes_updated_at is not None else None,
        quote_freshness_status=quote_freshness_status,
        quote_freshness_label=quote_freshness_label,
    )


@router.get("/analytics", response_model=AnalyticsResponse)
@cache_response(ttl=30)  # 30 seconds cache
async def get_analytics(request: Request, include_paper: bool = False) -> AnalyticsResponse:
    """Get portfolio analytics (value, beta, volatility, concentration, sector exposure).

    Args:
        include_paper: If False (default), excludes paper trading accounts.
    """
    return await run_in_threadpool(get_analytics_payload, include_paper)
