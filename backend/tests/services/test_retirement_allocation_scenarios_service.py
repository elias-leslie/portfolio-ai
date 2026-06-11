"""Tests for AllocationScenariosService.

Covers insert/update/delete dispatch in replace_scenarios, the
delete-before-insert ordering that frees unique names, JSON holdings
round-trip, and duplicate-name validation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.services.retirement_allocation_scenarios_service import (
    AllocationScenarioHolding,
    AllocationScenarioInput,
    AllocationScenariosReplaceRequest,
    AllocationScenariosService,
)


class _Cursor:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows

    def fetchone(self) -> tuple | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[tuple]:
        return self.rows


class _Conn:
    def __init__(self, routes: dict[str, list[tuple]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, list]] = []

    def execute(self, query: str, params: list | None = None) -> _Cursor:
        normalized = " ".join(query.split())
        self.calls.append((normalized, params or []))
        for needle, rows in self.routes.items():
            if needle in normalized:
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


_NOW = datetime(2026, 6, 11, tzinfo=UTC)


def _scenario_input(name: str = "All equity", **kwargs: Any) -> AllocationScenarioInput:
    return AllocationScenarioInput(
        name=name,
        holdings=[AllocationScenarioHolding(symbol="VTI", weight=100.0)],
        **kwargs,
    )


def test_replace_inserts_new_scenarios_with_holdings_json() -> None:
    storage = _Storage({"SELECT id FROM": []})
    service = AllocationScenariosService(storage=storage)
    service.replace_scenarios(
        AllocationScenariosReplaceRequest(scenarios=[_scenario_input()])
    )
    inserts = [c for c in storage.all_calls() if c[0].startswith("INSERT INTO")]
    assert len(inserts) == 1
    params = inserts[0][1]
    assert params[1] == "All equity"
    assert json.loads(params[2]) == [{"symbol": "VTI", "weight": 100.0}]


def test_replace_updates_existing_and_deletes_stale_before_insert() -> None:
    storage = _Storage({"SELECT id FROM": [("keep-id",), ("stale-id",)]})
    service = AllocationScenariosService(storage=storage)
    service.replace_scenarios(
        AllocationScenariosReplaceRequest(
            scenarios=[
                _scenario_input("Kept", id="keep-id"),
                _scenario_input("Fresh"),
            ]
        )
    )
    writes = [
        c
        for c in storage.all_calls()
        if c[0].startswith(("INSERT", "UPDATE", "DELETE"))
    ]
    kinds = [c[0].split()[0] for c in writes]
    assert kinds == ["DELETE", "UPDATE", "INSERT"]
    assert writes[0][1] == ["stale-id"]
    assert writes[1][1][-1] == "keep-id"


def test_bridge_overrides_persist() -> None:
    storage = _Storage({"SELECT id FROM": []})
    service = AllocationScenariosService(storage=storage)
    service.replace_scenarios(
        AllocationScenariosReplaceRequest(
            scenarios=[
                _scenario_input(bridge_growth="portfolio", bridge_real_return=0.03)
            ]
        )
    )
    insert = next(c for c in storage.all_calls() if c[0].startswith("INSERT"))
    assert insert[1][3] == "portfolio"
    assert insert[1][4] == 0.03


def test_duplicate_names_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        AllocationScenariosReplaceRequest(
            scenarios=[_scenario_input("Mix"), _scenario_input("  mix ")]
        )


def test_list_scenarios_parses_jsonb_rows() -> None:
    row = (
        "id-1",
        "Mix",
        [{"symbol": "VTI", "weight": 60.0}, {"symbol": "BND", "weight": 40.0}],
        "fixed",
        0.01,
        None,
        _NOW,
        _NOW,
    )
    storage = _Storage({"SELECT id, name, holdings": [row]})
    service = AllocationScenariosService(storage=storage)
    rows = service.list_scenarios()
    assert len(rows) == 1
    assert rows[0].name == "Mix"
    assert [h.symbol for h in rows[0].holdings] == ["VTI", "BND"]
    assert rows[0].bridge_growth == "fixed"
