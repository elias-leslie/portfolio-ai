"""Unit tests for cadence-based shopping-list suggestions."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

from app.services.household_shopping_list_service import HouseholdShoppingListService


class _Rows:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class _Conn:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.queries: list[tuple[str, list[Any]]] = []

    def execute(self, sql: str, params: list[Any] | None = None) -> _Rows:
        self.queries.append((sql, params or []))
        return _Rows(self.rows if "purchase_events AS" in sql else [])


class _Storage:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


def _service(conn: _Conn) -> HouseholdShoppingListService:
    service = HouseholdShoppingListService()
    service.storage = _Storage(conn)
    return service


def test_suggested_items_bucket_and_default_selection() -> None:
    conn = _Conn(
        [
            (
                "prod-honey",
                "Raw Honey 32 oz",
                6,
                date(2026, 1, 1),
                date(2026, 6, 1),
                14.0,
                2.0,
                date(2026, 6, 15),
                -4,
                120.0,
                0.9,
                "Groceries",
                "Amazon",
                12.99,
                "32 oz",
                "weight_oz",
                False,
            ),
            (
                "prod-coffee",
                "Peet's Coffee 18 oz",
                5,
                date(2026, 1, 10),
                date(2026, 6, 1),
                35.0,
                10.0,
                date(2026, 6, 30),
                11,
                80.0,
                0.8,
                "Groceries",
                "Amazon",
                15.99,
                "18 ounces",
                "weight_oz",
                False,
            ),
            (
                "prod-cat",
                "Cat Litter",
                4,
                date(2026, 1, 5),
                date(2026, 6, 1),
                45.0,
                24.0,
                date(2026, 7, 16),
                27,
                160.0,
                0.7,
                "Pet",
                "Walmart",
                27.99,
                "40 lb",
                "weight_oz",
                True,
            ),
        ]
    )

    result = _service(conn).suggested_items(days_ahead=14, watch_days=45, limit=10)

    assert result.item_count == 3
    assert result.buy_now_count == 1
    assert result.soon_count == 1
    assert result.watch_count == 1
    honey, coffee, cat_litter = result.items
    assert honey.due_bucket == "buy_now"
    assert honey.selected_by_default is True
    assert honey.unit_label == "oz"
    assert "Overdue by 4 days" in honey.reason
    assert coffee.due_bucket == "soon"
    assert coffee.selected_by_default is True
    assert cat_litter.due_bucket == "watch"
    assert cat_litter.already_on_open_list is True
    assert cat_litter.selected_by_default is False
    sql, params = conn.queries[0]
    assert "GROUP BY p.id, p.canonical_name, i.purchase_date::date" in sql
    assert params == [365, 3, 45, 10]
