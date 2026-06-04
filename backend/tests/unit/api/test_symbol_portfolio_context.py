"""Tests for canonical symbol-level portfolio context."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.api.symbols import portfolio_context
from app.api.symbols.builders import build_portfolio_section


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]], columns: list[str]) -> None:
        self._rows = rows
        self.description = [(column,) for column in columns]

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None


class _FakeConnection:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, _params: list[str] | None = None) -> _FakeResult:
        self.queries.append(sql)
        if "GROUP BY UPPER(p.symbol)" in sql:
            return _FakeResult(
                [("VTI", 2482.409, 221.4, 335.73)],
                ["symbol", "shares", "cost_basis", "current_price"],
            )
        if "COUNT(DISTINCT UPPER(p.symbol))" in sql:
            return _FakeResult([(7,)], ["num_holdings"])
        raise AssertionError(f"Unexpected query: {sql}")


class _FakeStorage:
    def __init__(self) -> None:
        self.connection_instance = _FakeConnection()

    def connection(self) -> _FakeConnection:
        return self.connection_instance


def test_symbol_portfolio_context_aggregates_multi_account_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _FakeStorage()
    monkeypatch.setattr(
        portfolio_context,
        "get_fund_lookthroughs",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        portfolio_context,
        "get_effective_portfolio_totals",
        lambda *_args, **_kwargs: SimpleNamespace(
            effective_invested_total_value=851_070.0,
        ),
    )

    positions_by_symbol, summary = portfolio_context.fetch_symbol_portfolio_context(
        storage,
        ["VTI"],
    )
    section = build_portfolio_section(positions_by_symbol["VTI"], summary)

    assert positions_by_symbol["VTI"]["shares"] == pytest.approx(2482.409)
    assert positions_by_symbol["VTI"]["cost_basis"] == pytest.approx(221.4)
    assert summary == {"total_value": 851_070.0, "num_holdings": 7}
    assert section.position is not None
    assert section.position.current_value == pytest.approx(833_419.17)
    assert section.position.weight_pct == pytest.approx(97.926043)
    assert any("a.account_type != 'paper'" in query for query in storage.connection_instance.queries)
    assert any("p.position_type != 'paper'" in query for query in storage.connection_instance.queries)
    assert any("ROW_NUMBER() OVER" in query for query in storage.connection_instance.queries)
    assert not any("MAX(pc.price)" in query for query in storage.connection_instance.queries)


def test_build_portfolio_section_does_not_turn_cost_basis_into_current_price() -> None:
    section = build_portfolio_section(
        {"symbol": "VTI", "shares": 10.0, "cost_basis": 200.0, "current_price": None},
        {"total_value": 10_000.0, "num_holdings": 1},
    )

    assert section.held is True
    assert section.position is not None
    assert section.position.current_value is None
    assert section.position.gain is None
    assert section.position.gain_pct is None
    assert section.position.weight_pct is None
