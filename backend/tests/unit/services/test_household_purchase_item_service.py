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
        accounts: list[tuple[Any, ...]] | None = None,
        category_update_product_id: str | None = None,
        owner_update_product_id: str | None = None,
        purchase_item_insert_conflicts: bool = False,
    ) -> None:
        self.import_rows = import_rows or []
        self.unlinked_items = unlinked_items or []
        self.candidate_transactions = candidate_transactions or []
        self.accounts = accounts or []
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
        if "FROM household_accounts" in sql:
            self._result = ("all", self.accounts)
        elif "FROM household_import_rows r" in sql:
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
    shipment: dict[str, Any] | None = None,
) -> tuple[Any, ...]:
    metadata: dict[str, Any] = {
        "Order ID": order_id,
        "Product Name": "FreeKey System",
        "Unit Price": "7.85",
        "Original Quantity": "1",
        **(shipment or {}),
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


def _amazon_item(
    *,
    item_id: str,
    group_key: str = "amazon:113-0000000-0000000",
    amount: float,
    shipment_key: str,
    shipment_total: float,
    ship_date: str,
    paid_account_id: str | None = "acct-1",
) -> tuple[Any, ...]:
    metadata = json.dumps(
        {
            "card_label": "Visa - 9728",
            "card_mask": "9728",
            "ship_date": ship_date,
            "shipment_key": shipment_key,
            "shipment_total": shipment_total,
            "paid_account_id": paid_account_id,
        }
    )
    return (item_id, group_key, _MAY_FOURTH, amount, metadata, "Amazon", "amazon_order_history")


def _amazon_charge(
    *,
    transaction_id: str,
    amount: float,
    day: int,
    account_id: str = "acct-1",
) -> tuple[Any, ...]:
    return (
        transaction_id,
        datetime(2026, 5, day, 12, 0, tzinfo=UTC),
        "Amazon",
        "AMAZON MKTPL*BV4O36640",
        amount,
        account_id,
        "Chase Prime Visa / Amazon card",
        "statement",
        "credit_card",
    )


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


def test_promote_stamps_the_package_the_ship_date_and_the_card() -> None:
    """The half of the item/money link that does not need a matching charge."""
    conn = _ScriptedConn(
        import_rows=[
            _amazon_import_row(
                shipment={
                    "Ship Date": "2026-05-06T20:20:16.546Z",
                    "Carrier Name & Tracking Number": "AMZN_US(TBA331050966070)",
                    "Shipment Item Subtotal": "85.49",
                    "Shipment Item Subtotal Tax": "5.98",
                    "Payment Method Type": "Visa - 2000",
                }
            )
        ],
        accounts=[
            (
                "acct-prime",
                "Chase Prime Visa / Amazon card",
                "1000",
                {
                    "prior_masks": [
                        {"mask": "2000", "from": "2025-12-30", "through": "2026-04-08"}
                    ]
                },
            )
        ],
    )
    _service(conn).promote_import_rows()
    metadata = json.loads(conn.purchase_item_inserts[0][17])
    assert metadata["ship_date"] == "2026-05-06"
    assert metadata["shipment_key"] == "AMZN_US(TBA331050966070)"
    assert metadata["shipment_total"] == 91.47
    assert metadata["card_mask"] == "2000"


def test_promote_names_a_card_retired_before_the_purchase_rather_than_guessing() -> None:
    """The order is dated May; that number was replaced in April, so it is not this account's."""
    conn = _ScriptedConn(
        import_rows=[_amazon_import_row(shipment={"Payment Method Type": "Visa - 2000"})],
        accounts=[
            (
                "acct-prime",
                "Chase Prime Visa / Amazon card",
                "1000",
                {
                    "prior_masks": [
                        {"mask": "2000", "from": "2025-12-30", "through": "2026-04-08"}
                    ]
                },
            )
        ],
    )
    _service(conn).promote_import_rows()
    metadata = json.loads(conn.purchase_item_inserts[0][17])
    assert "paid_account_id" not in metadata
    assert metadata["paid_account_state"] == "outside_card_window"


def test_promote_resolves_a_card_the_account_used_to_carry() -> None:
    conn = _ScriptedConn(
        import_rows=[
            _amazon_import_row(
                shipment={
                    "Payment Method Type": "Visa - 2000",
                    "Ship Date": "2026-02-14T00:00:00Z",
                }
            )
        ],
        accounts=[
            (
                "acct-prime",
                "Chase Prime Visa / Amazon card",
                "1000",
                {
                    "prior_masks": [
                        {"mask": "2000", "from": "2025-12-30", "through": "2026-06-30"}
                    ]
                },
            )
        ],
    )
    _service(conn).promote_import_rows()
    metadata = json.loads(conn.purchase_item_inserts[0][17])
    assert metadata["paid_account_id"] == "acct-prime"
    assert metadata["paid_account_state"] == "reissued_card"


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
    assert summary == {
        "groups": 1,
        "linked": 1,
        "partial": 0,
        "pending": 0,
        "allocated_items": 2,
    }
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


def test_link_falls_back_to_packages_when_the_order_total_matches_nothing() -> None:
    """An order billed as it ships is two charges, and no order total equals either."""
    conn = _ScriptedConn(
        unlinked_items=[
            _amazon_item(
                item_id="item-a",
                amount=20.0,
                shipment_key="TRK-A",
                shipment_total=20.0,
                ship_date="2026-05-05",
            ),
            _amazon_item(
                item_id="item-b",
                amount=15.0,
                shipment_key="TRK-B",
                shipment_total=15.0,
                ship_date="2026-05-08",
            ),
        ],
        candidate_transactions=[
            _amazon_charge(transaction_id="tx-a", amount=20.0, day=5),
            _amazon_charge(transaction_id="tx-b", amount=15.0, day=8),
        ],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary["linked"] == 1
    assert summary["allocated_items"] == 2
    assert {params[3]: params[0] for params in conn.link_updates} == {
        "item-a": "tx-a",
        "item-b": "tx-b",
    }


def test_link_reports_a_partly_charged_order_as_partial() -> None:
    conn = _ScriptedConn(
        unlinked_items=[
            _amazon_item(
                item_id="item-a",
                amount=20.0,
                shipment_key="TRK-A",
                shipment_total=20.0,
                ship_date="2026-05-05",
            ),
            _amazon_item(
                item_id="item-b",
                amount=15.0,
                shipment_key="TRK-B",
                shipment_total=15.0,
                ship_date="2026-05-08",
            ),
        ],
        candidate_transactions=[_amazon_charge(transaction_id="tx-a", amount=20.0, day=5)],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary == {
        "groups": 1,
        "linked": 0,
        "partial": 1,
        "pending": 0,
        "allocated_items": 1,
    }


def test_link_refuses_a_charge_on_a_card_the_order_was_not_paid_with() -> None:
    """One charge lands on one card; a same-priced charge elsewhere is someone else's."""
    conn = _ScriptedConn(
        unlinked_items=[
            _amazon_item(
                item_id="item-a",
                amount=20.0,
                shipment_key="TRK-A",
                shipment_total=20.0,
                ship_date="2026-05-05",
                paid_account_id="acct-prime",
            )
        ],
        candidate_transactions=[
            _amazon_charge(
                transaction_id="tx-other", amount=20.0, day=5, account_id="acct-sapphire"
            )
        ],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary["pending"] == 1
    assert conn.link_updates == []


def test_link_dates_the_search_from_the_day_it_shipped() -> None:
    """The card is charged when the package leaves, which can be a week after the order."""
    late_charge = _amazon_charge(transaction_id="tx-late", amount=20.0, day=12)
    conn = _ScriptedConn(
        unlinked_items=[
            _amazon_item(
                item_id="item-a",
                amount=20.0,
                shipment_key="TRK-A",
                shipment_total=20.0,
                ship_date="2026-05-11",
            )
        ],
        candidate_transactions=[late_charge],
    )
    summary = _service(conn).link_purchase_groups()
    assert summary["linked"] == 1
    assert conn.link_updates[0][0] == "tx-late"


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
