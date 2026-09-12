"""Read views over purchase items, products, and price history (Purchases tab)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdItemLinkageBucket,
    HouseholdItemLinkageCoverage,
    HouseholdProductDetail,
    HouseholdProductIdentifier,
    HouseholdProductList,
    HouseholdProductPricePoint,
    HouseholdProductSummary,
    HouseholdPurchaseItem,
    HouseholdPurchaseItemReviewQueue,
    HouseholdUnknownPayingCard,
)
from app.services._household_finance_utils import iso_or_none, to_float
from app.services._household_item_linkage import build_linkage_coverage
from app.services._household_report_builder import _coerce_metadata, _extract_package_measure
from app.services.household_product_normalization_service import (
    HouseholdProductNormalizationService,
)
from app.services.household_unit_prices import unit_price_basis
from app.storage import get_storage

# Sparkline payload cap per product; detail view fetches a longer history.
_PRICE_POINT_CAP = 24
_DETAIL_OBSERVATION_CAP = 200
_DETAIL_ITEM_CAP = 50
_REVIEW_QUEUE_CAP = 100
_ACTIVE_PRODUCT_WINDOW_MONTHS = 18
_UNIT_LABELS = {
    "weight_oz": "oz",
    "volume_fl_oz": "fl oz",
    "count": "ct",
}

_PRODUCT_LATEST_SEEN_SQL = (
    "CASE "
    "WHEN obs.last_observed_date IS NULL THEN items.last_purchase_date "
    "WHEN items.last_purchase_date IS NULL THEN obs.last_observed_date "
    "WHEN obs.last_observed_date >= items.last_purchase_date "
    "THEN obs.last_observed_date "
    "ELSE items.last_purchase_date "
    "END"
)

_PRODUCT_SORT_COLUMNS = {
    "recent": _PRODUCT_LATEST_SEEN_SQL,
    "frequency": "COALESCE(items.purchase_count, 0)",
    "name": "LOWER(p.canonical_name)",
    "price": "latest_obs.total_price",
    "owner": "LOWER(COALESCE(owner_rule.owner_name, latest_item.owner_name, ''))",
    "review": "COALESCE(items.needs_review_count, 0)",
}


def _reliable_observation_sql(alias: str = "o") -> str:
    return (
        f"({alias}.source <> 'vendor_quote' OR "
        f"({alias}.metadata -> 'equivalence_confirmed' = 'true'::jsonb "
        f"AND {alias}.metadata ->> 'withdrawn_at' IS NULL))"
    )


def _price_point(row: Any) -> HouseholdProductPricePoint:
    """Shared row shape: observed_date, merchant, total, quantity, unit, source."""
    basis = unit_price_basis(
        description=str(_row_value(row, 6, "") or ""),
        metadata=_coerce_metadata(_row_value(row, 7, {})),
        line_total=row[2],
        packages=row[3],
        source=str(row[5]),
        quote_package_label=str(_row_value(row, 8, "") or ""),
    )
    return HouseholdProductPricePoint(
        observed_date=iso_or_none(row[0]) or "",
        merchant=str(row[1]) if row[1] else None,
        total_price=float(row[2] or 0.0),
        quantity=to_float(row[3]),
        unit_price=round(basis.unit_price, 4) if basis else None,
        unit_label=basis.unit_label if basis else None,
        package_label=basis.package_label if basis else None,
        package_quantity=basis.package_quantity if basis else None,
        basis_evidence=basis.evidence_text if basis else None,
        package_price=round(basis.package_price, 2) if basis else None,
        description=str(_row_value(row, 6, "") or "") or None,
        source=str(row[5] or ""),
    )


def _row_value(row: Any, index: int, default: Any = None) -> Any:
    try:
        return row[index]
    except IndexError:
        return default


def _unit_label(unit: str | None) -> str | None:
    if not unit:
        return None
    return _UNIT_LABELS.get(unit, unit.replace("_", " "))


_ITEM_SELECT = """
    SELECT i.id, i.transaction_id, i.product_id, p.canonical_name,
           i.product_match_status, i.product_match_confidence, i.purchase_date,
           m.canonical_name, i.description, i.quantity, i.unit_price, i.amount,
           i.allocated_amount, i.category, i.essentiality, i.categorization_source,
           i.metadata ->> 'owner_name', COALESCE(i.metadata ->> 'owner_source', 'none')
    FROM household_purchase_items i
    LEFT JOIN household_products p ON p.id = i.product_id
    LEFT JOIN household_merchants m ON m.id = i.merchant_id
