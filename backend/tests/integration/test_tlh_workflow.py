"""Postgres-backed integration tests for the TLH workflow + scan snapshot.

Exercises the cross-account wash-sale fixture from the F2 plan: a
Taxable sell candidate plus a Roth buy 20 days prior must trigger
``WashSaleVerdict.blocked=True``. Also asserts the daily workflow
upserts ``tlh_scan_results`` idempotently for the same scan_date.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from app.portfolio.manager import PortfolioManager
from app.portfolio.models import PriceData
from app.portfolio.tlh import TLHAnalyzer
from app.portfolio.transactions import TransactionLedger
from app.storage import PortfolioStorage, get_storage
from app.workflows.tlh import run_tlh_scan


@pytest.fixture
def storage() -> PortfolioStorage:
    return get_storage()


@pytest.fixture
def manager(storage: PortfolioStorage) -> PortfolioManager:
    return PortfolioManager(storage)


@pytest.fixture
def ledger(storage: PortfolioStorage) -> TransactionLedger:
    return TransactionLedger(storage)


class _StubPriceFetcher:
    """Bypass the live multi-source fetcher for deterministic tests."""

    def __init__(self, prices: dict[str, float]) -> None:
        self._prices = {sym.upper(): price for sym, price in prices.items()}

    def fetch_cached_price_data(self, symbols: list[str]) -> dict[str, PriceData]:
        out: dict[str, PriceData] = {}
        for sym in symbols:
            price = self._prices.get(sym.upper())
            if price is None:
                continue
            out[sym] = PriceData(symbol=sym, price=price)
        return out


def _seed_cross_account_fixture(
    manager: PortfolioManager,
    ledger: TransactionLedger,
    *,
    today: date,
) -> tuple[Any, Any]:
    """Taxable account holds AAPL underwater; Roth bought AAPL 20d before today."""
    taxable = manager.add_account("WashSale-Taxable", "Taxable")
    roth = manager.add_account("WashSale-Roth", "Roth")

    manager.add_position(
        account_id=taxable.id,
        symbol="AAPL",
        shares=10.0,
        cost_basis=200.0,
    )
    ledger.record_transaction(
        account_id=roth.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=today - timedelta(days=20),
        shares=5.0,
        price=180.0,
    )
    return taxable, roth


def _cleanup_accounts(storage: PortfolioStorage, account_ids: list[str]) -> None:
    if not account_ids:
        return
    with storage.connection() as conn:
        for acct_id in account_ids:
            conn.execute(
                "DELETE FROM portfolio_accounts WHERE id = %s",
                [acct_id],
            )
        conn.commit()


def test_cross_account_wash_sale_fixture(
    storage: PortfolioStorage,
    manager: PortfolioManager,
    ledger: TransactionLedger,
) -> None:
    today = date.today()
    taxable, roth = _seed_cross_account_fixture(manager, ledger, today=today)
    try:
        analyzer = TLHAnalyzer(
            storage,
            ledger,
            _StubPriceFetcher({"AAPL": 100.0}),
        )

        verdict = analyzer.wash_sale_check(
            symbol="AAPL", sell_date=today, household_id=None
        )
        assert verdict.blocked is True
        # Roth conflict surfaces with negative day offset.
        roth_conflict = next(
            (c for c in verdict.conflicting_buys if c.account_id == roth.id),
            None,
        )
        assert roth_conflict is not None
        assert roth_conflict.account_type == "Roth"
        assert roth_conflict.days_offset == -20
    finally:
        _cleanup_accounts(storage, [taxable.id, roth.id])


def test_workflow_snapshot_is_idempotent_for_same_day(
    storage: PortfolioStorage,
    manager: PortfolioManager,
    ledger: TransactionLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date.today()
    taxable, roth = _seed_cross_account_fixture(manager, ledger, today=today)
    try:
        # Force the workflow to use a deterministic in-memory price fetcher.
        from app.portfolio import price_fetcher as price_fetcher_mod

        monkeypatch.setattr(
            price_fetcher_mod,
            "PriceDataFetcher",
            lambda _storage: _StubPriceFetcher({"AAPL": 100.0}),
        )

        first = run_tlh_scan(scan_date=today)
        assert first["scan_date"] == today.isoformat()
        assert first["candidates_found"] >= 1

        second = run_tlh_scan(scan_date=today)
        assert second["candidates_found"] == first["candidates_found"]

        rows = storage.query(
            "SELECT account_id, symbol FROM tlh_scan_results "
            "WHERE scan_date = %s",
            [today],
        ).to_dicts()
        # Re-running the same day must not duplicate the AAPL/taxable row.
        keys = [(r["account_id"], r["symbol"]) for r in rows]
        assert (taxable.id, "AAPL") in keys
        assert keys.count((taxable.id, "AAPL")) == 1
    finally:
        with storage.connection() as conn:
            conn.execute(
                "DELETE FROM tlh_scan_results WHERE scan_date = %s",
                [today],
            )
            conn.commit()
        _cleanup_accounts(storage, [taxable.id, roth.id])
