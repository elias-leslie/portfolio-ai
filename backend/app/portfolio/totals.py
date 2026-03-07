"""Shared helpers for live portfolio value totals."""

from __future__ import annotations

from dataclasses import dataclass

from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage


@dataclass(slots=True)
class PortfolioTotals:
    """Cash and invested totals for the current portfolio."""

    cash_balance_total: float
    invested_total_value: float

    @property
    def cash_inclusive_total_value(self) -> float:
        """Return invested value plus cash balances."""
        return self.invested_total_value + self.cash_balance_total


def get_live_portfolio_totals(
    storage: PortfolioStorage,
    *,
    include_paper: bool = False,
) -> PortfolioTotals:
    """Return live portfolio totals using the same pricing path as the portfolio views."""
    portfolio_mgr = PortfolioManager(storage)
    all_accounts = portfolio_mgr.get_accounts()
    accounts = all_accounts if include_paper else [
        account for account in all_accounts if account.account_type != "paper"
    ]

    cash_balance_total = sum(account.cash_balance for account in accounts)
    account_ids = {account.id for account in accounts}
    positions = [position for position in portfolio_mgr.get_positions() if position.account_id in account_ids]

    if not positions:
        return PortfolioTotals(
            cash_balance_total=cash_balance_total,
            invested_total_value=0.0,
        )

    price_fetcher = PriceDataFetcher(storage)
    symbols = list({position.symbol for position in positions})
    price_data = price_fetcher.fetch_price_data(symbols)
    analytics = PortfolioAnalytics().calculate_full_analytics(
        positions,
        price_data,
        storage=storage,
        account_ids=list(account_ids),
    )

    return PortfolioTotals(
        cash_balance_total=cash_balance_total,
        invested_total_value=analytics.portfolio_value.total_value,
    )
