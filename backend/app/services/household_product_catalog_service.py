"""Read views over purchase items, products, and price history (Purchases tab)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdProductDetail,
    HouseholdProductIdentifier,
    HouseholdProductList,
    HouseholdProductPricePoint,
    HouseholdProductSummary,
    HouseholdPurchaseItem,
    HouseholdPurchaseItemList,
    HouseholdPurchaseItemReviewQueue,
)
from app.services._household_finance_utils import iso_or_none, to_float
from app.services.household_product_normalization_service import (
    HouseholdProductNormalizationService,
)
from app.storage import get_storage

# Sparkline payload cap per product; detail view fetches a longer history.
_PRICE_POINT_CAP = 24
_DETAIL_OBSERVATION_CAP = 200
_DETAIL_ITEM_CAP = 50
_REVIEW_QUEUE_CAP = 100

_PRODUCT_SORTS = {
    "recent": "last_observed_date DESC NULLS LAST, purchase_count DESC",
    "frequency": "purchase_count DESC, last_observed_date DESC NULLS LAST",
    "name": "LOWER(p.canonical_name) ASC",
}


def _price_point(row: Any) -> HouseholdProductPricePoint:
    """Shared row shape: observed_date, merchant, total, quantity, unit, source."""
    return HouseholdProductPricePoint(
        observed_date=iso_or_none(row[0]) or "",
        merchant=str(row[1]) if row[1] else None,
        total_price=float(row[2] or 0.0),
        quantity=to_float(row[3]),
        unit_price=to_float(row[4]),
        source=str(row[5] or ""),
    )


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
        limit: int = 50,
        offset: int = 0,
    ) -> HouseholdProductList:
        normalized_search = (search or "").strip()
        order_by = _PRODUCT_SORTS.get((sort or "recent").strip().lower(), _PRODUCT_SORTS["recent"])
        page_limit = max(1, min(int(limit), 200))
        page_offset = max(0, int(offset))

        where = "TRUE"
        params: list[Any] = []
        if normalized_search:
            where = "(p.canonical_name ILIKE %s OR p.brand ILIKE %s)"
            like = f"%{normalized_search}%"
            params = [like, like]

        sql = f"""
            WITH obs AS (
                SELECT product_id,
                       COUNT(*) AS observation_count,
                       MIN(observed_date) AS first_observed_date,
                       MAX(observed_date) AS last_observed_date
                FROM household_product_price_observations
                GROUP BY product_id
            ),
            items AS (
                SELECT product_id,
                       COUNT(*) AS purchase_count,
                       COUNT(*) FILTER (
                           WHERE product_match_status = 'needs_review'
                       ) AS needs_review_count
                FROM household_purchase_items
                WHERE removed IS NOT TRUE AND product_id IS NOT NULL
                GROUP BY product_id
            )
            SELECT p.id, p.canonical_name, p.brand, p.package_display_label, p.image_url,
                   COALESCE(items.purchase_count, 0) AS purchase_count,
                   COALESCE(obs.observation_count, 0) AS observation_count,
                   COALESCE(items.needs_review_count, 0) AS needs_review_count,
                   obs.first_observed_date,
                   obs.last_observed_date,
                   COUNT(*) OVER () AS total_count
            FROM household_products p
            LEFT JOIN obs ON obs.product_id = p.id
            LEFT JOIN items ON items.product_id = p.id
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

        products = [
            self._summary(row, points_by_product.get(str(row[0]), []))
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
        row: Any, points: list[HouseholdProductPricePoint]
    ) -> HouseholdProductSummary:
        latest = points[-1] if points else None
        return HouseholdProductSummary(
            id=str(row[0]),
            canonical_name=str(row[1] or ""),
            brand=str(row[2]) if row[2] else None,
            package_display_label=str(row[3]) if row[3] else None,
            image_url=str(row[4]) if row[4] else None,
            purchase_count=int(row[5] or 0),
            observation_count=int(row[6] or 0),
            needs_review_count=int(row[7] or 0),
            first_observed_date=iso_or_none(row[8]),
            last_observed_date=iso_or_none(row[9]),
            latest_price=latest.total_price if latest else None,
            latest_unit_price=latest.unit_price if latest else None,
            latest_merchant=latest.merchant if latest else None,
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
            """
            SELECT product_id, observed_date, merchant, total_price, quantity,
                   unit_price, source
            FROM (
                SELECT o.product_id::text AS product_id,
                       o.observed_date,
                       m.canonical_name AS merchant,
                       o.total_price,
                       o.quantity,
                       o.unit_price,
                       o.source,
                       ROW_NUMBER() OVER (
                           PARTITION BY o.product_id
                           ORDER BY o.observed_date DESC, o.created_at DESC
                       ) AS recency_rank
                FROM household_product_price_observations o
                LEFT JOIN household_merchants m ON m.id = o.merchant_id
                WHERE o.product_id = ANY(%s::uuid[])
            ) recent
            WHERE recency_rank <= %s
            ORDER BY product_id, observed_date ASC
            """,
            [product_ids, per_product_cap],
        ).fetchall()
        by_product: dict[str, list[HouseholdProductPricePoint]] = {}
        for row in rows:
            by_product.setdefault(str(row[0]), []).append(_price_point(row[1:7]))
        return by_product

    def get_product_detail(self, product_id: str) -> HouseholdProductDetail | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                WITH obs AS (
                    SELECT product_id,
                           COUNT(*) AS observation_count,
                           MIN(observed_date) AS first_observed_date,
                           MAX(observed_date) AS last_observed_date
                    FROM household_product_price_observations
                    WHERE product_id = %s
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
                    """
                    SELECT o.observed_date, m.canonical_name, o.total_price,
                           o.quantity, o.unit_price, o.source
                    FROM household_product_price_observations o
                    LEFT JOIN household_merchants m ON m.id = o.merchant_id
                    WHERE o.product_id = %s
                    ORDER BY o.observed_date ASC, o.created_at ASC
                    LIMIT %s
                    """,
                    [product_id, _DETAIL_OBSERVATION_CAP],
                ).fetchall()
            ]
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

        summary = self._summary(row, observations[-_PRICE_POINT_CAP:])
        return HouseholdProductDetail(
            generated_at=datetime.now(UTC).isoformat(),
            product=summary,
            identifiers=[
                HouseholdProductIdentifier(kind=str(r[0]), value=str(r[1]))
                for r in identifier_rows
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

    def list_items(
        self,
        *,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> HouseholdPurchaseItemList:
        normalized_search = (search or "").strip()
        page_limit = max(1, min(int(limit), 200))
        page_offset = max(0, int(offset))
        where = "i.removed IS NOT TRUE"
        params: list[Any] = []
        if normalized_search:
            like = f"%{normalized_search}%"
            where += """
              AND (
                i.description ILIKE %s
                OR p.canonical_name ILIKE %s
                OR m.canonical_name ILIKE %s
              )
            """
            params.extend([like, like, like])

        with self.storage.connection() as conn:
            total_row = conn.execute(
                f"""
                SELECT COUNT(*)
                FROM household_purchase_items i
                LEFT JOIN household_products p ON p.id = i.product_id
                LEFT JOIN household_merchants m ON m.id = i.merchant_id
                WHERE {where}
                """,
                params,
            ).fetchone()
            rows = conn.execute(
                f"""
                {_ITEM_SELECT}
                WHERE {where}
                ORDER BY i.purchase_date DESC NULLS LAST, i.created_at DESC
                LIMIT %s OFFSET %s
                """,
                [*params, page_limit, page_offset],
            ).fetchall()

        return HouseholdPurchaseItemList(
            generated_at=datetime.now(UTC).isoformat(),
            total_count=int(total_row[0]) if total_row else 0,
            offset=page_offset,
            limit=page_limit,
            returned_count=len(rows),
            items=[_purchase_item(row) for row in rows],
        )

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
