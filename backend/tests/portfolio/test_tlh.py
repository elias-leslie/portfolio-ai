"""Unit tests for TLHAnalyzer.

Stubs storage with an in-memory PG-shaped fake (mirroring the pattern
in ``test_transactions.py``) and a fake price fetcher so the logic
(taxable filter, threshold math, sort + limit, ST/LT split, wash-sale
across spouse + tax-advantaged accounts, replacement YAML lookup)
exercises end-to-end without a database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.portfolio.contracts.tlh import (
    ReplacementSecurity,
    TLHCandidate,
    WashSaleVerdict,
)
from app.portfolio.models import PriceData
from app.portfolio.tlh import TLHAnalyzer
from app.portfolio.transactions import TransactionLedger


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]):
        self._rows = list(rows)

    def fetchall(self) -> list[tuple[Any, ...]]:
        out = list(self._rows)
        self._rows = []
        return out

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self._rows:
            return None
        return self._rows.pop(0)


class _FakeConn:
    def __init__(self, store: _FakeStore) -> None:
        self.store = store
        self._last: _Cursor | None = None
        self.commit_count = 0

    def execute(
        self,
        query: str,
        params: Iterable[Any] | None = None,
    ) -> _FakeConn:
        params = list(params) if params is not None else []
        normalized = " ".join(query.split())
        rows = self.store.handle(normalized, params)
        self._last = _Cursor(rows)
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        assert self._last is not None
        return self._last.fetchall()

    def fetchone(self) -> tuple[Any, ...] | None:
        assert self._last is not None
        return self._last.fetchone()

    def commit(self) -> None:
        self.commit_count += 1


class _FakeStore:
    """In-memory PG-shaped store covering the TLH/Ledger query surface."""

    def __init__(self) -> None:
        self.accounts: list[dict[str, Any]] = []
        self.positions: list[dict[str, Any]] = []
        self.transactions: list[dict[str, Any]] = []
        self.tax_lots: list[dict[str, Any]] = []

    # ------------- helpers used by tests directly -------------

    def add_account(
        self,
        *,
        id: str,
        account_type: str,
        is_spouse: bool = False,
    ) -> None:
        self.accounts.append(
            {"id": id, "account_type": account_type, "is_spouse": is_spouse}
        )

    def add_position(
        self,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        cost_basis: float,
        position_type: str = "long",
    ) -> None:
        self.positions.append(
            {
                "account_id": account_id,
                "symbol": symbol.upper(),
                "shares": shares,
                "cost_basis": cost_basis,
                "position_type": position_type,
            }
        )

    def add_lot(
        self,
        *,
        account_id: str,
        symbol: str,
        acquired_date: date,
        shares: float,
        cost_per_share: float,
    ) -> None:
        self.tax_lots.append(
            {
                "id": str(uuid.uuid4()),
                "account_id": account_id,
                "symbol": symbol.upper(),
                "acquired_date": acquired_date,
                "original_shares": shares,
                "remaining_shares": shares,
                "cost_per_share": cost_per_share,
                "cost_basis_total": cost_per_share * shares,
                "acquisition_txn_id": None,
                "disposed_at": None,
            }
        )

    def add_buy(
        self,
        *,
        account_id: str,
        symbol: str,
        trade_date: date,
        shares: float,
        price: float,
    ) -> None:
        self.transactions.append(
            {
                "id": str(uuid.uuid4()),
                "account_id": account_id,
                "symbol": symbol.upper(),
                "transaction_type": "buy",
                "trade_date": trade_date,
                "settlement_date": None,
                "shares": shares,
                "price": price,
                "fees": 0.0,
                "realized_gain": None,
                "source": "manual",
                "external_id": None,
                "metadata": "{}",
                "created_at": datetime.now(UTC),
            }
        )

    # ------------- query handler -------------

    def handle(self, query: str, params: list[Any]) -> list[tuple[Any, ...]]:
        q = query.upper()

        if q.startswith("SELECT P.ACCOUNT_ID, A.ACCOUNT_TYPE, P.SYMBOL"):
            out = []
            for pos in self.positions:
                acct = next(
                    (a for a in self.accounts if a["id"] == pos["account_id"]),
                    None,
                )
                if acct is None:
                    continue
                if pos["position_type"] != "long" or pos["shares"] <= 0:
                    continue
                out.append(
                    (
                        pos["account_id"],
                        acct["account_type"],
                        pos["symbol"],
                        pos["shares"],
                        pos["cost_basis"],
                        pos["position_type"],
                    )
                )
            return out

        if q.startswith("SELECT ID, ACCOUNT_TYPE, COALESCE(IS_SPOUSE"):
            return [
                (a["id"], a["account_type"], a["is_spouse"])
                for a in self.accounts
            ]

        if q.startswith(
            "SELECT ID, ACCOUNT_ID, SYMBOL, TRANSACTION_TYPE, TRADE_DATE,"
        ):
            account_ids, symbol, txn_type, since, until = params
            account_ids_set = set(account_ids)
            matches = [
                row
                for row in self.transactions
                if row["account_id"] in account_ids_set
                and row["symbol"] == symbol
                and row["transaction_type"] == txn_type
                and since <= row["trade_date"] <= until
            ]
            matches.sort(key=lambda r: (r["trade_date"], r["created_at"]))
            return [
                (
                    row["id"],
                    row["account_id"],
                    row["symbol"],
                    row["transaction_type"],
                    row["trade_date"],
                    row.get("settlement_date"),
                    row["shares"],
                    row["price"],
                    row["fees"],
                    row.get("realized_gain"),
                    row["source"],
                    row.get("external_id"),
                    row.get("metadata") or "{}",
                    row["created_at"],
                )
                for row in matches
            ]

        if q.startswith("SELECT ID, ACCOUNT_ID, SYMBOL, ACQUIRED_DATE"):
            account_id, symbol = params
            matches = [
                row
                for row in self.tax_lots
                if row["account_id"] == account_id
                and row["symbol"] == symbol
                and float(row["remaining_shares"]) > 0
            ]
            matches.sort(key=lambda r: (r["acquired_date"], r["id"]))
            return [
                (
                    row["id"],
                    row["account_id"],
                    row["symbol"],
                    row["acquired_date"],
                    row["original_shares"],
                    row["remaining_shares"],
                    row["cost_per_share"],
                    row["cost_basis_total"],
                    row["acquisition_txn_id"],
                    row["disposed_at"],
                )
                for row in matches
            ]

        if q.startswith("SELECT COST_BASIS FROM PORTFOLIO_POSITIONS"):
            account_id, symbol = params
            for row in self.positions:
                if row["account_id"] == account_id and row["symbol"] == symbol:
                    return [(row["cost_basis"],)]
            return []

        raise AssertionError(f"unhandled query: {query[:120]} ; params={params!r}")


class _FakeStorage:
    def __init__(self) -> None:
        self.store = _FakeStore()

    def connection(self) -> Any:
        store = self.store

        class _Ctx:
            def __enter__(self_inner) -> _FakeConn:  # noqa: N805
                self_inner.conn = _FakeConn(store)
                return self_inner.conn

            def __exit__(self_inner, *_a: Any) -> None:  # noqa: N805
                pass

        return _Ctx()


class _FakePriceFetcher:
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


def _make_analyzer(
    *,
    prices: dict[str, float] | None = None,
) -> tuple[TLHAnalyzer, _FakeStore]:
    storage = _FakeStorage()
    ledger = TransactionLedger(storage)  # type: ignore[arg-type]
    fetcher = _FakePriceFetcher(prices or {})
    analyzer = TLHAnalyzer(storage, ledger, fetcher)  # type: ignore[arg-type]
    return analyzer, storage.store


# ----------------------------------------------------------------------
# find_loss_candidates
# ----------------------------------------------------------------------


def test_find_candidates_filters_to_taxable_only() -> None:
    analyzer, store = _make_analyzer(prices={"AAPL": 100.0, "VTI": 100.0})
    store.add_account(id="acct-tax", account_type="Taxable")
    store.add_account(id="acct-roth", account_type="Roth")
    store.add_account(id="acct-ira", account_type="IRA")
    store.add_account(id="acct-401k", account_type="401k")
    store.add_account(id="acct-hsa", account_type="HSA")
    # All at the same loss; only Taxable should surface.
    for acct in ("acct-tax", "acct-roth", "acct-ira", "acct-401k", "acct-hsa"):
        store.add_position(account_id=acct, symbol="AAPL", shares=10, cost_basis=200.0)

    out = analyzer.find_loss_candidates(min_loss_pct=0.05, min_loss_amount=100.0)
    assert [c.account_id for c in out] == ["acct-tax"]


def test_find_candidates_respects_min_thresholds() -> None:
    analyzer, store = _make_analyzer(prices={"AAA": 95.0, "BBB": 50.0})
    store.add_account(id="acct-tax", account_type="Taxable")
    # AAA: 5% loss on 10 shares = $50 loss — passes pct only
    store.add_position(account_id="acct-tax", symbol="AAA", shares=10, cost_basis=100.0)
    # BBB: 50% loss on 100 shares = $5000 loss — passes both
    store.add_position(account_id="acct-tax", symbol="BBB", shares=100, cost_basis=100.0)

    # min_loss_amount=200 filters AAA out.
    out = analyzer.find_loss_candidates(min_loss_pct=0.05, min_loss_amount=200.0)
    assert [c.symbol for c in out] == ["BBB"]


def test_find_candidates_sorts_largest_loss_first_and_clips_to_limit() -> None:
    analyzer, store = _make_analyzer(prices={"A": 50.0, "B": 70.0, "C": 90.0})
    store.add_account(id="t", account_type="Taxable")
    store.add_position(account_id="t", symbol="A", shares=100, cost_basis=100.0)
    store.add_position(account_id="t", symbol="B", shares=100, cost_basis=100.0)
    store.add_position(account_id="t", symbol="C", shares=100, cost_basis=100.0)

    out = analyzer.find_loss_candidates(min_loss_pct=0.0, min_loss_amount=0.0, limit=2)
    assert [c.symbol for c in out] == ["A", "B"]


def test_find_candidates_excludes_zero_or_positive_positions() -> None:
    analyzer, store = _make_analyzer(prices={"X": 200.0, "Y": 100.0})
    store.add_account(id="t", account_type="Taxable")
    store.add_position(account_id="t", symbol="X", shares=10, cost_basis=100.0)  # gain
    store.add_position(account_id="t", symbol="Y", shares=10, cost_basis=100.0)  # flat

    out = analyzer.find_loss_candidates(min_loss_pct=0.0, min_loss_amount=0.0)
    assert out == []


def test_find_candidates_ignores_short_positions() -> None:
    analyzer, store = _make_analyzer(prices={"X": 50.0})
    store.add_account(id="t", account_type="Taxable")
    store.add_position(
        account_id="t",
        symbol="X",
        shares=10,
        cost_basis=100.0,
        position_type="short",
    )
    assert analyzer.find_loss_candidates(min_loss_pct=0.0, min_loss_amount=0.0) == []


def test_find_candidates_skips_positions_without_price() -> None:
    analyzer, store = _make_analyzer(prices={"X": 50.0})  # no Y
    store.add_account(id="t", account_type="Taxable")
    store.add_position(account_id="t", symbol="X", shares=10, cost_basis=100.0)
    store.add_position(account_id="t", symbol="Y", shares=10, cost_basis=100.0)

    out = analyzer.find_loss_candidates(min_loss_pct=0.0, min_loss_amount=0.0)
    assert [c.symbol for c in out] == ["X"]


def test_find_candidates_detail_populates_lt_st_split() -> None:
    today = date.today()
    analyzer, store = _make_analyzer(prices={"AAPL": 100.0})
    store.add_account(id="t", account_type="Taxable")
    store.add_position(account_id="t", symbol="AAPL", shares=20, cost_basis=200.0)
    # Long-term lot: acquired 400 days ago (10 shares).
    store.add_lot(
        account_id="t",
        symbol="AAPL",
        acquired_date=today - timedelta(days=400),
        shares=10,
        cost_per_share=200.0,
    )
    # Short-term lot: acquired 60 days ago (10 shares).
    store.add_lot(
        account_id="t",
        symbol="AAPL",
        acquired_date=today - timedelta(days=60),
        shares=10,
        cost_per_share=200.0,
    )

    out = analyzer.find_loss_candidates(
        min_loss_pct=0.0, min_loss_amount=0.0, detail=True
    )
    assert len(out) == 1
    cand = out[0]
    assert cand.holding_period_days == 400
    # Each lot: (100-200) * 10 = -1000 loss.
    assert cand.realized_loss_long_term == pytest.approx(-1000.0)
    assert cand.realized_loss_short_term == pytest.approx(-1000.0)


def test_find_candidates_falls_back_when_no_lots() -> None:
    analyzer, store = _make_analyzer(prices={"AAPL": 100.0})
    store.add_account(id="t", account_type="Taxable")
    store.add_position(account_id="t", symbol="AAPL", shares=10, cost_basis=200.0)
    # No lots seeded.

    out = analyzer.find_loss_candidates(
        min_loss_pct=0.0, min_loss_amount=0.0, detail=True
    )
    assert len(out) == 1
    cand = out[0]
    assert cand.holding_period_days is None
    assert cand.realized_loss_long_term == 0.0
    assert cand.realized_loss_short_term == 0.0


# ----------------------------------------------------------------------
# wash_sale_check
# ----------------------------------------------------------------------


def test_wash_sale_negative_when_no_buys_in_window() -> None:
    analyzer, store = _make_analyzer()
    store.add_account(id="t", account_type="Taxable")

    verdict = analyzer.wash_sale_check(
        symbol="AAPL", sell_date=date(2026, 6, 1), household_id=None
    )
    assert isinstance(verdict, WashSaleVerdict)
    assert verdict.blocked is False
    assert verdict.conflicting_buys == []
    assert verdict.substantially_identical is False


def test_wash_sale_positive_for_tax_advantaged_account() -> None:
    """Roth buy 20 days before a Taxable sell triggers wash-sale (Rev. Rul. 2008-5)."""
    analyzer, store = _make_analyzer()
    store.add_account(id="taxable", account_type="Taxable")
    store.add_account(id="roth", account_type="Roth")
    sell_date = date(2026, 6, 1)
    store.add_buy(
        account_id="roth",
        symbol="AAPL",
        trade_date=sell_date - timedelta(days=20),
        shares=5,
        price=180.0,
    )

    verdict = analyzer.wash_sale_check(
        symbol="AAPL", sell_date=sell_date, household_id=None
    )
    assert verdict.blocked is True
    assert len(verdict.conflicting_buys) == 1
    conflict = verdict.conflicting_buys[0]
    assert conflict.account_id == "roth"
    assert conflict.account_type == "Roth"
    assert conflict.days_offset == -20


def test_wash_sale_positive_for_spouse_account() -> None:
    analyzer, store = _make_analyzer()
    store.add_account(id="me", account_type="Taxable")
    store.add_account(id="spouse", account_type="Taxable", is_spouse=True)
    sell_date = date(2026, 6, 1)
    store.add_buy(
        account_id="spouse",
        symbol="AAPL",
        trade_date=sell_date + timedelta(days=5),
        shares=5,
        price=180.0,
    )

    verdict = analyzer.wash_sale_check(
        symbol="AAPL", sell_date=sell_date, household_id=None
    )
    assert verdict.blocked is True
    assert verdict.conflicting_buys[0].account_id == "spouse"
    assert verdict.conflicting_buys[0].days_offset == 5


def test_wash_sale_substantially_identical_etf_pair() -> None:
    """Selling VTI and buying ITOT inside the window flags substantially identical."""
    analyzer, store = _make_analyzer()
    store.add_account(id="taxable", account_type="Taxable")
    sell_date = date(2026, 6, 1)
    store.add_buy(
        account_id="taxable",
        symbol="ITOT",
        trade_date=sell_date - timedelta(days=10),
        shares=10,
        price=80.0,
    )

    verdict = analyzer.wash_sale_check(
        symbol="VTI", sell_date=sell_date, household_id=None
    )
    assert verdict.blocked is True
    assert verdict.substantially_identical is True
    assert verdict.conflicting_buys[0].txn_id  # populated


def test_wash_sale_ignores_buys_outside_30_day_window() -> None:
    analyzer, store = _make_analyzer()
    store.add_account(id="t", account_type="Taxable")
    sell_date = date(2026, 6, 1)
    store.add_buy(
        account_id="t",
        symbol="AAPL",
        trade_date=sell_date - timedelta(days=31),
        shares=5,
        price=180.0,
    )
    store.add_buy(
        account_id="t",
        symbol="AAPL",
        trade_date=sell_date + timedelta(days=31),
        shares=5,
        price=180.0,
    )

    verdict = analyzer.wash_sale_check(
        symbol="AAPL", sell_date=sell_date, household_id=None
    )
    assert verdict.blocked is False


# ----------------------------------------------------------------------
# suggest_replacement
# ----------------------------------------------------------------------


def test_suggest_replacement_hit() -> None:
    analyzer, _ = _make_analyzer()
    repl = analyzer.suggest_replacement("VTI")
    assert isinstance(repl, ReplacementSecurity)
    assert repl.to_symbol == "ITOT"
    assert repl.confidence == "close"


def test_suggest_replacement_bidirectional() -> None:
    analyzer, _ = _make_analyzer()
    repl = analyzer.suggest_replacement("ITOT")
    assert repl is not None
    assert repl.to_symbol == "VTI"


def test_suggest_replacement_miss() -> None:
    analyzer, _ = _make_analyzer()
    assert analyzer.suggest_replacement("ZZZZ") is None


def test_candidate_is_pydantic_contract() -> None:
    analyzer, store = _make_analyzer(prices={"AAPL": 100.0})
    store.add_account(id="t", account_type="Taxable")
    store.add_position(account_id="t", symbol="AAPL", shares=10, cost_basis=200.0)

    out = analyzer.find_loss_candidates(min_loss_pct=0.0, min_loss_amount=0.0)
    assert isinstance(out[0], TLHCandidate)
    assert out[0].schema_version == 1
