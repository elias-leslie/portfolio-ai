"""Promote import rows to purchase items, link them to charges, allocate splits."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import HouseholdPurchaseItemCategoryUpdate
from app.services._household_dashboard_builders import (
    suggest_category,
    suggest_essentiality,
)
from app.services._household_item_splits import allocate_overhead_cents
from app.services._household_report_builder import (
    _coerce_metadata,
    _merchant_aliases,
    _merchant_root,
    report_rows_overlap,
)
from app.services.household_product_normalization_service import (
    HouseholdProductNormalizationService,
)
from app.storage import get_storage

logger = get_logger(__name__)

_PROMOTE_COMMIT_BATCH = 200

# Open Food Facts categories_tags -> existing canonical spend categories
# (_PLAID_CATEGORY_MAP strings; never a forked taxonomy).
_OPEN_FOOD_FACTS_TAG_CATEGORIES: dict[str, tuple[str, str]] = {
    "en:beverages": ("Groceries", "essential"),
    "en:snacks": ("Groceries", "essential"),
    "en:sweet-snacks": ("Groceries", "essential"),
    "en:salty-snacks": ("Groceries", "essential"),
    "en:dairies": ("Groceries", "essential"),
    "en:breakfasts": ("Groceries", "essential"),
    "en:cereals-and-potatoes": ("Groceries", "essential"),
    "en:meats": ("Groceries", "essential"),
    "en:seafood": ("Groceries", "essential"),
    "en:plant-based-foods": ("Groceries", "essential"),
    "en:frozen-foods": ("Groceries", "essential"),
    "en:desserts": ("Groceries", "essential"),
    "en:condiments": ("Groceries", "essential"),
    "en:baby-foods": ("Groceries", "essential"),
    "en:dietary-supplements": ("Healthcare", "essential"),
    "en:pet-food": ("Household", "mixed"),
}


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


class HouseholdPurchaseItemService:
    """First-class purchase items promoted 1:1 from household_import_rows."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.normalization_service = HouseholdProductNormalizationService()

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote_import_rows(
        self,
        *,
        document_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, int]:
        """Promote receipt/Amazon import rows into purchase items + observations.

        Idempotent via the import_row_id UNIQUE constraint; already-promoted
        rows are filtered out up front.
        """
        # Receipt reviews can emit the same physical line twice (per-transaction
        # raw spelling + top-level cleaned spelling) under one external_row_id,
        # so receipt rows dedupe per line before promotion. Amazon rows must
        # NOT collapse on external_row_id: there it is the order id shared by
        # every item in the order. Preferring an already-promoted variant keeps
        # re-runs idempotent (the losing variant never promotes later).
        sql = """
            SELECT id, document_id, dataset_type, row_date, merchant, description,
                   amount, row_metadata
            FROM (
                SELECT DISTINCT ON (
                        CASE
                            WHEN r.dataset_type = 'receipt_line_items'
                            THEN r.document_id::text || ':' || COALESCE(r.external_row_id, r.id::text)
                            ELSE r.id::text
                        END
                    )
                    r.id, r.document_id, r.dataset_type, r.row_date, r.merchant,
                    r.description, r.amount, r.row_metadata
                FROM household_import_rows r
                WHERE (r.dataset_type = 'receipt_line_items' OR r.dataset_type LIKE 'amazon%%')
                  AND r.amount IS NOT NULL
                  AND r.row_date IS NOT NULL
                  {document_filter}
                ORDER BY
                    CASE
                        WHEN r.dataset_type = 'receipt_line_items'
                        THEN r.document_id::text || ':' || COALESCE(r.external_row_id, r.id::text)
                        ELSE r.id::text
                    END,
                    (
                        SELECT 0 FROM household_purchase_items pi
                        WHERE pi.import_row_id = r.id
                    ) NULLS LAST,
                    r.created_at DESC,
                    length(COALESCE(r.description, '')) ASC,
                    r.id ASC
            ) canonical
            WHERE NOT EXISTS (
                SELECT 1 FROM household_purchase_items i WHERE i.import_row_id = canonical.id
            )
            ORDER BY canonical.row_date ASC
            LIMIT %s
        """
        params: list[Any] = []
        if document_id is not None:
            sql = sql.format(document_filter="AND r.document_id = %s")
            params.append(document_id)
        else:
            sql = sql.format(document_filter="")
        params.append(limit)

        summary = {"scanned": 0, "promoted": 0, "skipped": 0, "products_created": 0}
        with self.storage.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            pending = 0
            for row in rows:
                summary["scanned"] += 1
                promoted, product_created = self._promote_row(conn, row)
                if promoted:
                    summary["promoted"] += 1
                    summary["products_created"] += product_created
                    pending += 1
                else:
                    summary["skipped"] += 1
                if pending >= _PROMOTE_COMMIT_BATCH:
                    conn.commit()
                    pending = 0
            conn.commit()
        return summary

    def _promote_row(self, conn: Any, row: Any) -> tuple[bool, bool]:
        import_row_id = str(row[0])
        row_document_id = str(row[1]) if row[1] is not None else None
        dataset_type = str(row[2] or "")
        row_date = row[3]
        amount = _parse_float(row[6])
        metadata = _coerce_metadata(row[7])
        raw_enrichment = metadata.get("product_enrichment")
        enrichment = raw_enrichment if isinstance(raw_enrichment, dict) else {}
        item_name = str(metadata.get("Product Name") or row[5] or "").strip()
        raw_merchant = str(row[4] or "").strip() or (
            "Amazon" if dataset_type.startswith("amazon") else ""
        )
        if amount is None or not item_name or not raw_merchant:
            return False, False

        if dataset_type == "receipt_line_items":
            receipt_index = str(metadata.get("Receipt Index") or "0").strip() or "0"
            group_key = f"{row_document_id}:{receipt_index}"
            observation_source = "receipt"
        else:
            order_id = str(metadata.get("Order ID") or "").strip()
            group_key = f"amazon:{order_id}" if order_id else f"amazon:row:{import_row_id}"
            observation_source = "order_history"

        match = self.normalization_service.match_or_create_product(
            conn,
            merchant=raw_merchant,
            item_name=item_name,
            enrichment=enrichment,
        )
        category, essentiality, categorization_source, item_rule_id = self._initial_category(
            conn,
            product_id=match.product_id,
            enrichment=enrichment,
            merchant=raw_merchant,
            item_name=item_name,
        )
        merchant_id = self._lookup_or_create_merchant(
            conn,
            raw_merchant=raw_merchant,
            category=category,
            essentiality=essentiality,
        )

        quantity = _parse_float(metadata.get("Original Quantity")) or 1.0
        unit_price = _parse_float(metadata.get("Unit Price"))
        item_metadata: dict[str, Any] = {}
        receipt_total = _parse_float(metadata.get("Receipt Total"))
        if receipt_total is not None:
            item_metadata["receipt_total"] = receipt_total
        account_label = str(metadata.get("Account Label") or "").strip()
        if account_label:
            item_metadata["account_label"] = account_label

        item_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        inserted = conn.execute(
            """
            INSERT INTO household_purchase_items (
                id, import_row_id, document_id, purchase_group_key, merchant_id,
                product_id, product_match_status, product_match_confidence,
                purchase_date, description, quantity, unit_price, amount,
                category, essentiality, categorization_source, item_rule_id,
                metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s::jsonb, %s, %s
            )
            ON CONFLICT (import_row_id) DO NOTHING
            RETURNING id
            """,
            [
                item_id,
                import_row_id,
                row_document_id,
                group_key,
                merchant_id,
                match.product_id,
                match.status if not match.created else "auto",
                match.confidence,
                row_date,
                item_name,
                quantity,
                unit_price,
                round(amount, 2),
                category,
                essentiality,
                categorization_source,
                item_rule_id,
                json.dumps(item_metadata),
                now,
                now,
            ],
        ).fetchone()
        if inserted is None:
            return False, False

        measure_raw = enrichment.get("package_measure")
        measure = measure_raw if isinstance(measure_raw, dict) else {}
        observed_date = row_date.date() if hasattr(row_date, "date") else row_date
        conn.execute(
            """
            INSERT INTO household_product_price_observations (
                id, product_id, purchase_item_id, merchant_id, observed_date,
                total_price, quantity, unit_price, package_display_label,
                package_normalized_quantity, package_normalized_unit, source,
                metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            [
                str(uuid.uuid4()),
                match.product_id,
                item_id,
                merchant_id,
                observed_date,
                round(amount, 2),
                quantity,
                unit_price,
                str(measure.get("display_label") or "").strip() or None,
                measure.get("normalized_quantity"),
                str(measure.get("normalized_unit") or "").strip() or None,
                observation_source,
                json.dumps({"dataset_type": dataset_type}),
                now,
                now,
            ],
        )
        return True, match.created

    def _initial_category(
        self,
        conn: Any,
        *,
        product_id: str,
        enrichment: dict[str, Any],
        merchant: str,
        item_name: str,
    ) -> tuple[str, str, str, str | None]:
        """Product rule -> Open Food Facts tag map -> keyword suggestion."""
        rule = HouseholdProductNormalizationService._active_product_rule(conn, product_id)
        if rule is not None:
            return str(rule[1]), str(rule[2]), "product_rule", str(rule[0])
        open_food_facts = enrichment.get("open_food_facts")
        tags = (
            open_food_facts.get("categories_tags")
            if isinstance(open_food_facts, dict)
            else None
        )
        if isinstance(tags, list):
            for tag in tags:
                mapped = _OPEN_FOOD_FACTS_TAG_CATEGORIES.get(str(tag))
                if mapped is not None:
                    return mapped[0], mapped[1], "suggested", None
        return (
            suggest_category(merchant, item_name),
            suggest_essentiality(merchant, item_name),
            "suggested",
            None,
        )

    @staticmethod
    def _lookup_or_create_merchant(
        conn: Any,
        *,
        raw_merchant: str,
        category: str,
        essentiality: str,
    ) -> str | None:
        """Read-only alias lookup; create only when missing.

        Deliberately never updates an existing merchant row — promotion must
        not move merchant-level categories the way _resolve_merchant does.
        """
        alias_keys = sorted(_merchant_aliases(raw_merchant))
        normalized_key = alias_keys[0] if alias_keys else _merchant_root(raw_merchant)
        if not normalized_key:
            return None
        existing = conn.execute(
            """
            SELECT id
            FROM household_merchants
            WHERE normalized_key = ANY(%s)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [alias_keys or [normalized_key]],
        ).fetchone()
        if existing is not None:
            return str(existing[0])
        merchant_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO household_merchants (
                id, canonical_name, normalized_key, display_name, primary_category,
                essentiality, metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            [
                merchant_id,
                raw_merchant,
                normalized_key,
                raw_merchant,
                category,
                essentiality,
                json.dumps({"alias_keys": alias_keys}),
                now,
                now,
            ],
        )
        return merchant_id

    # ------------------------------------------------------------------
    # Linking + allocation
    # ------------------------------------------------------------------

    def link_purchase_groups(self, *, limit: int = 2000) -> dict[str, int]:
        """Link pending purchase groups to ledger charges and allocate splits.

        One group <-> one transaction. Groups that do not find a charge stay
        pending and contribute nothing to spend math. Refund-flow transactions
        are excluded (v1).
        """
        summary = {"groups": 0, "linked": 0, "pending": 0, "allocated_items": 0}
        with self.storage.connection() as conn:
            item_rows = conn.execute(
                """
                SELECT i.id, i.purchase_group_key, i.purchase_date, i.amount,
                       i.metadata, COALESCE(m.canonical_name, ''),
                       r.dataset_type
                FROM household_purchase_items i
                LEFT JOIN household_merchants m ON m.id = i.merchant_id
                JOIN household_import_rows r ON r.id = i.import_row_id
                WHERE i.transaction_id IS NULL
                  AND i.removed IS NOT TRUE
                ORDER BY i.purchase_date ASC, i.created_at ASC, i.id ASC
                LIMIT %s
                """,
                [limit],
            ).fetchall()

            groups: dict[str, list[Any]] = {}
            for item in item_rows:
                groups.setdefault(str(item[1]), []).append(item)

            used_transaction_ids: set[str] = set()
            for group_key, items in groups.items():
                summary["groups"] += 1
                linked = self._link_group(
                    conn,
                    group_key=group_key,
                    items=items,
                    used_transaction_ids=used_transaction_ids,
                )
                if linked:
                    summary["linked"] += 1
                    summary["allocated_items"] += len(items)
                else:
                    summary["pending"] += 1
            conn.commit()
        return summary

    def _link_group(
        self,
        conn: Any,
        *,
        group_key: str,
        items: list[Any],
        used_transaction_ids: set[str],
    ) -> bool:
        dates = [item[2] for item in items if item[2] is not None]
        if not dates:
            return False
        line_amounts = [float(item[3] or 0.0) for item in items]
        dataset_type = str(items[0][6] or "")
        merchant = str(items[0][5] or "").strip()
        first_metadata = _coerce_metadata(items[0][4])
        # Receipt charges include tax/fees the line items do not; the printed
        # receipt total is the amount that hits the card. Amazon item totals
        # are tax-inclusive, so their sum is the order charge.
        receipt_total = _parse_float(first_metadata.get("receipt_total"))
        if dataset_type == "receipt_line_items" and receipt_total is not None:
            group_total = receipt_total
        else:
            group_total = round(sum(line_amounts), 2)
        if group_total <= 0:
            return False

        min_date = min(dates)
        max_date = max(dates)
        candidates = conn.execute(
            """
            SELECT t.id, t.transaction_date,
                   COALESCE(m.canonical_name, t.raw_merchant, t.description),
                   t.description, CAST(t.amount AS DOUBLE PRECISION),
                   t.household_account_id, t.account_label,
                   d.document_type, d.source_type
            FROM household_transactions t
            LEFT JOIN household_merchants m ON m.id = t.merchant_id
            LEFT JOIN household_documents d ON d.id = t.document_id
            WHERE t.flow_type = 'expense'
              AND t.removed IS NOT TRUE
              AND t.transaction_date >= %s - INTERVAL '2 days'
              AND t.transaction_date <= %s + INTERVAL '2 days'
              AND ABS(CAST(t.amount AS DOUBLE PRECISION) - %s) <= 0.005
              AND NOT EXISTS (
                  SELECT 1 FROM household_purchase_items pi
                  WHERE pi.transaction_id = t.id
                    AND pi.removed IS NOT TRUE
              )
            ORDER BY t.transaction_date ASC
            """,
            [min_date, max_date, group_total],
        ).fetchall()

        group_row = {
            "date": min_date.date() if hasattr(min_date, "date") else min_date,
            "merchant": merchant,
            "description": merchant,
            "amount": group_total,
            "source_kind": "import",
            "document_type": "import",
            "source_type": dataset_type,
            "household_account_id": None,
            "account_label": str(first_metadata.get("account_label") or "") or None,
        }
        for candidate in candidates:
            transaction_id = str(candidate[0])
            if transaction_id in used_transaction_ids:
                continue
            transaction_row = {
                "date": candidate[1].date() if hasattr(candidate[1], "date") else candidate[1],
                "merchant": str(candidate[2] or ""),
                "description": str(candidate[3] or ""),
                "amount": float(candidate[4] or 0.0),
                "source_kind": "transaction",
                "document_type": str(candidate[7] or ""),
                "source_type": str(candidate[8] or ""),
                "household_account_id": (
                    str(candidate[5]) if candidate[5] is not None else None
                ),
                "account_label": str(candidate[6] or "") or None,
            }
            if not report_rows_overlap(group_row, transaction_row):
                continue
            self._allocate_group(
                conn,
                items=items,
                line_amounts=line_amounts,
                transaction_id=transaction_id,
                transaction_amount=float(candidate[4] or 0.0),
            )
            used_transaction_ids.add(transaction_id)
            return True
        return False

    @staticmethod
    def _allocate_group(
        conn: Any,
        *,
        items: list[Any],
        line_amounts: list[float],
        transaction_id: str,
        transaction_amount: float,
    ) -> None:
        line_cents = [round(amount * 100) for amount in line_amounts]
        allocated = allocate_overhead_cents(line_cents, round(transaction_amount * 100))
        now = datetime.now(UTC).isoformat()
        for item, cents in zip(items, allocated, strict=True):
            conn.execute(
                """
                UPDATE household_purchase_items
                SET transaction_id = %s,
                    allocated_amount = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [transaction_id, cents / 100.0, now, str(item[0])],
            )

    # ------------------------------------------------------------------
    # Categorization
    # ------------------------------------------------------------------

    def update_item_category(
        self,
        item_id: str,
        payload: HouseholdPurchaseItemCategoryUpdate,
    ) -> bool:
        with self.storage.connection() as conn:
            now = datetime.now(UTC).isoformat()
            row = conn.execute(
                """
                UPDATE household_purchase_items
                SET category = %s,
                    essentiality = %s,
                    categorization_source = 'manual',
                    item_rule_id = NULL,
                    updated_at = %s
                WHERE id = %s
                RETURNING product_id
                """,
                [payload.category, payload.essentiality, now, item_id],
            ).fetchone()
            if row is None:
                return False
            product_id = str(row[0]) if row[0] is not None else None
            if payload.apply_to_product and product_id is not None:
                self._upsert_product_rule(
                    conn,
                    product_id=product_id,
                    category=payload.category,
                    essentiality=payload.essentiality,
                    created_from_item_id=item_id,
                )
                self.normalization_service.apply_product_rule_to_items(
                    conn, product_id=product_id
                )
            conn.commit()
        return True

    @staticmethod
    def _upsert_product_rule(
        conn: Any,
        *,
        product_id: str,
        category: str,
        essentiality: str,
        created_from_item_id: str,
    ) -> str:
        now = datetime.now(UTC)
        rule_metadata = json.dumps(
            {
                "created_from_purchase_item_id": created_from_item_id,
                "updated_at": now.isoformat(),
            }
        )
        existing = conn.execute(
            """
            SELECT id FROM household_transaction_rules
            WHERE product_id = %s AND rule_type = 'product' AND enabled IS TRUE
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [product_id],
        ).fetchone()
        if existing is not None:
            rule_id = str(existing[0])
            conn.execute(
                """
                UPDATE household_transaction_rules
                SET category = %s,
                    essentiality = %s,
                    source = 'manual',
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = %s
                WHERE id = %s
                """,
                [category, essentiality, rule_metadata, now, rule_id],
            )
            return rule_id
        rule_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO household_transaction_rules (
                id, rule_type, product_id, category, essentiality, enabled,
                source, applied_count, metadata, created_at, updated_at
            ) VALUES (%s, 'product', %s, %s, %s, TRUE, 'manual', 0, %s::jsonb, %s, %s)
            """,
            [rule_id, product_id, category, essentiality, rule_metadata, now, now],
        )
        return rule_id

    # ------------------------------------------------------------------
    # Orchestration entry points
    # ------------------------------------------------------------------

    def sync_document(self, *, document_id: str) -> dict[str, int]:
        """Pipeline hook: promote this document's rows, then link pending groups."""
        promote_summary = self.promote_import_rows(document_id=document_id)
        link_summary = self.link_purchase_groups()
        return {**promote_summary, **{f"link_{k}": v for k, v in link_summary.items()}}

    def backfill(self, *, limit: int = 10000) -> dict[str, int]:
        """Promote all eligible import rows, then link pending groups."""
        promote_summary = self.promote_import_rows(limit=limit)
        link_summary = self.link_purchase_groups(limit=limit)
        return {**promote_summary, **{f"link_{k}": v for k, v in link_summary.items()}}
