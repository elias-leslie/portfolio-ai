"""Unit tests for IPSService, AssetClassifier, and DriftCalculator.

Uses an in-memory PG-shaped fake (mirroring the pattern in
``test_tlh.py``) so the math can be exercised without a database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

import pytest

from app.portfolio import asset_classification
from app.portfolio.asset_classification import AssetClassifier, HoldingValue
from app.portfolio.contracts.ips import IPSScope, IPSTarget
from app.portfolio.ips import (
    DriftCalculator,
    IPSService,
)
from app.portfolio.models import PriceData


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]], *, rowcount: int = 0) -> None:
        self._rows = list(rows)
        self.rowcount = rowcount

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

    def execute(self, query: str, params: Iterable[Any] | None = None) -> _FakeConn:
        params_list = list(params) if params is not None else []
        normalized = " ".join(query.split())
        rows, rowcount = self.store.handle(normalized, params_list)
        self._last = _Cursor(rows, rowcount=rowcount)
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        assert self._last is not None
        return self._last.fetchall()

    def fetchone(self) -> tuple[Any, ...] | None:
        assert self._last is not None
        return self._last.fetchone()

    def commit(self) -> None:
        self.commit_count += 1

    @property
    def rowcount(self) -> int:
        return self._last.rowcount if self._last else 0


class _FakeStore:
    def __init__(self) -> None:
        self.targets: list[dict[str, Any]] = []
        self.accounts: list[dict[str, Any]] = []
        self.positions: list[dict[str, Any]] = []

    # --- helpers ---
    def add_account(
        self,
        *,
        id: str,
        account_type: str,
        is_spouse: bool = False,
        cash_balance: float = 0.0,
    ) -> None:
        self.accounts.append(
            {
                "id": id,
                "account_type": account_type,
                "is_spouse": is_spouse,
                "cash_balance": cash_balance,
            }
        )

    def add_position(self, *, account_id: str, symbol: str, shares: float, cost_basis: float) -> None:
        self.positions.append(
            {
                "account_id": account_id,
                "symbol": symbol.upper(),
                "shares": shares,
                "cost_basis": cost_basis,
                "position_type": "long",
            }
        )

    # --- query handler ---
    def handle(  # noqa: PLR0911 — naturally a SQL-dispatch fixture; clarity > merging branches
        self, query: str, params: list[Any]
    ) -> tuple[list[tuple[Any, ...]], int]:
        q = query.upper()

        if q.startswith("SELECT SCOPE, SCOPE_ID, ASSET_CLASS, TARGET_PCT"):
            scope, scope_id = params
            rows = sorted(
                [t for t in self.targets if t["scope"] == scope and t["scope_id"] == scope_id],
                key=lambda t: t["asset_class"],
            )
            return [
                (
                    t["scope"],
                    t["scope_id"],
                    t["asset_class"],
                    t["target_pct"],
                    t["drift_band_pct"],
                    t.get("notes"),
                )
                for t in rows
            ], 0

        if q.startswith("SELECT DISTINCT SCOPE, SCOPE_ID FROM IPS_TARGETS"):
            distinct = sorted({(t["scope"], t["scope_id"]) for t in self.targets})
            return [(s, sid) for s, sid in distinct], 0

        if q.startswith("INSERT INTO IPS_TARGETS"):
            (
                _id,
                scope,
                scope_id,
                asset_class,
                target_pct,
                drift_band_pct,
                notes,
            ) = params
            for existing in self.targets:
                if (
                    existing["scope"] == scope
                    and existing["scope_id"] == scope_id
                    and existing["asset_class"] == asset_class
                ):
                    existing.update(
                        {
                            "target_pct": target_pct,
                            "drift_band_pct": drift_band_pct,
                            "notes": notes,
                        }
                    )
                    return [], 1
            self.targets.append(
                {
                    "id": _id,
                    "scope": scope,
                    "scope_id": scope_id,
                    "asset_class": asset_class,
                    "target_pct": target_pct,
                    "drift_band_pct": drift_band_pct,
                    "notes": notes,
                }
            )
            return [], 1

        if q.startswith("DELETE FROM IPS_TARGETS"):
            scope, scope_id, asset_class = params
            before = len(self.targets)
            self.targets = [
                t
                for t in self.targets
                if not (
                    t["scope"] == scope
                    and t["scope_id"] == scope_id
                    and t["asset_class"] == asset_class
                )
            ]
            return [], before - len(self.targets)

        if q.startswith("SELECT ID, ACCOUNT_TYPE, COALESCE(IS_SPOUSE"):
            if "WHERE ID = %S" in q:
                (account_id,) = params
                acc = next((a for a in self.accounts if a["id"] == account_id), None)
                if acc is None:
                    return [], 0
                return [
                    (
                        acc["id"],
                        acc["account_type"],
                        acc["is_spouse"],
                        acc["cash_balance"],
                    )
                ], 0
            return [
                (a["id"], a["account_type"], a["is_spouse"], a["cash_balance"])
                for a in self.accounts
                if a["account_type"] != "paper"
            ], 0

        if q.startswith("SELECT ACCOUNT_ID, SYMBOL, SHARES, COST_BASIS"):
            return [
                (p["account_id"], p["symbol"], p["shares"], p["cost_basis"])
                for p in self.positions
                if p["position_type"] == "long" and p["shares"] > 0
            ], 0

        raise AssertionError(f"unhandled query: {query[:160]} ; params={params!r}")


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


# ----------------------------------------------------------------------
# IPSService
# ----------------------------------------------------------------------


def test_set_and_get_targets_round_trip() -> None:
    storage = _FakeStorage()
    svc = IPSService(storage)
    svc.set_target(scope="household", scope_id="hh1", asset_class="us_equity", target_pct=0.6)
    svc.set_target(
        scope="household",
        scope_id="hh1",
        asset_class="bonds",
        target_pct=0.3,
        drift_band_pct=0.10,
        notes="loosen bonds band",
    )
    targets = svc.get_targets("household", "hh1")
    assert [t.asset_class for t in targets] == ["bonds", "us_equity"]
    assert targets[0].drift_band_pct == 0.10
    assert targets[0].notes == "loosen bonds band"


def test_set_target_upsert_overwrites_existing() -> None:
    storage = _FakeStorage()
    svc = IPSService(storage)
    svc.set_target(scope="household", scope_id="hh1", asset_class="us_equity", target_pct=0.6)
    svc.set_target(scope="household", scope_id="hh1", asset_class="us_equity", target_pct=0.5)
    targets = svc.get_targets("household", "hh1")
    assert len(targets) == 1
    assert targets[0].target_pct == 0.5


def test_set_target_validates_ranges() -> None:
    storage = _FakeStorage()
    svc = IPSService(storage)
    with pytest.raises(ValueError):
        svc.set_target(scope="household", scope_id="hh1", asset_class="us_equity", target_pct=1.5)
    with pytest.raises(ValueError):
        svc.set_target(
            scope="household",
            scope_id="hh1",
            asset_class="us_equity",
            target_pct=0.5,
            drift_band_pct=2.0,
        )
    with pytest.raises(ValueError):
        svc.set_target(scope="weird", scope_id="hh1", asset_class="us_equity", target_pct=0.5)


def test_delete_target_removes_row() -> None:
    storage = _FakeStorage()
    svc = IPSService(storage)
    svc.set_target(scope="household", scope_id="hh1", asset_class="us_equity", target_pct=0.6)
    assert svc.delete_target(scope="household", scope_id="hh1", asset_class="us_equity") is True
    assert svc.get_targets("household", "hh1") == []


def test_list_scopes_returns_distinct_pairs() -> None:
    storage = _FakeStorage()
    svc = IPSService(storage)
    svc.set_target(scope="household", scope_id="hh1", asset_class="us_equity", target_pct=0.6)
    svc.set_target(scope="household", scope_id="hh1", asset_class="bonds", target_pct=0.4)
    svc.set_target(scope="account", scope_id="acct-1", asset_class="us_equity", target_pct=0.7)
    scopes = svc.list_scopes()
    assert ("account", "acct-1") in scopes
    assert ("household", "hh1") in scopes
    assert len(scopes) == 2


# ----------------------------------------------------------------------
# AssetClassifier
# ----------------------------------------------------------------------


def test_classifier_uses_explicit_table() -> None:
    classifier = AssetClassifier(storage=None)  # explicit-only path
    out = classifier.classify_value(
        [
            HoldingValue(symbol="VTI", value=6000.0),
            HoldingValue(symbol="VXUS", value=2000.0),
            HoldingValue(symbol="BND", value=2000.0),
        ]
    )
    assert out.total_value == 10000.0
    assert out.by_class == {"us_equity": 6000.0, "intl_equity": 2000.0, "bonds": 2000.0}
    assert out.unclassified_value == 0.0


def test_classifier_buckets_unknown_as_unclassified() -> None:
    classifier = AssetClassifier(storage=None)
    out = classifier.classify_value([HoldingValue(symbol="ZZZWEIRD", value=1000.0)])
    assert out.total_value == 1000.0
    assert out.by_class == {"unclassified": 1000.0}
    assert out.unclassified_value == 1000.0


def test_classifier_primary_class_for_explicit_symbol() -> None:
    classifier = AssetClassifier(storage=None)
    assert classifier.primary_class("BND") == "bonds"
    assert classifier.primary_class("VXUS") == "intl_equity"
    assert classifier.primary_class("SPAXX") == "cash"
    assert classifier.primary_class("ZZZ") == "unclassified"


def test_classifier_skips_lookthrough_for_explicit_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_lookthrough(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("explicit symbols should not need fund look-through")

    monkeypatch.setattr(asset_classification, "get_fund_lookthroughs", fail_lookthrough)
    classifier = AssetClassifier(storage=_FakeStorage())
    out = classifier.classify_value(
        [
            HoldingValue(symbol="VTI", value=70.0),
            HoldingValue(symbol="SCHD", value=10.0),
            HoldingValue(symbol="BND", value=10.0),
            HoldingValue(symbol="SPAXX", value=10.0),
        ]
    )
    assert out.by_class == {"us_equity": 80.0, "bonds": 10.0, "cash": 10.0}


# ----------------------------------------------------------------------
# DriftCalculator
# ----------------------------------------------------------------------


def _make_drift(
    *,
    targets: list[tuple[str, float, float]],
    accounts: list[tuple[str, str]],
    positions: list[tuple[str, str, float, float]],
    prices: dict[str, float],
) -> tuple[DriftCalculator, IPSService, _FakeStore]:
    storage = _FakeStorage()
    store = storage.store
    for acct_id, acct_type in accounts:
        store.add_account(id=acct_id, account_type=acct_type)
    for acct_id, symbol, shares, cost in positions:
        store.add_position(account_id=acct_id, symbol=symbol, shares=shares, cost_basis=cost)
    ips = IPSService(storage)
    for asset_class, target_pct, band in targets:
        ips.set_target(
            scope="household",
            scope_id="hh1",
            asset_class=asset_class,
            target_pct=target_pct,
            drift_band_pct=band,
        )
    classifier = AssetClassifier(storage=None)  # explicit-only for determinism
    calc = DriftCalculator(storage, classifier, ips, _FakePriceFetcher(prices))
    return calc, ips, store


def test_drift_report_balanced_portfolio_in_band() -> None:
    calc, _, _ = _make_drift(
        targets=[("us_equity", 0.6, 0.05), ("bonds", 0.4, 0.05)],
        accounts=[("acct-tax", "Taxable")],
        positions=[("acct-tax", "VTI", 60.0, 100.0), ("acct-tax", "BND", 40.0, 100.0)],
        prices={"VTI": 100.0, "BND": 100.0},
    )
    report = calc.compute_drift("household", "hh1", snapshot_date=date(2026, 5, 9))
    assert report.total_value == 10000.0
    by_class = {r.asset_class: r for r in report.rows}
    assert pytest.approx(by_class["us_equity"].drift_pct, abs=1e-6) == 0.0
    assert pytest.approx(by_class["bonds"].drift_pct, abs=1e-6) == 0.0
    assert by_class["us_equity"].out_of_band is False
    assert by_class["bonds"].out_of_band is False


def test_drift_report_overweight_us_equity_marked_out_of_band() -> None:
    calc, _, _ = _make_drift(
        targets=[("us_equity", 0.5, 0.05), ("bonds", 0.5, 0.05)],
        accounts=[("acct-tax", "Taxable")],
        positions=[("acct-tax", "VTI", 80.0, 100.0), ("acct-tax", "BND", 20.0, 100.0)],
        prices={"VTI": 100.0, "BND": 100.0},
    )
    report = calc.compute_drift("household", "hh1", snapshot_date=date(2026, 5, 9))
    by_class = {r.asset_class: r for r in report.rows}
    assert by_class["us_equity"].out_of_band is True
    assert by_class["bonds"].out_of_band is True
    assert pytest.approx(by_class["us_equity"].drift_pct, abs=1e-6) == 0.30
    assert pytest.approx(by_class["bonds"].drift_pct, abs=1e-6) == -0.30


def test_drift_summary_max_drift_and_oob_count() -> None:
    calc, _, _ = _make_drift(
        targets=[
            ("us_equity", 0.5, 0.05),
            ("bonds", 0.3, 0.05),
            ("intl_equity", 0.2, 0.05),
        ],
        accounts=[("acct-tax", "Taxable")],
        positions=[
            ("acct-tax", "VTI", 80.0, 100.0),
            ("acct-tax", "BND", 10.0, 100.0),
            ("acct-tax", "VXUS", 10.0, 100.0),
        ],
        prices={"VTI": 100.0, "BND": 100.0, "VXUS": 100.0},
    )
    digest = calc.compute_summary("household", "hh1", snapshot_date=date(2026, 5, 9))
    assert digest.classes_out_of_band == 3
    assert pytest.approx(digest.max_drift_pct, abs=1e-6) == 0.30


def test_drift_marks_classes_present_but_missing_targets() -> None:
    calc, _, _ = _make_drift(
        targets=[("us_equity", 1.0, 0.05)],
        accounts=[("acct-tax", "Taxable")],
        positions=[
            ("acct-tax", "VTI", 50.0, 100.0),
            ("acct-tax", "BND", 50.0, 100.0),
        ],
        prices={"VTI": 100.0, "BND": 100.0},
    )
    report = calc.compute_drift("household", "hh1", snapshot_date=date(2026, 5, 9))
    assert "bonds" in report.classes_missing_targets
    by_class = {row.asset_class: row for row in report.rows}
    assert by_class["bonds"].out_of_band is False


def test_drift_includes_account_cash_in_allocation_and_total() -> None:
    calc, _, store = _make_drift(
        targets=[("us_equity", 0.55, 0.05), ("cash", 0.45, 0.05)],
        accounts=[("acct-tax", "Taxable")],
        positions=[("acct-tax", "VTI", 11.0, 100.0)],
        prices={"VTI": 100.0},
    )
    store.accounts[0]["cash_balance"] = 900.0

    report = calc.compute_drift("household", "hh1", snapshot_date=date(2026, 5, 9))

    by_class = {row.asset_class: row for row in report.rows}
    assert report.total_value == 2000.0
    assert by_class["cash"].actual_value == 900.0
    assert by_class["cash"].actual_pct == 0.45
    assert by_class["cash"].out_of_band is False


def test_drift_uses_only_account_in_account_scope() -> None:
    calc, ips, _ = _make_drift(
        targets=[("us_equity", 1.0, 0.05)],
        accounts=[("acct-a", "Taxable"), ("acct-b", "Roth")],
        positions=[
            ("acct-a", "VTI", 50.0, 100.0),
            ("acct-b", "VTI", 50.0, 100.0),
        ],
        prices={"VTI": 100.0},
    )
    # Reset targets to account scope.
    ips.delete_target(scope="household", scope_id="hh1", asset_class="us_equity")
    ips.set_target(scope="account", scope_id="acct-a", asset_class="us_equity", target_pct=1.0)
    report = calc.compute_drift("account", "acct-a", snapshot_date=date(2026, 5, 9))
    assert report.total_value == 5000.0


def test_drift_handles_empty_portfolio() -> None:
    calc, _, _ = _make_drift(
        targets=[("us_equity", 1.0, 0.05)],
        accounts=[("acct-tax", "Taxable")],
        positions=[],
        prices={},
    )
    report = calc.compute_drift("household", "hh1", snapshot_date=date(2026, 5, 9))
    assert report.total_value == 0.0
    # Single targeted class, no actual data → drift = 0 - 1.0 = -1.0
    by_class = {r.asset_class: r for r in report.rows}
    assert by_class["us_equity"].actual_pct == 0.0
    assert by_class["us_equity"].target_pct == 1.0


# Suppress unused import warning when pytest collects this file.
_ = uuid
_ = IPSScope
_ = IPSTarget