"""


def _purchase_item(row: Any) -> HouseholdPurchaseItem:
    return HouseholdPurchaseItem(
        id=str(row[0]),
        transaction_id=str(row[1]) if row[1] is not None else None,
        product_id=str(row[2]) if row[2] is not None else None,
        product_name=str(row[3]) if row[3] else None,
        product_match_status=str(row[4] or "unmatched"),
        product_match_confidence=to_float(row[5]),
        purchase_date=iso_or_none(row[6]),
        merchant=str(row[7]) if row[7] else None,
        description=str(row[8] or ""),
        quantity=to_float(row[9]),
        unit_price=to_float(row[10]),
        amount=float(row[11] or 0.0),
        allocated_amount=to_float(row[12]),
        category=str(row[13] or ""),
        essentiality=str(row[14] or ""),
        categorization_source=str(row[15] or "suggested"),
        owner_name=str(row[16]) if row[16] else None,
        owner_source=str(row[17] or "none"),
    )


class HouseholdProductCatalogService:
    """Catalog, price-history, and review reads plus product-link writes."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.normalization_service = HouseholdProductNormalizationService()

    def list_products(
        self,
        *,
        search: str = "",
        sort: str = "recent",
        sort_dir: str = "desc",
        scope: str = "active",
        limit: int = 50,
        offset: int = 0,
    ) -> HouseholdProductList:
        normalized_search = (search or "").strip()
        sort_key = (sort or "recent").strip().lower()
        sort_column = _PRODUCT_SORT_COLUMNS.get(sort_key, _PRODUCT_SORT_COLUMNS["recent"])
        direction = "ASC" if (sort_dir or "desc").strip().lower() == "asc" else "DESC"
        nulls = "NULLS FIRST" if direction == "ASC" else "NULLS LAST"
        order_by = f"{sort_column} {direction} {nulls}"
        if sort_key != "recent":
            order_by = f"{order_by}, {_PRODUCT_LATEST_SEEN_SQL} DESC NULLS LAST"
        page_limit = max(1, min(int(limit), 200))
        page_offset = max(0, int(offset))

        active_sql = (
            f"COALESCE({_PRODUCT_LATEST_SEEN_SQL} >= "
            f"CURRENT_DATE - INTERVAL '{_ACTIVE_PRODUCT_WINDOW_MONTHS} months', FALSE) "
            "OR COALESCE(items.needs_review_count, 0) > 0 "
            "OR owner_rule.owner_name IS NOT NULL"
        )
        scope_key = (scope or "active").strip().lower()
        scope_clause = {
            "active": f"({active_sql})",
            "archived": f"NOT ({active_sql})",
            "all": "TRUE",
        }.get(scope_key, f"({active_sql})")

        where = scope_clause
        params: list[Any] = []
        if normalized_search:
            where = f"({where}) AND (p.canonical_name ILIKE %s OR p.brand ILIKE %s)"
            like = f"%{normalized_search}%"
            params = [like, like]

        sql = f"""
            WITH obs AS (
                SELECT product_id,
                       COUNT(*) AS observation_count,
                       MIN(observed_date) AS first_observed_date,
                       MAX(observed_date) AS last_observed_date
                FROM household_product_price_observations o
                WHERE {_reliable_observation_sql("o")}
                GROUP BY product_id
            ),
            items AS (
                SELECT product_id,
                       COUNT(*) AS purchase_count,
                       MAX(purchase_date) AS last_purchase_date,
                       COUNT(*) FILTER (
                           WHERE product_match_status = 'needs_review'
                       ) AS needs_review_count
                FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_id IS NOT NULL
                GROUP BY product_id
            ),
            latest_item AS (
                SELECT DISTINCT ON (product_id)
                       product_id,
                       id AS owner_item_id,
                       metadata ->> 'owner_name' AS owner_name,
                       COALESCE(metadata ->> 'owner_source', 'none') AS owner_source
                FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_id IS NOT NULL
                ORDER BY product_id, purchase_date DESC NULLS LAST, created_at DESC
            ),
            owner_rule AS (
                SELECT DISTINCT ON (product_id)
                       product_id,
                       metadata ->> 'owner_name' AS owner_name
                FROM household_transaction_rules
                WHERE rule_type = 'product'
                  AND enabled IS TRUE
                  AND NULLIF(TRIM(metadata ->> 'owner_name'), '') IS NOT NULL
                ORDER BY product_id, updated_at DESC
            ),
            latest_obs AS (
                SELECT DISTINCT ON (product_id)
                       product_id,
                       total_price / CASE WHEN source='vendor_quote' THEN 1 ELSE NULLIF(quantity,0) END AS total_price,
                       unit_price
                FROM household_product_price_observations
                WHERE {_reliable_observation_sql("household_product_price_observations")}
                ORDER BY product_id, observed_date DESC NULLS LAST, created_at DESC
            )
            SELECT p.id, p.canonical_name, p.brand, p.package_display_label, p.image_url,
                   COALESCE(items.purchase_count, 0) AS purchase_count,
                   COALESCE(obs.observation_count, 0) AS observation_count,
                   COALESCE(items.needs_review_count, 0) AS needs_review_count,
                   obs.first_observed_date,
                   obs.last_observed_date,
                   COUNT(*) OVER () AS total_count,
                   latest_item.owner_item_id,
                   COALESCE(owner_rule.owner_name, latest_item.owner_name) AS owner_name,
                   CASE
                     WHEN owner_rule.owner_name IS NOT NULL THEN 'product_rule'
                     ELSE COALESCE(latest_item.owner_source, 'none')
                   END AS owner_source,
                   CASE WHEN {active_sql} THEN 'active' ELSE 'archived' END AS catalog_status
            FROM household_products p
            LEFT JOIN obs ON obs.product_id = p.id
            LEFT JOIN items ON items.product_id = p.id
            LEFT JOIN latest_item ON latest_item.product_id = p.id
            LEFT JOIN owner_rule ON owner_rule.product_id = p.id
            LEFT JOIN latest_obs ON latest_obs.product_id = p.id
            WHERE {where}
            ORDER BY {order_by}, p.id ASC
            LIMIT %s OFFSET %s
        """

        with self.storage.connection() as conn:
            rows = conn.execute(sql, [*params, page_limit, page_offset]).fetchall()
            review_total_row = conn.execute(
                """
                SELECT COUNT(*) FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_match_status = 'needs_review'
                """
            ).fetchone()
            points_by_product = self._price_points(
                conn,
                product_ids=[str(row[0]) for row in rows],
                per_product_cap=_PRICE_POINT_CAP,
            )
            best_prices_by_product = self._best_researched_prices(
                conn,
                product_ids=[str(row[0]) for row in rows],
            )

        products = [
            self._summary(
                row,
                points_by_product.get(str(row[0]), []),
                best_prices_by_product.get(str(row[0])),
            )
            for row in rows
        ]
        return HouseholdProductList(
            generated_at=datetime.now(UTC).isoformat(),
            total_count=int(rows[0][10]) if rows else 0,
            needs_review_total=int(review_total_row[0]) if review_total_row else 0,
            offset=page_offset,
            limit=page_limit,
            returned_count=len(products),
            products=products,
        )

    @staticmethod
    def _summary(
        row: Any,
        points: list[HouseholdProductPricePoint],
        best_price: dict[str, Any] | None = None,
    ) -> HouseholdProductSummary:
        latest = points[-1] if points else None
        title_measure = _extract_package_measure(str(row[1] or ""), {})
        return HouseholdProductSummary(
            id=str(row[0]),
            canonical_name=str(row[1] or ""),
            brand=str(row[2]) if row[2] else None,
            package_display_label=(latest.package_label if latest else None)
            or (title_measure.display_label if title_measure else None),
            image_url=str(row[4]) if row[4] else None,
            purchase_count=int(row[5] or 0),
            observation_count=int(row[6] or 0),
            needs_review_count=int(row[7] or 0),
            first_observed_date=iso_or_none(row[8]),
            last_observed_date=iso_or_none(row[9]),
            latest_price=latest.package_price if latest else None,
            latest_unit_price=latest.unit_price if latest else None,
            latest_unit_label=latest.unit_label if latest else None,
            latest_description=latest.description if latest else None,
            latest_merchant=latest.merchant if latest else None,
            best_researched_vendor_key=(str(best_price["vendor_key"]) if best_price else None),
            best_researched_vendor=(str(best_price["vendor_name"]) if best_price else None),
            best_researched_total_price=(float(best_price["total_price"]) if best_price else None),
            best_researched_unit_price=(float(best_price["unit_price"]) if best_price else None),
            best_researched_unit_label=(str(best_price["unit_label"]) if best_price else None),
            best_researched_package_label=(
                str(best_price["package_label"])
                if best_price and best_price.get("package_label")
                else None
            ),
            best_researched_observed_date=(
                str(best_price["observed_date"]) if best_price else None
            ),
            best_researched_confidence=(
                to_float(best_price.get("confidence")) if best_price else None
            ),
            best_researched_url=(
                str(best_price["url"]) if best_price and best_price.get("url") else None
            ),
            best_researched_source=(
                str(best_price["source"]) if best_price and best_price.get("source") else None
            ),
            catalog_status=str(_row_value(row, 14, "active") or "active"),
            owner_item_id=str(row[11]) if _row_value(row, 11) else None,
            owner_name=str(row[12]) if _row_value(row, 12) else None,
            owner_source=str(_row_value(row, 13, "none") or "none"),
            price_points=points,
        )

    @staticmethod
    def _price_points(
        conn: Any,
        *,
        product_ids: list[str],
        per_product_cap: int,
    ) -> dict[str, list[HouseholdProductPricePoint]]:
        if not product_ids:
            return {}
        rows = conn.execute(
            f"""
            SELECT product_id, observed_date, merchant, total_price, quantity,
                   unit_price, source, description, row_metadata, package_display_label
            FROM (
                SELECT o.product_id::text AS product_id,
                       o.observed_date,
                       m.canonical_name AS merchant,
                       o.total_price,
                       o.quantity,
                       o.unit_price,
                       o.source,
                       COALESCE(i.description, p.canonical_name) AS description,
                       COALESCE(ir.row_metadata,'{{}}'::jsonb) || o.metadata AS row_metadata, o.package_display_label,
                       ROW_NUMBER() OVER (
                           PARTITION BY o.product_id
                           ORDER BY o.observed_date DESC, o.created_at DESC
                       ) AS recency_rank
                FROM household_product_price_observations o
                LEFT JOIN household_merchants m ON m.id = o.merchant_id
                JOIN household_products p ON p.id = o.product_id
                LEFT JOIN household_purchase_items i ON i.id = o.purchase_item_id
                LEFT JOIN household_import_rows ir ON ir.id = i.import_row_id
                WHERE o.product_id = ANY(%s::uuid[])
                  AND {_reliable_observation_sql("o")}
            ) recent
            WHERE recency_rank <= %s
            ORDER BY product_id, observed_date ASC, recency_rank DESC
            """,
            [product_ids, per_product_cap],
        ).fetchall()
        by_product: dict[str, list[HouseholdProductPricePoint]] = {}
        for row in rows:
            by_product.setdefault(str(row[0]), []).append(_price_point(row[1:]))
        return by_product

    @staticmethod
    def _best_researched_prices(
        conn: Any,
        *,
        product_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Lowest latest-per-store observation, never an availability claim.

        Normalize raw line amounts before ranking. Stored legacy package fields
        can contain parser mistakes and cannot select a winner safely in SQL.
        """
        if not product_ids:
            return {}
        rows = conn.execute(
            """
            SELECT o.product_id::text,
                   COALESCE(o.metadata ->> 'vendor_key', LOWER(m.canonical_name), o.source) AS vendor_key,
                   COALESCE(m.canonical_name, o.metadata ->> 'vendor_key', o.source),
                   o.total_price, o.quantity, o.package_display_label,
                   COALESCE(i.description, p.canonical_name), COALESCE(ir.row_metadata,'{}'::jsonb) || o.metadata,
                   o.observed_date, o.metadata, o.source
            FROM household_product_price_observations o
            JOIN household_products p ON p.id = o.product_id
            LEFT JOIN household_purchase_items i ON i.id = o.purchase_item_id
            LEFT JOIN household_import_rows ir ON ir.id = i.import_row_id
            LEFT JOIN household_merchants m ON m.id = o.merchant_id
            WHERE o.product_id = ANY(%s::uuid[]) AND o.total_price > 0
              AND o.observed_date <= CURRENT_DATE
              AND (i.id IS NULL OR i.removed IS NOT TRUE)
            ORDER BY o.observed_date DESC, o.created_at DESC
            """,
            [product_ids],
        ).fetchall()
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        actual_units: dict[str, str] = {}
        for row in rows:
            product_id, vendor_key = str(row[0]), str(row[1])
            metadata = _coerce_metadata(row[9])
            basis = unit_price_basis(
                description=str(row[6] or ""),
                metadata=_coerce_metadata(row[7]),
                line_total=row[3],
                packages=row[4],
                source=str(row[10]),
                quote_package_label=str(row[5] or ""),
            )
            if basis is None:
                continue
            if row[10] in {"receipt", "order_history"}:
                actual_units.setdefault(product_id, basis.unit_label)
            # Research can return substitutes; a confidence percentage is not
            # household confirmation of equivalence or a purchase observation.
            if row[10] == "vendor_quote" and (
                metadata.get("equivalence_confirmed") is not True or metadata.get("withdrawn_at")
            ):
                continue
            latest.setdefault(
                (product_id, vendor_key),
                {
                    "vendor_key": vendor_key,
                    "vendor_name": str(row[2] or vendor_key),
                    "total_price": round(basis.package_price, 2),
                    "unit_price": round(basis.unit_price, 4),
                    "package_label": basis.package_label,
                    "unit_label": basis.unit_label,
                    "observed_date": iso_or_none(row[8]),
                    "confidence": None,
                    "url": metadata.get("url"),
                    "source": str(row[10]),
                },
            )
        best: dict[str, dict[str, Any]] = {}
        for (product_id, _vendor), point in latest.items():
            if actual_units.get(product_id, point["unit_label"]) != point["unit_label"]:
                continue
            if product_id not in best or point["unit_price"] < best[product_id]["unit_price"]:
                best[product_id] = point
        return best

    def get_product_detail(self, product_id: str) -> HouseholdProductDetail | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                f"""
                WITH obs AS (
                    SELECT product_id,
                           COUNT(*) AS observation_count,
                           MIN(observed_date) AS first_observed_date,
                           MAX(observed_date) AS last_observed_date
                    FROM household_product_price_observations
                    WHERE product_id = %s
                      AND {_reliable_observation_sql("household_product_price_observations")}
                    GROUP BY product_id
                ),
                items AS (
                    SELECT product_id,
                           COUNT(*) AS purchase_count,
                           COUNT(*) FILTER (
                               WHERE product_match_status = 'needs_review'
                           ) AS needs_review_count
                    FROM household_purchase_items
                    WHERE removed IS NOT TRUE AND product_id = %s
                    GROUP BY product_id
                )
                SELECT p.id, p.canonical_name, p.brand, p.package_display_label,
                       p.image_url,
                       COALESCE(items.purchase_count, 0),
                       COALESCE(obs.observation_count, 0),
                       COALESCE(items.needs_review_count, 0),
                       obs.first_observed_date,
                       obs.last_observed_date
                FROM household_products p
                LEFT JOIN obs ON obs.product_id = p.id
                LEFT JOIN items ON items.product_id = p.id
                WHERE p.id = %s
                """,
                [product_id, product_id, product_id],
            ).fetchone()
            if row is None:
                return None
            observations = [
                _price_point(observation_row)
                for observation_row in conn.execute(
                    f"""
                    SELECT o.observed_date, m.canonical_name, o.total_price,
                           o.quantity, o.unit_price, o.source,
                           COALESCE(i.description, p.canonical_name), COALESCE(ir.row_metadata,'{{}}'::jsonb) || o.metadata AS row_metadata, o.package_display_label
                    FROM household_product_price_observations o
                    LEFT JOIN household_merchants m ON m.id = o.merchant_id
                    JOIN household_products p ON p.id = o.product_id
                    LEFT JOIN household_purchase_items i ON i.id = o.purchase_item_id
                    LEFT JOIN household_import_rows ir ON ir.id = i.import_row_id
                    WHERE o.product_id = %s
                      AND {_reliable_observation_sql("o")}
                    ORDER BY o.observed_date DESC, o.created_at DESC
                    LIMIT %s
                    """,
                    [product_id, _DETAIL_OBSERVATION_CAP],
                ).fetchall()
            ]
            observations.reverse()
            identifier_rows = conn.execute(
                """
                SELECT kind, value FROM household_product_identifiers
                WHERE product_id = %s
                ORDER BY kind ASC, value ASC
                """,
                [product_id],
            ).fetchall()
            item_rows = conn.execute(
                f"""
                {_ITEM_SELECT}
                WHERE i.removed IS NOT TRUE AND i.product_id = %s
                ORDER BY i.purchase_date DESC NULLS LAST, i.created_at DESC
                LIMIT %s
                """,
                [product_id, _DETAIL_ITEM_CAP],
            ).fetchall()
            best_prices_by_product = self._best_researched_prices(
                conn,
                product_ids=[product_id],
            )

        summary = self._summary(
            row,
            observations[-_PRICE_POINT_CAP:],
            best_prices_by_product.get(product_id),
        )
        return HouseholdProductDetail(
            generated_at=datetime.now(UTC).isoformat(),
            product=summary,
            identifiers=[
                HouseholdProductIdentifier(kind=str(r[0]), value=str(r[1])) for r in identifier_rows
            ],
            observations=observations,
            recent_items=[_purchase_item(r) for r in item_rows],
        )

    def list_transaction_items(self, transaction_id: str) -> list[HouseholdPurchaseItem]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"""
                {_ITEM_SELECT}
                WHERE i.removed IS NOT TRUE AND i.transaction_id = %s
                ORDER BY i.amount DESC, i.created_at ASC
                """,
                [transaction_id],
            ).fetchall()
        return [_purchase_item(row) for row in rows]

    def list_review_queue(self) -> HouseholdPurchaseItemReviewQueue:
        with self.storage.connection() as conn:
            total_row = conn.execute(
                """
                SELECT COUNT(*) FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_match_status = 'needs_review'
                """
            ).fetchone()
            rows = conn.execute(
                f"""
                {_ITEM_SELECT}
                WHERE i.removed IS NOT TRUE AND i.product_match_status = 'needs_review'
                ORDER BY i.purchase_date DESC NULLS LAST, i.created_at DESC
                LIMIT %s
                """,
                [_REVIEW_QUEUE_CAP],
            ).fetchall()
        return HouseholdPurchaseItemReviewQueue(
            generated_at=datetime.now(UTC).isoformat(),
            total_count=int(total_row[0]) if total_row else 0,
            items=[_purchase_item(row) for row in rows],
        )

    def linkage_coverage(self) -> HouseholdItemLinkageCoverage:
        """How much of the item layer is tied to money, and why the rest is not."""
        with self.storage.connection() as conn:
            coverage = build_linkage_coverage(conn)
        return HouseholdItemLinkageCoverage(
            generated_at=coverage.generated_at,
            total_items=coverage.total_items,
            linked_items=coverage.linked_items,
            addressable_items=coverage.addressable_items,
            addressable_linked_share=coverage.addressable_linked_share,
            feed_starts_on=iso_or_none(coverage.feed_starts_on),
            buckets=[HouseholdItemLinkageBucket(**bucket) for bucket in coverage.buckets],
            unknown_cards=[
                HouseholdUnknownPayingCard(
                    mask=card.mask,
                    item_count=card.item_count,
                    amount=card.amount,
                    first_seen=iso_or_none(card.first_seen),
                    last_seen=iso_or_none(card.last_seen),
                )
                for card in coverage.unknown_cards
            ],
        )

    def assign_product(
        self,
        *,
        item_id: str,
        action: str,
        product_id: str | None = None,
    ) -> bool:
        with self.storage.connection() as conn:
            changed = self.normalization_service.reassign_item(
                conn,
                item_id=item_id,
                action=action,
                product_id=product_id,
            )
            conn.commit()
        return changed

    def merge_products(self, *, source_product_id: str, target_product_id: str) -> bool:
        with self.storage.connection() as conn:
            merged = self.normalization_service.merge_products(
                conn,
                source_product_id=source_product_id,
                target_product_id=target_product_id,
            )
            conn.commit()
        return merged
