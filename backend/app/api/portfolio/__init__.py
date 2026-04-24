"""Portfolio API module."""

from __future__ import annotations

__all__ = ["router"]

from functools import lru_cache
from importlib import import_module
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.middleware.cache import cache_response, invalidate_endpoint_cache
from app.portfolio.account_linkage import (
    AccountLinkage,
    build_account_linkages,
    classify_account_linkage,
)
from app.portfolio.account_valuation import (
    calculate_account_valuations,
    summarize_quote_freshness,
)
from app.portfolio.current_facts import calculate_current_position_fact
from app.services.household_portfolio_totals import get_effective_portfolio_totals

from .analytics_routes import router as analytics_router
from .jenny_routes import router as jenny_router
from .models import AccountCreate, AccountResponse, PortfolioResponse, PositionResponse
from .position_routes import router as position_router

# Create main router
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
logger = get_logger(__name__)


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
def _household_service():
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


@lru_cache(maxsize=1)
def _analytics_calculator():
    return import_module("app.portfolio.analytics").PortfolioAnalytics()


def _get_filtered_accounts_and_positions(
    include_paper: bool,
) -> tuple[list[Any], set[str], list[Any]]:
    """Return filtered accounts, their IDs, and filtered positions."""
    portfolio_mgr = _portfolio_mgr()
    all_accounts = portfolio_mgr.get_accounts()
    if not include_paper:
        accounts = [acc for acc in all_accounts if acc.account_type != "paper"]
    else:
        accounts = all_accounts

    account_ids = {acc.id for acc in accounts}

    all_positions = portfolio_mgr.get_positions()
    positions = [p for p in all_positions if p.account_id in account_ids]

    return accounts, account_ids, positions


def _fetch_prices(symbols: list[str]) -> dict[str, Any]:
    """Fetch price data for portfolio symbols."""
    return _price_fetcher().fetch_price_data(symbols)


def _build_position_responses(
    positions: list[Any],
    price_data: dict[str, Any],
) -> list[PositionResponse]:
    """Build PositionResponse objects enriched with current price and gain data."""
    position_responses = []
    for pos in positions:
        price_info = price_data.get(pos.symbol)
        current_price = price_info.price if price_info else None
        current_fact = calculate_current_position_fact(
            symbol=pos.symbol,
            shares=pos.shares,
            cost_basis=pos.cost_basis,
            position_type=pos.position_type,
            current_price=current_price,
        )

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
                current_value=current_fact.current_value,
                gain=current_fact.gain,
                gain_pct=current_fact.gain_pct,
                price_updated_at=(
                    price_info.cached_at.isoformat()
                    if price_info is not None and getattr(price_info, "cached_at", None) is not None
                    else None
                ),
                price_source=(
                    str(getattr(price_info, "source", None))
                    if price_info is not None and getattr(price_info, "source", None)
                    else None
                ),
            )
        )
    return position_responses


def _household_cash_overrides(dashboard: Any | None) -> dict[str, float]:
    if dashboard is None:
        return {}
    overrides: dict[str, float] = {}
    for account in list(getattr(dashboard, "accounts", []) or []):
        linked_portfolio_account_id = getattr(account, "linked_portfolio_account_id", None)
        cash_balance = getattr(account, "cash_balance", None)
        if linked_portfolio_account_id and cash_balance is not None:
            overrides[str(linked_portfolio_account_id)] = float(cash_balance)
    return overrides


def _get_household_dashboard() -> Any | None:
    try:
        return _household_service().get_dashboard()
    except Exception as exc:
        logger.warning("portfolio_household_dashboard_unavailable", error=str(exc))
        return None


def _get_portfolio_payload(include_paper: bool) -> PortfolioResponse:
    accounts, account_ids, positions = _get_filtered_accounts_and_positions(include_paper)
    household_dashboard = _get_household_dashboard()
    effective_totals = get_effective_portfolio_totals(
        _storage(),
        include_paper=include_paper,
        household_service=_household_service(),
        dashboard=household_dashboard,
    )
    cash_overrides = _household_cash_overrides(household_dashboard)
    account_valuations = calculate_account_valuations(
        accounts,
        positions,
        {},
        cash_overrides=cash_overrides,
    )
    cash_balance_total = sum(
        (
            account_valuations.get(account.id).effective_cash_balance
            if account_valuations.get(account.id) is not None
            else float(getattr(account, "cash_balance", 0.0) or 0.0)
        )
        for account in accounts
    )

    if not positions:
        quotes_updated_at, quote_freshness_status, quote_freshness_label = (
            summarize_quote_freshness(account_valuations)
        )
        return PortfolioResponse(
            positions=[],
            cash_balance_total=cash_balance_total,
            total_value=cash_balance_total,
            total_cost_basis=cash_balance_total,
            total_gain=0.0,
            total_gain_pct=0.0,
            effective_total_value=effective_totals.effective_total_value,
            household_total_value=effective_totals.household_total_value,
            household_invested_total_value=effective_totals.household_invested_total_value,
            household_cash_reserve=effective_totals.household_cash_reserve,
            household_investment_accounts_count=effective_totals.household_investment_accounts_count,
            quotes_updated_at=quotes_updated_at.isoformat() if quotes_updated_at is not None else None,
            quote_freshness_status=quote_freshness_status,
            quote_freshness_label=quote_freshness_label,
        )

    symbols = list({p.symbol for p in positions})
    price_data = _fetch_prices(symbols)
    account_valuations = calculate_account_valuations(
        accounts,
        positions,
        price_data,
        cash_overrides=cash_overrides,
    )

    analytics = _analytics_calculator().calculate_full_analytics(
        positions,
        price_data,
        storage=_storage(),
        account_ids=list(account_ids),
    )

    position_responses = _build_position_responses(positions, price_data)
    quotes_updated_at, quote_freshness_status, quote_freshness_label = (
        summarize_quote_freshness(account_valuations)
    )

    total_cost_basis = analytics.portfolio_value.total_cost_basis + cash_balance_total
    total_gain = analytics.portfolio_value.total_gain
    total_value = sum(
        (
            account_valuations.get(account.id).total_value
            if account_valuations.get(account.id) is not None
            else float(getattr(account, "cash_balance", 0.0) or 0.0)
        )
        for account in accounts
    )
    total_gain_pct = (total_gain / total_cost_basis) * 100 if total_cost_basis > 0 else 0.0

    return PortfolioResponse(
        positions=position_responses,
        cash_balance_total=cash_balance_total,
        total_value=total_value,
        total_cost_basis=total_cost_basis,
        total_gain=total_gain,
        total_gain_pct=total_gain_pct,
        effective_total_value=effective_totals.effective_total_value,
        household_total_value=effective_totals.household_total_value,
        household_invested_total_value=effective_totals.household_invested_total_value,
        household_cash_reserve=effective_totals.household_cash_reserve,
        household_investment_accounts_count=effective_totals.household_investment_accounts_count,
        quotes_updated_at=quotes_updated_at.isoformat() if quotes_updated_at is not None else None,
        quote_freshness_status=quote_freshness_status,
        quote_freshness_label=quote_freshness_label,
    )


