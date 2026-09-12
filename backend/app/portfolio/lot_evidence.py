"""Read recorded lots in the same non-paper holdings scope, without a sale."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.portfolio.account_types import is_taxable
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.portfolio.transactions import TransactionLedger
from app.storage import PortfolioStorage


class LotEvidence(BaseModel):
    id: str
    acquired_date: date
    remaining_shares: float
    cost_per_share: float
    remaining_basis: float
    gain_at_quote: float | None


class AccountLotEvidence(BaseModel):
    account_id: str
    account_name: str
    account_type: str
    taxable: bool
    position_shares: float
    recorded_lot_shares: float
    coverage: Literal["complete", "partial", "missing", "mismatch"]
    lots: list[LotEvidence] = Field(default_factory=list)


class SymbolLotEvidence(BaseModel):
    symbol: str
    quote_price: float | None = None
    quote_time: datetime | None = None
    quote_source: str | None = None
    accounts: list[AccountLotEvidence] = Field(default_factory=list)


def get_lot_evidence(storage: PortfolioStorage, symbol: str) -> SymbolLotEvidence:
    symbol = symbol.upper()
    manager = PortfolioManager(storage)
    ledger = TransactionLedger(storage)
    accounts = {
        account.id: account for account in manager.get_accounts() if account.account_type != "paper"
    }
    positions: dict[str, float] = {}
    for position in manager.get_positions():
        if (
            position.account_id in accounts
            and position.symbol.upper() == symbol
            and position.position_type == "long"
        ):
            positions[position.account_id] = positions.get(position.account_id, 0) + position.shares
    price = PriceDataFetcher(storage).fetch_cached_price_data([symbol]).get(symbol)
    quote = (
        price.price
        if price and not price.error and math.isfinite(price.price) and price.price > 0
        else None
    )
    result = SymbolLotEvidence(
        symbol=symbol,
        quote_price=quote,
        quote_time=price.quote_time if price else None,
        quote_source=price.source if quote is not None and price else None,
    )
    for account_id, shares in positions.items():
        if shares <= 0:
            continue
        account = accounts[account_id]
        lots = ledger.open_lots(account_id, symbol)
        lot_shares = sum(lot.remaining_shares for lot in lots)
        coverage = (
            "missing"
            if not lots
            else "complete"
            if math.isclose(lot_shares, shares, rel_tol=1e-6, abs_tol=1e-6)
            else "partial"
            if lot_shares < shares
            else "mismatch"
        )
        result.accounts.append(
            AccountLotEvidence(
                account_id=account_id,
                account_name=account.name,
                account_type=account.account_type,
                taxable=is_taxable(account.account_type),
                position_shares=shares,
                recorded_lot_shares=lot_shares,
                coverage=coverage,
                lots=[
                    LotEvidence(
                        id=lot.id,
                        acquired_date=lot.acquired_date,
                        remaining_shares=lot.remaining_shares,
                        cost_per_share=lot.cost_per_share,
                        remaining_basis=lot.remaining_shares * lot.cost_per_share,
                        gain_at_quote=(quote - lot.cost_per_share) * lot.remaining_shares
                        if quote is not None
                        else None,
                    )
                    for lot in lots
                ],
            )
        )
    return result
