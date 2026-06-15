"""Unit tests for purchase item promotion, linking, and categorization."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdPurchaseItemCategoryUpdate,
    HouseholdPurchaseItemOwnerUpdate,
)
from app.services.household_purchase_item_service import HouseholdPurchaseItemService

_MAY_FOURTH = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


class _ScriptedConn:
    def __init__(
        self,
        *,
        import_rows: list[tuple[Any, ...]] | None = None,
        unlinked_items: list[tuple[Any, ...]] | None = None,
        candidate_transactions: list[tuple[Any, ...]] | None = None,
        category_update_product_id: str | None = None,
        owner_update_product_id: str | None = None,
        purchase_item_insert_conflicts: bool = False,
    ) -> None:
        self.import_rows = import_rows or []
        self.unlinked_items = unlinked_items or []
        self.candidate_transactions = candidate_transactions or []
        self.category_update_product_id = category_update_product_id
        self.owner_update_product_id = owner_update_product_id
        self.purchase_item_insert_conflicts = purchase_item_insert_conflicts
        self.purchase_item_inserts: list[list[Any]] = []
        self.observation_inserts: list[list[Any]] = []
        self.merchant_inserts: list[list[Any]] = []
        self.link_updates: list[list[Any]] = []
        self.rule_inserts: list[list[Any]] = []
        self.rule_updates: list[list[Any]] = []
        self.owner_updates: list[list[Any]] = []
        self.rule_reapply_updates: list[list[Any]] = []
        self.committed = 0
        self._result: tuple[str, Any] = ("none", None)

    def execute(self, sql: str, params: list[Any] | None = None) -> _ScriptedConn:
        params = params or []
        if "FROM household_import_rows r" in sql:
            self._result = ("all", self.import_rows)
        elif "JOIN household_products p" in sql or (
            "FROM household_product_identifiers" in sql and sql.strip().startswith("SELECT")
        ):
            self._result = ("one", None)
        elif (
            "INSERT INTO household_products" in sql
            or "INSERT INTO household_product_identifiers" in sql
        ):
            self._result = ("none", None)
        elif "SET category" in sql and "UPDATE household_purchase_items" in sql and "categorization_source = 'manual'" in sql:
            self._result = ("one", (self.category_update_product_id,))
        elif "UPDATE household_purchase_items" in sql and "metadata =" in sql:
            self.owner_updates.append(params)
            self._result = (
                "one",
                (
                    self.owner_update_product_id,
                    "Groceries",
                    "essential",
                ),
            )
        elif "categorization_source = 'product_rule'" in sql:
            self.rule_reapply_updates.append(params)
            self._result = ("all", [("item-1",)])
        elif "FROM household_transaction_rules" in sql:
            self._result = ("one", None)
        elif "UPDATE household_transaction_rules" in sql:
            self.rule_updates.append(params)
            self._result = ("none", None)
        elif "INSERT INTO household_transaction_rules" in sql:
            self.rule_inserts.append(params)
            self._result = ("none", None)
        elif "FROM household_merchants" in sql:
            self._result = ("one", None)
        elif "INSERT INTO household_merchants" in sql:
            self.merchant_inserts.append(params)
            self._result = ("none", None)
        elif "INSERT INTO household_purchase_items" in sql:
            self.purchase_item_inserts.append(params)
            self._result = (
                "one",
                None if self.purchase_item_insert_conflicts else (params[0],),
            )
        elif "INSERT INTO household_product_price_observations" in sql:
            self.observation_inserts.append(params)
            self._result = ("none", None)
        elif "FROM household_purchase_items i" in sql:
            self._result = ("all", self.unlinked_items)
        elif "FROM household_transactions t" in sql:
            self._result = ("all", self.candidate_transactions)
        elif "SET transaction_id" in sql:
            self.link_updates.append(params)
            self._result = ("none", None)
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


def _service(conn: _ScriptedConn) -> HouseholdPurchaseItemService:
    service = HouseholdPurchaseItemService()
    service.storage = _Storage(conn)
    return service


def _amazon_import_row(
    *,
    row_id: str = "row-1",
    order_id: str = "106-2759616-1448213",
    amount: str = "8.40",
    tags: list[str] | None = None,
) -> tuple[Any, ...]:
    metadata: dict[str, Any] = {
        "Order ID": order_id,
        "Product Name": "FreeKey System",
        "Unit Price": "7.85",
        "Original Quantity": "1",
        "product_enrichment": {
            "identifiers": {"asin": "B00AQ664H6"},
            "normalized_item_key": "amazon freekey system",
            "package_measure": None,
            "open_food_facts": {"categories_tags": tags} if tags else None,
        },
    }
    return (row_id, "doc-1", "amazon_order_history", _MAY_FOURTH, "Amazon", "FreeKey System", amount, metadata)


def _receipt_item(
    *,
    item_id: str,
    group_key: str = "doc-9:0",
    amount: float,
    receipt_total: float = 34.96,
) -> tuple[Any, ...]:
    metadata = json.dumps({"receipt_total": receipt_total, "account_label": "Visa credit 9728"})
    return (item_id, group_key, _MAY_FOURTH, amount, metadata, "Ulta Beauty", "receipt_line_items")


def _candidate_transaction(
    *,
    transaction_id: str = "tx-1",
    amount: float = 34.96,
) -> tuple[Any, ...]:
    return (
        transaction_id,
        _MAY_FOURTH,
        "Ulta Beauty",
        "ULTA BEAUTY #123 ANYTOWN FL",
        amount,
        "acct-1",
        "Visa credit 9728",
        "statement",
        "credit_card",
    )


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------


def test_promote_amazon_row_inserts_item_and_observation() -> None:
    conn = _ScriptedConn(import_rows=[_amazon_import_row()])
    summary = _service(conn).promote_import_rows()
    assert summary["promoted"] == 1
    assert summary["products_created"] == 1
    assert len(conn.purchase_item_inserts) == 1
    insert = conn.purchase_item_inserts[0]
    assert insert[1] == "row-1"  # import_row_id
    assert insert[3] == "amazon:106-2759616-1448213"  # purchase_group_key
    assert insert[9] == "FreeKey System"  # description, original wording
    assert len(conn.observation_inserts) == 1
    assert conn.observation_inserts[0][11] == "order_history"  # source
    assert conn.committed >= 1


def test_promote_uses_open_food_facts_tag_map_for_category() -> None:
    conn = _ScriptedConn(import_rows=[_amazon_import_row(tags=["en:beverages"])])
    _service(conn).promote_import_rows()
    insert = conn.purchase_item_inserts[0]
    assert insert[13] == "Groceries"  # category
    assert insert[14] == "essential"  # essentiality
    assert insert[15] == "suggested"  # categorization_source


def test_promote_skips_rows_already_promoted_via_conflict() -> None:
    conn = _ScriptedConn(
        import_rows=[_amazon_import_row()], purchase_item_insert_conflicts=True
    )
    summary = _service(conn).promote_import_rows()
    assert summary["promoted"] == 0
    assert summary["skipped"] == 1
    assert conn.observation_inserts == []


# ---------------------------------------------------------------------------
# Linking + allocation
# ---------------------------------------------------------------------------


def test_link_group_allocates_receipt_total_with_tax_overhead() -> None:
    conn = _ScriptedConn(
        unlinked_items=[
            _receipt_item(item_id="item-a", amount=28.0),
            _receipt_item(item_id="item-b", amount=4.99),
        ],
        candidate_transactions=[_candidate_transaction()],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary == {"groups": 1, "linked": 1, "pending": 0, "allocated_items": 2}
    assert len(conn.link_updates) == 2
    allocated = {params[3]: params[1] for params in conn.link_updates}
    assert allocated == {"item-a": 29.67, "item-b": 5.29}
    assert round(sum(allocated.values()), 2) == 34.96
    assert all(params[0] == "tx-1" for params in conn.link_updates)


def test_link_group_stays_pending_without_a_matching_charge() -> None:
    conn = _ScriptedConn(
        unlinked_items=[_receipt_item(item_id="item-a", amount=28.0)],
        candidate_transactions=[],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary["pending"] == 1
    assert conn.link_updates == []


def test_link_uses_one_transaction_for_at_most_one_group() -> None:
    conn = _ScriptedConn(
        unlinked_items=[
            _receipt_item(item_id="item-a", group_key="doc-9:0", amount=34.96, receipt_total=34.96),
            _receipt_item(item_id="item-b", group_key="doc-9:1", amount=34.96, receipt_total=34.96),
        ],
        candidate_transactions=[_candidate_transaction()],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary["linked"] == 1
    assert summary["pending"] == 1
    assert len(conn.link_updates) == 1


def test_link_rejects_merchant_mismatch() -> None:
    stranger = (
        "tx-9",
        _MAY_FOURTH,
        "Publix",
        "PUBLIX SUPER MAR 123",
        34.96,
        "acct-1",
        "Visa credit 9728",
        "statement",
        "credit_card",
    )
    conn = _ScriptedConn(
        unlinked_items=[_receipt_item(item_id="item-a", amount=34.96, receipt_total=34.96)],
        candidate_transactions=[stranger],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary["pending"] == 1
    assert conn.link_updates == []


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------


def test_update_item_category_applies_product_rule() -> None:
    conn = _ScriptedConn(category_update_product_id="prod-1")
    updated = _service(conn).update_item_category(
        "item-1",
        HouseholdPurchaseItemCategoryUpdate(
            category="Groceries", essentiality="essential", apply_to_product=True
        ),
    )
    assert updated is True
    assert len(conn.rule_inserts) == 1
    rule_insert = conn.rule_inserts[0]
    assert rule_insert[1] == "prod-1"
    assert rule_insert[2] == "Groceries"
    assert conn.committed == 1


def test_update_item_category_without_product_rule() -> None:
    conn = _ScriptedConn(category_update_product_id="prod-1")
    updated = _service(conn).update_item_category(
        "item-1",
        HouseholdPurchaseItemCategoryUpdate(
            category="Groceries", essentiality="essential", apply_to_product=False
        ),
    )
    assert updated is True
    assert conn.rule_inserts == []


def test_update_item_owner_without_product_rule() -> None:
    conn = _ScriptedConn(owner_update_product_id="prod-1")
    updated = _service(conn).update_item_owner(
        "item-1",
        HouseholdPurchaseItemOwnerUpdate(owner_name="Alex Demo", apply_to_product=False),
    )
    assert updated is True
    assert conn.owner_updates
    owner_patch = json.loads(conn.owner_updates[0][0])
    assert owner_patch["owner_name"] == "Alex Demo"
    assert owner_patch["owner_source"] == "manual"
    assert conn.rule_inserts == []


def test_update_item_owner_applies_product_rule() -> None:
    conn = _ScriptedConn(owner_update_product_id="prod-1")
    updated = _service(conn).update_item_owner(
        "item-1",
        HouseholdPurchaseItemOwnerUpdate(owner_name="Jordan Demo", apply_to_product=True),
    )
    assert updated is True
    assert len(conn.rule_inserts) == 1
    owner_rule = json.loads(conn.rule_inserts[0][4])
    assert owner_rule["category_rule_enabled"] is False
    assert owner_rule["owner_name"] == "Jordan Demo"
    assert len(conn.owner_updates) == 2
