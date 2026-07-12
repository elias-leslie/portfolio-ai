"""Canonical household allocation coverage tests."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from app.portfolio.asset_classification import AssetClassifier
from app.services.household_allocation_service import HouseholdAllocationService


class _Result:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class _Connection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def execute(self, _query: str, _params: object = None) -> _Result:
        return _Result(self.rows)


class _Storage:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    @contextmanager
    def connection(self):
        yield _Connection(self.rows)


class _PriceFetcher:
    def __init__(self, prices: dict[str, float]) -> None:
        self.prices = prices

    def fetch_cached_price_data(self, symbols: list[str]):
        return {
            symbol: SimpleNamespace(symbol=symbol, price=self.prices[symbol], error=None)
            for symbol in symbols
            if symbol in self.prices
        }


def _account(
    *,
    label: str,
    value: float,
    linked_id: str | None,
    cash: float = 0.0,
    household_id: str | None = "hh-1",
) -> SimpleNamespace:
    return SimpleNamespace(
        asset_group="taxable",
        current_value=value,
        label=label,
        household_account_id=household_id,
        linked_portfolio_account_id=linked_id,
        cash_balance=cash,
    )


def _dashboard(
    accounts: list[SimpleNamespace],
    *,
    invested_assets: float,
    blocking: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        accounts=accounts,
        overview=SimpleNamespace(invested_assets=invested_assets),
        account_control=SimpleNamespace(blocking_issue_count=blocking),
    )


def test_build_reconciles_unknown_account_value_into_unclassified() -> None:
    service = HouseholdAllocationService(
        _Storage([("acct-1", "VTI", 6.0)]),
        AssetClassifier(None),
        _PriceFetcher({"VTI": 100.0}),
    )

    universe = service.build(
        _dashboard(
            [
                _account(label="Brokerage", value=1_000.0, linked_id="acct-1", cash=100.0),
                _account(label="Work plan", value=500.0, linked_id=None, household_id="hh-2"),
            ],
            invested_assets=1_500.0,
        )
    )

    assert universe.status == "partial"
    assert universe.total_value == 1_500.0
    assert universe.by_class == {
        "cash": 100.0,
        "us_equity": 600.0,
        "unclassified": 800.0,
    }
    assert universe.exact_value == 700.0
    assert universe.unclassified_value == 800.0
    assert len(universe.accounts) == 2


def test_build_marks_exact_cash_and_holdings_complete() -> None:
    service = HouseholdAllocationService(
        _Storage([("acct-1", "VTI", 9.0)]),
        AssetClassifier(None),
        _PriceFetcher({"VTI": 100.0}),
    )

    universe = service.build(
        _dashboard(
            [_account(label="Brokerage", value=1_000.0, linked_id="acct-1", cash=100.0)],
            invested_assets=1_000.0,
        )
    )

    assert universe.status == "complete"
    assert universe.coverage_pct == 1.0
    assert universe.by_class == {"cash": 100.0, "us_equity": 900.0}
    assert universe.unclassified_value == 0.0


def test_build_treats_exactly_one_percent_missing_as_partial() -> None:
    service = HouseholdAllocationService(
        _Storage([("acct-1", "VTI", 99.0)]),
        AssetClassifier(None),
        _PriceFetcher({"VTI": 100.0}),
    )

    universe = service.build(
        _dashboard(
            [_account(label="Brokerage", value=10_000.0, linked_id="acct-1")],
            invested_assets=10_000.0,
        )
    )

    assert universe.status == "partial"
    assert universe.coverage_pct == 0.99
    assert universe.unclassified_value == 100.0
    assert universe.by_class == {
        "us_equity": 9_900.0,
        "unclassified": 100.0,
    }


def test_build_keeps_account_control_as_blocking_authority() -> None:
    service = HouseholdAllocationService(
        _Storage([("acct-1", "VTI", 9.0)]),
        AssetClassifier(None),
        _PriceFetcher({"VTI": 100.0}),
    )

    universe = service.build(
        _dashboard(
            [_account(label="Brokerage", value=1_000.0, linked_id="acct-1", cash=100.0)],
            invested_assets=1_000.0,
            blocking=1,
        )
    )

    assert universe.status == "blocked"
    assert "account-control issue" in universe.message


def test_build_flags_material_position_value_over_account_balance() -> None:
    service = HouseholdAllocationService(
        _Storage([("acct-1", "VTI", 12.0)]),
        AssetClassifier(None),
        _PriceFetcher({"VTI": 100.0}),
    )

    universe = service.build(
        _dashboard(
            [_account(label="Brokerage", value=1_000.0, linked_id="acct-1")],
            invested_assets=1_000.0,
        )
    )

    assert universe.status == "mismatch"
    assert universe.by_class == {"us_equity": 1_000.0}
    assert universe.accounts[0].mismatch is True
