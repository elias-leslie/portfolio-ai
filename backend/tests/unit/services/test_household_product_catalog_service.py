"""Unit tests for the product catalog / price-history read service."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.household_product_catalog_service import (
    HouseholdProductCatalogService,
)


class _ScriptedConn:
    """Route queries by shape; record params for assertions."""

    def __init__(
        self,
        *,
        product_rows: list[tuple[Any, ...]] | None = None,
        product_detail_row: tuple[Any, ...] | None = None,
        review_count: int = 0,
        price_point_rows: list[tuple[Any, ...]] | None = None,
        observation_rows: list[tuple[Any, ...]] | None = None,
        identifier_rows: list[tuple[Any, ...]] | None = None,
        item_rows: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self.product_rows = product_rows or []
        self.product_detail_row = product_detail_row
        self.review_count = review_count
        self.price_point_rows = price_point_rows or []
        self.observation_rows = observation_rows or []
        self.identifier_rows = identifier_rows or []
        self.item_rows = item_rows or []
        self.queries: list[tuple[str, list[Any]]] = []
        self.committed = 0
        self._result: tuple[str, Any] = ("none", None)

    def execute(self, sql: str, params: list[Any] | None = None) -> _ScriptedConn:
        self.queries.append((sql, params or []))
        if "COUNT(*) FROM household_purchase_items" in sql:
            self._result = ("one", (self.review_count,))
        elif "recency_rank" in sql:
            self._result = ("all", self.price_point_rows)
        elif "WITH obs AS" in sql and "WHERE p.id = %s" in sql:
            self._result = ("one", self.product_detail_row)
        elif "WITH obs AS" in sql:
            self._result = ("all", self.product_rows)
        elif "FROM household_product_price_observations o" in sql:
            self._result = ("all", self.observation_rows)
        elif "FROM household_product_identifiers" in sql:
            self._result = ("all", self.identifier_rows)
        elif "FROM household_purchase_items i" in sql:
            self._result = ("all", self.item_rows)
        else:
            self._result = ("none", None)
        return self

    def fetchone(self) -> Any:
        kind, payload = self._result
        return payload if kind == "one" else None

    def fetchall(self) -> list[Any]:
        kind, payload = self._result
        return list(payload) if kind == "all" else []

    def commit(self) -> None:
        self.committed += 1


class _Storage:
    def __init__(self, conn: _ScriptedConn) -> None:
        self.conn = conn

    @contextmanager
    def connection(self):
        yield self.conn


def _service(conn: _ScriptedConn) -> HouseholdProductCatalogService:
    service = HouseholdProductCatalogService()
    service.storage = _Storage(conn)
    return service


_PRODUCT_ROW = (
    "prod-1",  # id
    "GV Edamame",  # canonical_name
    "Great Value",  # brand
    "12 oz",  # package label
    None,  # image_url
    5,  # purchase_count
    5,  # observation_count
    1,  # needs_review_count
    date(2026, 1, 5),  # first observed
    date(2026, 6, 1),  # last observed
    1,  # total_count window
)

_POINT_ROWS = [
    ("prod-1", date(2026, 1, 5), "Walmart", Decimal("1.48"), Decimal("1"), Decimal("1.48"), "receipt"),
    ("prod-1", date(2026, 6, 1), "Walmart", Decimal("1.92"), Decimal("1"), Decimal("1.92"), "receipt"),
]

_ITEM_ROW = (
    "item-1",
    "txn-1",
    "prod-1",
    "GV Edamame",
    "needs_review",
    0.7,
    date(2026, 6, 1),
    "Walmart",
    "GV EDAMAME 12OZ",
    Decimal("2"),
    Decimal("0.96"),
    Decimal("1.92"),
    Decimal("2.05"),
    "Groceries",
    "essential",
    "suggested",
)


def test_list_products_builds_summaries_with_latest_price_from_points() -> None:
    conn = _ScriptedConn(
        product_rows=[_PRODUCT_ROW],
        review_count=3,
        price_point_rows=_POINT_ROWS,
    )

    catalog = _service(conn).list_products(search="edamame", limit=10, offset=0)

    assert catalog.total_count == 1
    assert catalog.needs_review_total == 3
    assert catalog.returned_count == 1
    product = catalog.products[0]
    assert product.canonical_name == "GV Edamame"
    assert product.purchase_count == 5
    assert product.needs_review_count == 1
    # Points arrive oldest-first; latest price comes from the newest point.
    assert [point.total_price for point in product.price_points] == [1.48, 1.92]
    assert product.latest_price == 1.92
    assert product.latest_unit_price == 1.92
    assert product.latest_merchant == "Walmart"
    # Search reaches the SQL as an ILIKE pattern.
    products_sql, products_params = conn.queries[0]
    assert "ILIKE" in products_sql
    assert products_params[0] == "%edamame%"


def test_product_detail_returns_observations_identifiers_and_items() -> None:
    conn = _ScriptedConn(
        product_detail_row=_PRODUCT_ROW[:10],
        observation_rows=[row[1:7] for row in _POINT_ROWS],
        identifier_rows=[("normalized_key", "walmart|gv edamame")],
        item_rows=[_ITEM_ROW],
    )

    detail = _service(conn).get_product_detail("prod-1")

    assert detail is not None
    assert detail.product.canonical_name == "GV Edamame"
    assert detail.product.latest_price == 1.92
    assert [obs.total_price for obs in detail.observations] == [1.48, 1.92]
    assert detail.identifiers[0].kind == "normalized_key"
    item = detail.recent_items[0]
    assert item.product_match_status == "needs_review"
    assert item.allocated_amount == 2.05
    assert item.category == "Groceries"


def test_product_detail_missing_product_returns_none() -> None:
    conn = _ScriptedConn(product_detail_row=None)
    assert _service(conn).get_product_detail("missing") is None


def test_transaction_items_and_review_queue_map_rows() -> None:
    conn = _ScriptedConn(item_rows=[_ITEM_ROW], review_count=1)
    service = _service(conn)

    items = service.list_transaction_items("txn-1")
    assert len(items) == 1
    assert items[0].transaction_id == "txn-1"
    assert items[0].quantity == 2.0
    assert items[0].unit_price == 0.96

    queue = service.list_review_queue()
    assert queue.total_count == 1
    assert queue.items[0].id == "item-1"
    assert queue.items[0].product_name == "GV Edamame"


def test_assign_product_delegates_and_commits() -> None:
    conn = _ScriptedConn()
    service = _service(conn)
    calls: list[dict[str, Any]] = []

    class _Normalization:
        @staticmethod
        def reassign_item(_conn: Any, *, item_id: str, action: str, product_id: Any) -> bool:
            calls.append({"item_id": item_id, "action": action, "product_id": product_id})
            return True

        @staticmethod
        def merge_products(_conn: Any, *, source_product_id: str, target_product_id: str) -> bool:
            calls.append({"source": source_product_id, "target": target_product_id})
            return True

    service.normalization_service = _Normalization()  # type: ignore[assignment]

    assert service.assign_product(item_id="item-1", action="confirm") is True
    assert service.merge_products(source_product_id="a", target_product_id="b") is True
    assert calls == [
        {"item_id": "item-1", "action": "confirm", "product_id": None},
        {"source": "a", "target": "b"},
    ]
    assert conn.committed == 2
