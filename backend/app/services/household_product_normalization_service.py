"""Normalize purchase line items into canonical household products."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.services._household_report_builder import _normalized_item_key

_IDENTIFIER_CONFIDENCE = 0.98
_KEY_COMPATIBLE_CONFIDENCE = 0.85
_KEY_INCOMPATIBLE_CONFIDENCE = 0.7
_AUTO_THRESHOLD = 0.75
_REVIEW_THRESHOLD = 0.5


@dataclass(frozen=True)
class ProductMatch:
    product_id: str
    status: str  # auto | needs_review
    confidence: float
    created: bool


def _barcode_kind(barcode: str) -> str:
    if len(barcode) == 12:
        return "upc"
    if len(barcode) == 13:
        return "ean"
    return "gtin"


def _hard_identifiers(enrichment: dict[str, Any]) -> list[tuple[str, str]]:
    raw = enrichment.get("identifiers")
    identifiers = raw if isinstance(raw, dict) else {}
    pairs: list[tuple[str, str]] = []
    asin = str(identifiers.get("asin") or "").strip()
    if asin:
        pairs.append(("asin", asin))
    barcode = str(identifiers.get("barcode") or "").strip()
    if barcode:
        pairs.append((_barcode_kind(barcode), barcode))
    return pairs


def _package_measure(enrichment: dict[str, Any]) -> dict[str, Any]:
    raw = enrichment.get("package_measure")
    return raw if isinstance(raw, dict) else {}


def _open_food_facts(enrichment: dict[str, Any]) -> dict[str, Any]:
    raw = enrichment.get("open_food_facts")
    return raw if isinstance(raw, dict) else {}


class HouseholdProductNormalizationService:
    """Match purchase items to canonical products via the identifier ladder."""

    def match_or_create_product(
        self,
        conn: Any,
        *,
        merchant: str,
        item_name: str,
        enrichment: dict[str, Any] | None = None,
    ) -> ProductMatch:
        """Identifier exact hit -> normalized-key hit -> create product."""
        enrichment = enrichment if isinstance(enrichment, dict) else {}
        identifier_pairs = _hard_identifiers(enrichment)
        normalized_key = (
            str(enrichment.get("normalized_item_key") or "").strip()
            or _normalized_item_key(merchant, item_name)
        )
        measure = _package_measure(enrichment)
        item_unit = str(measure.get("normalized_unit") or "").strip() or None

        for kind, value in identifier_pairs:
            hit = conn.execute(
                """
                SELECT product_id
                FROM household_product_identifiers
                WHERE kind = %s AND value = %s
                """,
                [kind, value],
            ).fetchone()
            if hit is not None:
                product_id = str(hit[0])
                self._ensure_identifiers(
                    conn,
                    product_id=product_id,
                    identifier_pairs=identifier_pairs,
                    normalized_key=normalized_key,
                )
                return ProductMatch(
                    product_id=product_id,
                    status="auto",
                    confidence=_IDENTIFIER_CONFIDENCE,
                    created=False,
                )

        if normalized_key:
            hit = conn.execute(
                """
                SELECT i.product_id, p.package_normalized_unit
                FROM household_product_identifiers i
                JOIN household_products p ON p.id = i.product_id
                WHERE i.kind = 'normalized_key' AND i.value = %s
                """,
                [normalized_key],
            ).fetchone()
            if hit is not None:
                product_id = str(hit[0])
                product_unit = str(hit[1] or "").strip() or None
                units_compatible = (
                    item_unit is None or product_unit is None or item_unit == product_unit
                )
                confidence = (
                    _KEY_COMPATIBLE_CONFIDENCE
                    if units_compatible
                    else _KEY_INCOMPATIBLE_CONFIDENCE
                )
                status = "auto" if confidence >= _AUTO_THRESHOLD else "needs_review"
                if confidence >= _REVIEW_THRESHOLD:
                    self._ensure_identifiers(
                        conn,
                        product_id=product_id,
                        identifier_pairs=identifier_pairs if status == "auto" else [],
                        normalized_key=normalized_key,
                    )
                    return ProductMatch(
                        product_id=product_id,
                        status=status,
                        confidence=confidence,
                        created=False,
                    )

        product_id = self._create_product(
            conn,
            item_name=item_name,
            enrichment=enrichment,
            identifier_pairs=identifier_pairs,
            normalized_key=normalized_key,
        )
        return ProductMatch(product_id=product_id, status="auto", confidence=1.0, created=True)

    def _create_product(
        self,
        conn: Any,
        *,
        item_name: str,
        enrichment: dict[str, Any],
        identifier_pairs: list[tuple[str, str]],
        normalized_key: str,
    ) -> str:
        measure = _package_measure(enrichment)
        open_food_facts = _open_food_facts(enrichment)
        product_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO household_products (
                id, canonical_name, brand, package_display_label,
                package_normalized_quantity, package_normalized_unit,
                image_url, metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            [
                product_id,
                item_name.strip() or "Unknown product",
                str(open_food_facts.get("brands") or "").strip() or None,
                str(measure.get("display_label") or "").strip() or None,
                measure.get("normalized_quantity"),
                str(measure.get("normalized_unit") or "").strip() or None,
                str(open_food_facts.get("image_url") or "").strip() or None,
                json.dumps(
                    {
                        "open_food_facts_categories": open_food_facts.get("categories_tags")
                        or []
                    }
                ),
                now,
                now,
            ],
        )
        self._ensure_identifiers(
            conn,
            product_id=product_id,
            identifier_pairs=identifier_pairs,
            normalized_key=normalized_key,
        )
        return product_id

    def _ensure_identifiers(
        self,
        conn: Any,
        *,
        product_id: str,
        identifier_pairs: list[tuple[str, str]],
        normalized_key: str,
    ) -> None:
        pairs = list(identifier_pairs)
        if normalized_key:
            pairs.append(("normalized_key", normalized_key))
        now = datetime.now(UTC).isoformat()
        for kind, value in pairs:
            conn.execute(
                """
                INSERT INTO household_product_identifiers (
                    id, product_id, kind, value, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (kind, value) DO NOTHING
                """,
                [str(uuid.uuid4()), product_id, kind, value, now, now],
            )

    def merge_products(
        self,
        conn: Any,
        *,
        source_product_id: str,
        target_product_id: str,
    ) -> bool:
        """Repoint everything from source to target, then delete source."""
        if source_product_id == target_product_id:
            return False
        rows = conn.execute(
            """
            SELECT id, brand, package_display_label, package_normalized_quantity,
                   package_normalized_unit, image_url
            FROM household_products
            WHERE id IN (%s, %s)
            """,
            [source_product_id, target_product_id],
        ).fetchall()
        by_id = {str(row[0]): row for row in rows}
        source = by_id.get(source_product_id)
        target = by_id.get(target_product_id)
        if source is None or target is None:
            return False

        now = datetime.now(UTC).isoformat()
        # The (kind, value) unique constraint is global, so no repoint conflict.
        for table, column in (
            ("household_product_identifiers", "product_id"),
            ("household_purchase_items", "product_id"),
            ("household_product_price_observations", "product_id"),
            ("household_shopping_list_items", "product_id"),
            ("household_price_findings", "product_id"),
        ):
            conn.execute(
                f"UPDATE {table} SET {column} = %s, updated_at = %s WHERE {column} = %s",
                [target_product_id, now, source_product_id],
            )

        target_rule = self._active_product_rule(conn, target_product_id)
        source_rule = self._active_product_rule(conn, source_product_id)
        if source_rule is not None and target_rule is not None:
            conn.execute(
                "UPDATE household_transaction_rules SET enabled = FALSE, updated_at = %s WHERE id = %s",
                [now, str(source_rule[0])],
            )
        elif source_rule is not None:
            conn.execute(
                "UPDATE household_transaction_rules SET product_id = %s, updated_at = %s WHERE id = %s",
                [target_product_id, now, str(source_rule[0])],
            )

        # Fill target gaps from source before the source row goes away.
        conn.execute(
            """
            UPDATE household_products
            SET brand = COALESCE(brand, %s),
                package_display_label = COALESCE(package_display_label, %s),
                package_normalized_quantity = COALESCE(package_normalized_quantity, %s),
                package_normalized_unit = COALESCE(package_normalized_unit, %s),
                image_url = COALESCE(image_url, %s),
                updated_at = %s
            WHERE id = %s
            """,
            [source[1], source[2], source[3], source[4], source[5], now, target_product_id],
        )
        conn.execute("DELETE FROM household_products WHERE id = %s", [source_product_id])
        self.apply_product_rule_to_items(conn, product_id=target_product_id)
        return True

    def reassign_item(
        self,
        conn: Any,
        *,
        item_id: str,
        action: str,
        product_id: str | None = None,
    ) -> bool:
        """confirm | reassign | detach a purchase item's product link."""
        now = datetime.now(UTC).isoformat()
        if action == "confirm":
            row = conn.execute(
                """
                UPDATE household_purchase_items
                SET product_match_status = 'confirmed',
                    product_match_confidence = GREATEST(COALESCE(product_match_confidence, 0), 0.99),
                    updated_at = %s
                WHERE id = %s AND product_id IS NOT NULL
                RETURNING product_id
                """,
                [now, item_id],
            ).fetchone()
            if row is not None:
                self.apply_product_rule_to_items(conn, product_id=str(row[0]))
            return row is not None
        if action == "reassign":
            if not product_id:
                return False
            row = conn.execute(
                """
                UPDATE household_purchase_items
                SET product_id = %s,
                    product_match_status = 'confirmed',
                    product_match_confidence = 0.99,
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                [product_id, now, item_id],
            ).fetchone()
            if row is not None:
                conn.execute(
                    """
                    UPDATE household_product_price_observations
                    SET product_id = %s, updated_at = %s
                    WHERE purchase_item_id = %s
                    """,
                    [product_id, now, item_id],
                )
                self.apply_product_rule_to_items(conn, product_id=product_id)
            return row is not None
        if action == "detach":
            row = conn.execute(
                """
                UPDATE household_purchase_items
                SET product_id = NULL,
                    product_match_status = 'unmatched',
                    product_match_confidence = NULL,
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                [now, item_id],
            ).fetchone()
            if row is not None:
                conn.execute(
                    "DELETE FROM household_product_price_observations WHERE purchase_item_id = %s",
                    [item_id],
                )
            return row is not None
        return False

    @staticmethod
    def _active_product_rule(conn: Any, product_id: str) -> Any:
        return conn.execute(
            """
            SELECT id, category, essentiality
            FROM household_transaction_rules
            WHERE product_id = %s
              AND rule_type = 'product'
              AND enabled IS TRUE
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [product_id],
        ).fetchone()

    def apply_product_rule_to_items(self, conn: Any, *, product_id: str) -> int:
        """Re-apply the product's enabled rule to its non-manual items."""
        rule = self._active_product_rule(conn, product_id)
        if rule is None:
            return 0
        rows = conn.execute(
            """
            UPDATE household_purchase_items
            SET category = %s,
                essentiality = %s,
                categorization_source = 'product_rule',
                item_rule_id = %s,
                updated_at = %s
            WHERE product_id = %s
              AND categorization_source != 'manual'
            RETURNING id
            """,
            [
                str(rule[1]),
                str(rule[2]),
                str(rule[0]),
                datetime.now(UTC).isoformat(),
                product_id,
            ],
        ).fetchall()
        return len(rows)
