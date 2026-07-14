"""Shared effective portfolio totals across household and investing surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING

from app.logging_config import get_logger
from app.portfolio.totals import get_live_portfolio_totals

if TYPE_CHECKING:
    from app.portfolio.totals import PortfolioTotals
    from app.services.household_finance_service import HouseholdFinanceService
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)

_INVESTMENT_ACCOUNT_GROUPS = {"retirement", "taxable", "education"}


@dataclass(slots=True)
class EffectivePortfolioTotals:
    live_cash_balance_total: float
    live_invested_total_value: float
    live_cash_inclusive_total_value: float
    household_total_value: float | None
    household_invested_total_value: float | None
    household_cash_reserve: float | None
    household_investment_accounts_count: int
    household_totals_trusted: bool
    account_control_status: str | None
    account_control_summary: str | None
    account_control_blocking_issue_count: int
    effective_total_value: float
    effective_invested_total_value: float


def _household_service() -> HouseholdFinanceService:
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


def _count_investment_accounts(accounts: list[object]) -> int:
    return sum(
        1
        for account in accounts
        if getattr(account, "current_value", None) is not None
        and getattr(account, "asset_group", None) in _INVESTMENT_ACCOUNT_GROUPS
    )


def get_effective_portfolio_totals(
    storage: PortfolioStorage,
    *,
    include_paper: bool = False,
    household_service: HouseholdFinanceService | None = None,
    dashboard: object | None = None,
) -> EffectivePortfolioTotals:
    """Return live position totals plus household canonical totals when available."""
    live_totals: PortfolioTotals = get_live_portfolio_totals(storage, include_paper=include_paper)
    live_cash_inclusive_total_value = live_totals.cash_inclusive_total_value
    default = EffectivePortfolioTotals(
        live_cash_balance_total=live_totals.cash_balance_total,
        live_invested_total_value=live_totals.invested_total_value,
        live_cash_inclusive_total_value=live_cash_inclusive_total_value,
        household_total_value=None,
        household_invested_total_value=None,
        household_cash_reserve=None,
        household_investment_accounts_count=0,
        household_totals_trusted=False,
        account_control_status=None,
        account_control_summary="Household account controls are unavailable.",
        account_control_blocking_issue_count=0,
        effective_total_value=live_cash_inclusive_total_value,
        effective_invested_total_value=live_totals.invested_total_value,
    )

    try:
        service = household_service or _household_service()
        dashboard = dashboard or service.get_dashboard()
        overview = getattr(dashboard, "overview", None)
        accounts = list(getattr(dashboard, "accounts", []) or [])
        household_total_value = (
            float(getattr(overview, "total_tracked_assets", 0.0) or 0.0) or None
        )
        household_invested_total_value = (
            float(getattr(overview, "invested_assets", 0.0) or 0.0) or None
        )
        household_cash_reserve = (
            float(getattr(overview, "cash_reserve", 0.0) or 0.0) or None
        )
        account_control = getattr(dashboard, "account_control", None)
        account_control_status = (
            str(getattr(account_control, "status", "") or "") or None
        )
        account_control_summary = (
            str(getattr(account_control, "summary", "") or "") or None
        )
        blocking_issue_count = int(
            getattr(account_control, "blocking_issue_count", 0) or 0
        )
        household_totals_trusted = account_control is not None and blocking_issue_count == 0
        if household_totals_trusted:
            effective_total_value = max(
                live_cash_inclusive_total_value,
                household_total_value or 0.0,
            )
            effective_invested_total_value = max(
                live_totals.invested_total_value,
                household_invested_total_value or 0.0,
            )
        else:
            # Keep raw household values available for audit, but never promote
            # them to the canonical Investing total while account control blocks.
            effective_total_value = live_cash_inclusive_total_value
            effective_invested_total_value = live_totals.invested_total_value
        return EffectivePortfolioTotals(
            live_cash_balance_total=live_totals.cash_balance_total,
            live_invested_total_value=live_totals.invested_total_value,
            live_cash_inclusive_total_value=live_cash_inclusive_total_value,
            household_total_value=household_total_value,
            household_invested_total_value=household_invested_total_value,
            household_cash_reserve=household_cash_reserve,
            household_investment_accounts_count=_count_investment_accounts(accounts),
            household_totals_trusted=household_totals_trusted,
            account_control_status=account_control_status,
            account_control_summary=account_control_summary,
            account_control_blocking_issue_count=blocking_issue_count,
            effective_total_value=effective_total_value,
            effective_invested_total_value=effective_invested_total_value,
        )
    except Exception as exc:
        logger.warning("effective_portfolio_totals_household_fallback", error=str(exc))
        return default