def _build_account_response(acc: Any, linkage: AccountLinkage | None = None) -> AccountResponse:
    resolved_linkage = linkage or classify_account_linkage(acc, [])
    return AccountResponse(
        id=acc.id,
        name=acc.name,
        account_type=acc.account_type,
        household_account_id=acc.household_account_id,
        household_linkage_state=resolved_linkage.state,
        household_linkage_label=resolved_linkage.label,
        household_linkage_detail=resolved_linkage.detail,
        household_linkage_action_href=resolved_linkage.action_href,
        household_linkage_candidate_count=resolved_linkage.candidate_count,
        household_linkage_candidate_ids=resolved_linkage.candidate_ids,
        cash_balance=acc.cash_balance,
        created_at=acc.created_at.isoformat(),
        updated_at=acc.updated_at.isoformat(),
    )


def _get_accounts_payload(include_paper: bool) -> list[AccountResponse]:
    accounts = _portfolio_mgr().get_accounts()

    if not include_paper:
        accounts = [acc for acc in accounts if acc.account_type != "paper"]

    household_dashboard = _get_household_dashboard()
    household_accounts = list(getattr(household_dashboard, "accounts", []) or [])
    linkages = build_account_linkages(accounts, household_accounts)

    return [
        _build_account_response(acc, linkages.get(acc.id))
        for acc in accounts
    ]


def _create_account_payload(account: AccountCreate) -> AccountResponse:
    created = _portfolio_mgr().add_account(account.name, account.account_type)
    try:
        _household_service().account_registry_service.sync_registry(_household_service(), limit=500)
    except Exception as exc:
        logger.warning(
            "portfolio_account_household_sync_failed",
            account_id=created.id,
            error=str(exc),
        )
    invalidate_endpoint_cache("/api/portfolio", method="GET")
    invalidate_endpoint_cache("/api/portfolio/", method="GET")
    invalidate_endpoint_cache("/api/portfolio/analytics", method="GET")
    persisted = next(
        (account for account in _portfolio_mgr().get_accounts() if account.id == created.id),
        created,
    )
    return _build_account_response(persisted)


def _delete_account_payload(account_id: str) -> dict[str, str]:
    portfolio_mgr = _portfolio_mgr()
    accounts = portfolio_mgr.get_accounts()
    if not any(acc.id == account_id for acc in accounts):
        raise HTTPException(status_code=404, detail="Account not found")

    positions = portfolio_mgr.get_positions()
    for pos in positions:
        if pos.account_id == account_id:
            portfolio_mgr.delete_position(pos.id)

    with _storage().connection() as conn:
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", (account_id,))
        conn.commit()

    try:
        _household_service().account_registry_service.sync_registry(_household_service(), limit=500)
    except Exception as exc:
        logger.warning(
            "portfolio_account_household_sync_failed",
            account_id=account_id,
            error=str(exc),
        )
    invalidate_endpoint_cache("/api/portfolio", method="GET")
    invalidate_endpoint_cache("/api/portfolio/", method="GET")
    invalidate_endpoint_cache("/api/portfolio/analytics", method="GET")

    return {"status": "deleted", "account_id": account_id}


@router.get("", response_model=PortfolioResponse)
@cache_response(ttl=30)  # 30 seconds cache
async def get_portfolio(request: Request, include_paper: bool = False) -> PortfolioResponse:
    """Get all portfolio positions with current values.

    Args:
        include_paper: If False (default), excludes paper trading accounts.
    """
    return await run_in_threadpool(_get_portfolio_payload, include_paper)


@router.get("/accounts", response_model=list[AccountResponse])
async def get_accounts(include_paper: bool = False) -> list[AccountResponse]:
    """Get all portfolio accounts.

    Args:
        include_paper: If False (default), excludes paper trading accounts.
    """
    return await run_in_threadpool(_get_accounts_payload, include_paper)


@router.post("/account", response_model=AccountResponse)
async def create_account(account: AccountCreate) -> AccountResponse:
    """Create a new portfolio account."""
    return await run_in_threadpool(_create_account_payload, account)


@router.delete("/account/{account_id}")
async def delete_account(account_id: str) -> dict[str, str]:
    """Delete a portfolio account and all its positions."""
    return await run_in_threadpool(_delete_account_payload, account_id)


# Include sub-routers
router.include_router(position_router)
router.include_router(analytics_router)
router.include_router(jenny_router)
