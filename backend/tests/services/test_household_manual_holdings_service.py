"""Tests for ManualHoldingsService.

Covers percent→shares conversion against the account value, the
shares-passthrough path, the SnapTrade edit guard, find-or-create linkage of
the portfolio account, and validation failures (unpriced symbol, percent
without account_value, percent total > 100).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.household_manual_holdings_service import (
    ManualHoldingEntry,
    ManualHoldingsReplaceRequest,
    ManualHoldingsService,
)


class _Cursor:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows

    def fetchone(self) -> tuple | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[tuple]:
        return self.rows


class _Conn:
    """Records writes; answers reads from a small route table."""

    def __init__(self, routes: dict[str, list[tuple]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, list]] = []

    def execute(self, query: str, params: list | None = None) -> _Cursor:
        self.calls.append((" ".join(query.split()), params or []))
        for needle, rows in self.routes.items():
            if needle in query:
                return _Cursor(rows)
        return _Cursor([])

    def commit(self) -> None:
        pass


class _Storage:
    def __init__(self, routes: dict[str, list[tuple]]) -> None:
        self.routes = routes
        self.conns: list[_Conn] = []

    def connection(self) -> Any:
        storage = self

        class _Ctx:
            def __enter__(self) -> _Conn:
                conn = _Conn(storage.routes)
                storage.conns.append(conn)
                return conn

            def __exit__(self, *_a: Any) -> None:
                pass

        return _Ctx()

    def all_calls(self) -> list[tuple[str, list]]:
        return [call for conn in self.conns for call in conn.calls]


def _service(
    routes: dict[str, list[tuple]], prices: dict[str, float]
) -> tuple[ManualHoldingsService, _Storage]:
    storage = _Storage(routes)
    service = ManualHoldingsService(storage=storage)
    service._fetch_prices = lambda symbols: {  # type: ignore[method-assign]
        s: MagicMock(price=prices[s], error=None) for s in symbols if s in prices
    }
    return service, storage


_HH_ROUTES = {
    "FROM household_accounts": [("FRS Investment Plan", "retirement")],
    "FROM portfolio_accounts": [],
    "FROM portfolio_positions": [],
}


def test_percent_entries_convert_to_shares_using_account_value() -> None:
    service, storage = _service(dict(_HH_ROUTES), {"VTI": 200.0, "BND": 50.0})
    service.replace_holdings(
        "hh-frs",
        ManualHoldingsReplaceRequest(
            entries=[
                ManualHoldingEntry(symbol="VTI", percent=60.0),
                ManualHoldingEntry(symbol="BND", percent=40.0),
            ],
            account_value=100_000.0,
        ),
    )
    inserts = [c for c in storage.all_calls() if "INSERT INTO portfolio_positions" in c[0]]
    assert len(inserts) == 2
    by_symbol = {call[1][2]: call[1] for call in inserts}
    # 60% of 100k at $200 = 300 shares; 40% of 100k at $50 = 800 shares.
    assert by_symbol["VTI"][3] == pytest.approx(300.0)
    assert by_symbol["BND"][3] == pytest.approx(800.0)


def test_shares_entries_pass_through_and_replace_existing() -> None:
    routes = dict(_HH_ROUTES)
    routes["FROM portfolio_accounts"] = [("manual-acct-1",)]
    service, storage = _service(routes, {"VTI": 200.0})
    service.replace_holdings(
        "hh-frs",
        ManualHoldingsReplaceRequest(
            entries=[ManualHoldingEntry(symbol="vti", shares=123.45)],
        ),
    )
    calls = storage.all_calls()
    deletes = [c for c in calls if "DELETE FROM portfolio_positions" in c[0]]
    inserts = [c for c in calls if "INSERT INTO portfolio_positions" in c[0]]
    account_creates = [c for c in calls if "INSERT INTO portfolio_accounts" in c[0]]
    assert len(deletes) == 1 and deletes[0][1] == ["manual-acct-1"]
    assert len(inserts) == 1
    assert inserts[0][1][2] == "VTI"
    assert inserts[0][1][3] == pytest.approx(123.45)
    assert not account_creates  # reused the linked account


def test_creates_portfolio_account_linked_to_household_account() -> None:
    service, storage = _service(dict(_HH_ROUTES), {"VTI": 200.0})
    service.replace_holdings(
        "hh-frs",
        ManualHoldingsReplaceRequest(
            entries=[ManualHoldingEntry(symbol="VTI", shares=10.0)],
        ),
    )
    creates = [
        c for c in storage.all_calls() if "INSERT INTO portfolio_accounts" in c[0]
    ]
    assert len(creates) == 1
    params = creates[0][1]
    assert params[1] == "FRS Investment Plan"
    assert params[2] == "IRA"  # retirement → pre-tax bucket account type
    assert params[3] == "hh-frs"


def test_snaptrade_linked_account_rejects_manual_edit() -> None:
    routes = dict(_HH_ROUTES)
    routes["FROM portfolio_accounts"] = [("snaptrade:abc",)]
    service, _ = _service(routes, {"VTI": 200.0})
    with pytest.raises(ValueError, match="SnapTrade"):
        service.replace_holdings(
            "hh-frs",
            ManualHoldingsReplaceRequest(
                entries=[ManualHoldingEntry(symbol="VTI", shares=1.0)],
            ),
        )


def test_unknown_household_account_raises_lookup_error() -> None:
    routes = dict(_HH_ROUTES)
    routes["FROM household_accounts"] = []
    service, _ = _service(routes, {})
    with pytest.raises(LookupError):
        service.get_holdings("missing")


def test_percent_without_account_value_rejected() -> None:
    service, _ = _service(dict(_HH_ROUTES), {"VTI": 200.0})
    with pytest.raises(ValueError, match="account_value"):
        service.replace_holdings(
            "hh-frs",
            ManualHoldingsReplaceRequest(
                entries=[ManualHoldingEntry(symbol="VTI", percent=50.0)],
            ),
        )


def test_percent_total_above_100_rejected() -> None:
    service, _ = _service(dict(_HH_ROUTES), {"VTI": 200.0, "BND": 50.0})
    with pytest.raises(ValueError, match="exceed 100"):
        service.replace_holdings(
            "hh-frs",
            ManualHoldingsReplaceRequest(
                entries=[
                    ManualHoldingEntry(symbol="VTI", percent=70.0),
                    ManualHoldingEntry(symbol="BND", percent=40.0),
                ],
                account_value=10_000.0,
            ),
        )


def test_unpriced_symbol_names_proxy_guidance() -> None:
    service, _ = _service(dict(_HH_ROUTES), {"VTI": 200.0})
    with pytest.raises(ValueError, match="FRSXX.*proxy"):
        service.replace_holdings(
            "hh-frs",
            ManualHoldingsReplaceRequest(
                entries=[ManualHoldingEntry(symbol="FRSXX", shares=10.0)],
            ),
        )


def test_entry_requires_exactly_one_of_shares_or_percent() -> None:
    with pytest.raises(ValueError):
        ManualHoldingEntry(symbol="VTI")
    with pytest.raises(ValueError):
        ManualHoldingEntry(symbol="VTI", shares=1.0, percent=10.0)
