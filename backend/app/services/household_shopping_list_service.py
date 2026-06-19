"""Shopping-list CRUD, paste import, vendor profiles, and optimization."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdShoppingList,
    HouseholdShoppingListImportRequest,
    HouseholdShoppingListImportResponse,
    HouseholdShoppingListItem,
    HouseholdShoppingListRequest,
    HouseholdShoppingListsResponse,
    HouseholdShoppingListSuggestionDismissRequest,
    HouseholdShoppingListSuggestionItem,
    HouseholdShoppingListSuggestions,
    HouseholdVendorProfile,
    HouseholdVendorProfileList,
    HouseholdVendorProfileUpdate,
)
from app.services._household_finance_utils import iso_or_none, to_float
from app.services._household_report_builder import _normalized_item_key
from app.services._price_vendor_adapters import VENDOR_ADAPTERS
from app.services._shopping_list_optimizer import optimize_shopping_list
from app.storage import get_storage

LIST_PARSER_AGENT_SLUG = "household-list-parser"
_FRESH_QUOTE_DAYS = 14
_FRESH_ACTUAL_OBSERVATION_DAYS = 90
_MIN_VENDOR_QUOTE_CONFIDENCE = 0.7
_SUGGESTION_LOOKBACK_DAYS = 365
_SUGGESTION_DEFAULT_DAYS_AHEAD = 14
_SUGGESTION_DEFAULT_WATCH_DAYS = 45
_SUGGESTION_DEFAULT_LIMIT = 100
_SUGGESTION_MIN_PURCHASE_EVENTS = 3
_UNIT_LABELS = {
    "weight_oz": "oz",
    "volume_fl_oz": "fl oz",
    "count": "ct",
}


class HouseholdShoppingListService:
    def __init__(self) -> None:
        self.storage = get_storage()
        from app.agents.clients.agent_hub_client import AgentHubAPIClient  # noqa: PLC0415

        self._client_cls = AgentHubAPIClient

    def list_shopping_lists(self) -> HouseholdShoppingListsResponse:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, status, latest_optimization, created_at, updated_at
                FROM household_shopping_lists
                WHERE status <> 'deleted'
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
            items = self._items_for_lists(conn, [str(row[0]) for row in rows])
        return HouseholdShoppingListsResponse(
            generated_at=datetime.now(UTC).isoformat(),
            lists=[_list_model(row, items.get(str(row[0]), [])) for row in rows],
        )

    def create_shopping_list(self, payload: HouseholdShoppingListRequest) -> HouseholdShoppingList:
        list_id = str(uuid.uuid4())
        name = payload.name.strip() or "Shopping list"
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_shopping_lists (id, name, status)
                VALUES (%s, %s, 'active')
                """,
                [list_id, name],
            )
            self._replace_items(conn, list_id, payload.items)
            conn.commit()
            row = self._list_row(conn, list_id)
            items = self._items_for_lists(conn, [list_id]).get(list_id, [])
        return _list_model(row, items)

    def suggested_items(
        self,
        *,
        days_ahead: int = _SUGGESTION_DEFAULT_DAYS_AHEAD,
        watch_days: int = _SUGGESTION_DEFAULT_WATCH_DAYS,
        limit: int = _SUGGESTION_DEFAULT_LIMIT,
    ) -> HouseholdShoppingListSuggestions:
        """Suggest a grocery/household list from recurring product cadence."""
        normalized_days_ahead = max(1, min(int(days_ahead), 60))
        normalized_watch_days = max(normalized_days_ahead, min(int(watch_days), 120))
        normalized_limit = max(1, min(int(limit), 100))
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                WITH purchase_events AS (
                    SELECT p.id AS product_id,
                           p.canonical_name AS product_name,
                           i.purchase_date::date AS purchase_date,
                           SUM(i.amount) AS event_spend,
                           MAX(i.product_match_confidence) AS event_match_confidence
                    FROM household_purchase_items i
                    JOIN household_products p ON p.id = i.product_id
                    WHERE i.removed IS NOT TRUE
                      AND i.product_id IS NOT NULL
                      AND COALESCE(
                          (p.metadata->'shopping_list'->>'exclude_recurring')::boolean,
                          false
                      ) IS NOT TRUE
                      AND i.purchase_date >= CURRENT_DATE - (%s::int * INTERVAL '1 day')
                    GROUP BY p.id, p.canonical_name, i.purchase_date::date
                ),
                dated_events AS (
                    SELECT *,
                           LAG(purchase_date) OVER (
                               PARTITION BY product_id ORDER BY purchase_date
                           ) AS previous_purchase_date
                    FROM purchase_events
                ),
                cadence AS (
                    SELECT product_id,
                           product_name,
                           COUNT(*) AS purchase_count,
                           MIN(purchase_date) AS first_purchase_date,
                           MAX(purchase_date) AS last_purchase_date,
                           PERCENTILE_CONT(0.5) WITHIN GROUP (
                               ORDER BY purchase_date - previous_purchase_date
                           ) FILTER (
                               WHERE previous_purchase_date IS NOT NULL
                           ) AS median_gap_days,
                           STDDEV_POP(
                               (purchase_date - previous_purchase_date)::double precision
                           ) FILTER (
                               WHERE previous_purchase_date IS NOT NULL
                           ) AS gap_stddev_days,
                           SUM(event_spend) AS total_spend,
                           MAX(event_match_confidence) AS match_confidence
                    FROM dated_events
                    GROUP BY product_id, product_name
                    HAVING COUNT(*) >= %s
                ),
                latest_item AS (
                    SELECT DISTINCT ON (i.product_id)
                           i.product_id,
                           i.category AS latest_category,
                           COALESCE(m.canonical_name, m.display_name) AS latest_merchant
                    FROM household_purchase_items i
                    LEFT JOIN household_merchants m ON m.id = i.merchant_id
                    WHERE i.removed IS NOT TRUE
                      AND i.product_id IS NOT NULL
                    ORDER BY i.product_id, i.purchase_date DESC NULLS LAST,
                             i.created_at DESC
                ),
                latest_actual_price AS (
                    SELECT DISTINCT ON (product_id)
                           product_id,
                           total_price,
                           package_display_label,
                           package_normalized_unit
                    FROM household_product_price_observations
                    WHERE source <> 'vendor_quote'
                      AND package_normalized_quantity IS NOT NULL
                      AND package_normalized_quantity > 0
                      AND package_normalized_unit IS NOT NULL
                    ORDER BY product_id, observed_date DESC, created_at DESC
                ),
                open_list_items AS (
                    SELECT DISTINCT i.product_id
                    FROM household_shopping_list_items i
                    JOIN household_shopping_lists l ON l.id = i.shopping_list_id
                    WHERE l.status = 'active'
                      AND i.status = 'open'
                      AND i.product_id IS NOT NULL
                ),
                due_items AS (
                    SELECT c.*,
                           (
                               c.last_purchase_date
                               + GREATEST(1, ROUND(c.median_gap_days)::int)
                           )::date AS next_due_date
                    FROM cadence c
                    WHERE c.median_gap_days IS NOT NULL
                      AND c.median_gap_days >= 3
                      AND c.median_gap_days <= 180
                )
                SELECT d.product_id::text,
                       d.product_name,
                       d.purchase_count,
                       d.first_purchase_date,
                       d.last_purchase_date,
                       CAST(d.median_gap_days AS DOUBLE PRECISION),
                       CAST(d.gap_stddev_days AS DOUBLE PRECISION),
                       d.next_due_date,
                       d.next_due_date - CURRENT_DATE AS days_until_due,
                       CAST(d.total_spend AS DOUBLE PRECISION),
                       CAST(d.match_confidence AS DOUBLE PRECISION),
                       latest_item.latest_category,
                       latest_item.latest_merchant,
                       CAST(latest_actual_price.total_price AS DOUBLE PRECISION),
                       latest_actual_price.package_display_label,
                       latest_actual_price.package_normalized_unit,
                       open_list_items.product_id IS NOT NULL AS already_on_open_list,
                       COUNT(*) OVER () AS total_count
                FROM due_items d
                LEFT JOIN latest_item ON latest_item.product_id = d.product_id
                LEFT JOIN latest_actual_price
                       ON latest_actual_price.product_id = d.product_id
                LEFT JOIN open_list_items ON open_list_items.product_id = d.product_id
                WHERE d.next_due_date <= CURRENT_DATE + (%s::int * INTERVAL '1 day')
                ORDER BY d.next_due_date ASC, d.purchase_count DESC,
                         d.total_spend DESC, d.product_name ASC
                LIMIT %s
                """,
                [
                    _SUGGESTION_LOOKBACK_DAYS,
                    _SUGGESTION_MIN_PURCHASE_EVENTS,
                    normalized_watch_days,
                    normalized_limit,
                ],
            ).fetchall()
        items = [
            _suggestion_item(row, days_ahead=normalized_days_ahead)
            for row in rows
        ]
        total_count = int(rows[0][17]) if rows and len(rows[0]) > 17 else len(items)
        return HouseholdShoppingListSuggestions(
            generated_at=datetime.now(UTC).isoformat(),
            lookback_days=_SUGGESTION_LOOKBACK_DAYS,
            days_ahead=normalized_days_ahead,
            watch_days=normalized_watch_days,
            limit=normalized_limit,
            total_count=total_count,
            item_count=len(items),
            returned_count=len(items),
            has_more=total_count > len(items),
            buy_now_count=sum(1 for item in items if item.due_bucket == "buy_now"),
            soon_count=sum(1 for item in items if item.due_bucket == "soon"),
            watch_count=sum(1 for item in items if item.due_bucket == "watch"),
            items=items,
        )

    def dismiss_suggestion(
        self,
        product_id: str,
        payload: HouseholdShoppingListSuggestionDismissRequest | None = None,
    ) -> bool:
        """Exclude a product from future recurring-list suggestions."""
        reason = (payload.reason if payload is not None else "not_recurring").strip()
        if not reason:
            reason = "not_recurring"
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                UPDATE household_products
                SET metadata = COALESCE(metadata, '{}'::jsonb)
                    || jsonb_build_object(
                        'shopping_list',
                        COALESCE(metadata->'shopping_list', '{}'::jsonb)
                        || jsonb_build_object(
                            'exclude_recurring', true,
                            'exclude_recurring_reason', %s::text,
                            'exclude_recurring_at', CURRENT_TIMESTAMP
                        )
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                RETURNING id
                """,
                [reason, product_id],
            )
            changed = result.fetchone() is not None
            conn.commit()
        return changed

    def restore_suggestion(self, product_id: str) -> bool:
        """Allow a product to appear in recurring-list suggestions again."""
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                UPDATE household_products
                SET metadata = COALESCE(metadata, '{}'::jsonb)
                    || jsonb_build_object(
                        'shopping_list',
                        COALESCE(metadata->'shopping_list', '{}'::jsonb)
                        || jsonb_build_object(
                            'exclude_recurring', false,
                            'recurring_restored_at', CURRENT_TIMESTAMP
                        )
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                RETURNING id
                """,
                [product_id],
            )
            changed = result.fetchone() is not None
            conn.commit()
        return changed

    def update_shopping_list(
        self,
        list_id: str,
        payload: HouseholdShoppingListRequest,
    ) -> HouseholdShoppingList | None:
        with self.storage.connection() as conn:
            row = self._list_row(conn, list_id)
            if row is None:
                return None
            conn.execute(
                """
                UPDATE household_shopping_lists
                SET name = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [payload.name.strip() or "Shopping list", payload.status or "active", list_id],
            )
            self._replace_items(conn, list_id, payload.items)
            conn.commit()
            row = self._list_row(conn, list_id)
            items = self._items_for_lists(conn, [list_id]).get(list_id, [])
        return _list_model(row, items)

    def archive_shopping_list(self, list_id: str) -> bool:
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                UPDATE household_shopping_lists
                SET status = 'deleted', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [list_id],
            )
            conn.commit()
        return getattr(result, "rowcount", 0) != 0

    def import_items(
        self,
        list_id: str,
        payload: HouseholdShoppingListImportRequest,
    ) -> HouseholdShoppingListImportResponse | None:
        parsed = self._parse_items(payload.text)
        with self.storage.connection() as conn:
            row = self._list_row(conn, list_id)
            if row is None:
                return None
            if payload.replace:
                conn.execute("DELETE FROM household_shopping_list_items WHERE shopping_list_id = %s", [list_id])
                next_position = 0
            else:
                position_row = conn.execute(
                    """
                    SELECT COALESCE(MAX(position), -1) + 1
                    FROM household_shopping_list_items
                    WHERE shopping_list_id = %s
                    """,
                    [list_id],
                ).fetchone()
                next_position = int(
                    position_row[0] if position_row is not None else 0
                )
            matched = 0
            for index, item in enumerate(parsed):
                product_id, confidence = self._match_product(conn, item["name"])
                if product_id:
                    matched += 1
                self._insert_item(
                    conn,
                    list_id=list_id,
                    product_id=product_id,
                    free_text=item["name"] if product_id is None else None,
                    quantity=item.get("quantity"),
                    unit=item.get("unit"),
                    position=next_position + index,
                    metadata={"match_confidence": confidence, "source": "paste_import"},
                )
            conn.commit()
            row = self._list_row(conn, list_id)
            items = self._items_for_lists(conn, [list_id]).get(list_id, [])
        return HouseholdShoppingListImportResponse(
            shopping_list=_list_model(row, items),
            parsed_count=len(parsed),
            matched_count=matched,
        )

    def optimize(
        self,
        list_id: str,
        max_local_stores: int | None = 2,
    ) -> HouseholdShoppingList | None:
        with self.storage.connection() as conn:
            row = self._list_row(conn, list_id)
            if row is None:
                return None
            items = self._items_for_lists(conn, [list_id]).get(list_id, [])
            profiles = self._vendor_profiles(conn)
            quotes = self._quotes_for_items(conn, items)
            result = optimize_shopping_list(
                [_optimizer_item(item) for item in items],
                quotes,
                [_optimizer_profile(profile) for profile in profiles],
                max_local_stores=max_local_stores,
            )
            result["generated_at"] = datetime.now(UTC).isoformat()
            conn.execute(
                """
                UPDATE household_shopping_lists
                SET latest_optimization = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                [json.dumps(result), list_id],
            )
            conn.commit()
            row = self._list_row(conn, list_id)
            items = self._items_for_lists(conn, [list_id]).get(list_id, [])
        return _list_model(row, items)

    def list_vendor_profiles(self) -> HouseholdVendorProfileList:
        with self.storage.connection() as conn:
            profiles = self._vendor_profiles(conn)
            conn.commit()
        return HouseholdVendorProfileList(
            generated_at=datetime.now(UTC).isoformat(),
            vendors=profiles,
        )

    def update_vendor_profiles(
        self,
        payload: HouseholdVendorProfileUpdate,
    ) -> HouseholdVendorProfileList:
        with self.storage.connection() as conn:
            self._seed_vendor_profiles(conn)
            for vendor in payload.vendors:
                conn.execute(
                    """
                    UPDATE household_vendor_profiles
                    SET enabled = %s, delivery_fee = %s, pickup_fee = %s,
                        free_delivery_threshold = %s, membership_monthly_fee = %s,
                        membership_active = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE vendor_key = %s
                    """,
                    [
                        vendor.enabled,
                        vendor.delivery_fee,
                        vendor.pickup_fee,
                        vendor.free_delivery_threshold,
                        vendor.membership_monthly_fee,
                        vendor.membership_active,
                        vendor.vendor_key,
                    ],
                )
            profiles = self._vendor_profiles(conn)
            conn.commit()
        return HouseholdVendorProfileList(
            generated_at=datetime.now(UTC).isoformat(),
            vendors=profiles,
        )

    def _parse_items(self, text: str) -> list[dict[str, Any]]:
        prompt = (
            "Parse this shopping list into JSON array items with name, quantity, unit. "
            "Return JSON only.\n\n"
            f"Shopping list:\n{text.strip()}"
        )
        from agent_hub.models.content import MessageInput, TextContent  # noqa: PLC0415

        client = self._client_cls(agent_slug=LIST_PARSER_AGENT_SLUG, use_memory=False)
        try:
            response = client.complete_messages(
                messages=[MessageInput(role="user", content=[TextContent(text=prompt)])],
                purpose="household_shopping_list_import",
            )
        finally:
            client.close()
        try:
            parsed = parse_shopping_list_items(response.content)
        except ValueError:
            parsed = _fallback_parse_items(text)
        return parsed or _fallback_parse_items(text)

    @staticmethod
    def _match_product(conn: Any, name: str) -> tuple[str | None, float | None]:
        clean = name.strip()
        if not clean:
            return None, None
        normalized_key = _normalized_item_key("", clean)
        row = conn.execute(
            """
            SELECT product_id
            FROM household_product_identifiers
            WHERE kind = 'normalized_key' AND value = %s
            LIMIT 1
            """,
            [normalized_key],
        ).fetchone()
        if row is not None:
            return str(row[0]), 0.85
        row = conn.execute(
            """
            SELECT p.id
            FROM household_products p
            WHERE p.canonical_name ILIKE %s
            ORDER BY LENGTH(p.canonical_name), p.id
            LIMIT 1
            """,
            [f"%{clean}%"],
        ).fetchone()
        if row is not None:
            return str(row[0]), 0.7
        return None, None

    @staticmethod
    def _list_row(conn: Any, list_id: str) -> Any:
        return conn.execute(
            """
            SELECT id, name, status, latest_optimization, created_at, updated_at
            FROM household_shopping_lists
            WHERE id = %s AND status <> 'deleted'
            """,
            [list_id],
        ).fetchone()

    def _replace_items(
        self,
        conn: Any,
        list_id: str,
        items: list[HouseholdShoppingListItem] | None,
    ) -> None:
        if items is None:
            return
        conn.execute("DELETE FROM household_shopping_list_items WHERE shopping_list_id = %s", [list_id])
        for index, item in enumerate(items):
            self._insert_item(
                conn,
                list_id=list_id,
                product_id=item.product_id,
                free_text=item.free_text,
                quantity=item.quantity,
                unit=item.unit,
                status=item.status,
                position=index,
                metadata={"match_confidence": item.match_confidence},
            )

    @staticmethod
    def _insert_item(
        conn: Any,
        *,
        list_id: str,
        product_id: str | None,
        free_text: str | None,
        quantity: float | None,
        unit: str | None,
        position: int,
        status: str = "open",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO household_shopping_list_items (
                id, shopping_list_id, product_id, free_text, quantity, unit,
                status, position, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            [
                str(uuid.uuid4()),
                list_id,
                product_id,
                free_text.strip() if free_text else None,
                quantity,
                unit.strip() if unit else None,
                status,
                position,
                json.dumps(metadata or {}),
            ],
        )

    @staticmethod
    def _items_for_lists(conn: Any, list_ids: list[str]) -> dict[str, list[HouseholdShoppingListItem]]:
        if not list_ids:
            return {}
        rows = conn.execute(
            """
            SELECT i.shopping_list_id, i.id, i.product_id, p.canonical_name,
                   i.free_text, i.quantity, i.unit, i.status, i.position,
                   i.metadata, i.created_at, i.updated_at
            FROM household_shopping_list_items i
            LEFT JOIN household_products p ON p.id = i.product_id
            WHERE i.shopping_list_id = ANY(%s::uuid[])
            ORDER BY i.shopping_list_id, i.position, i.created_at
            """,
            [list_ids],
        ).fetchall()
        by_list: dict[str, list[HouseholdShoppingListItem]] = {}
        for row in rows:
            by_list.setdefault(str(row[0]), []).append(_item_model(row))
        return by_list

    def _vendor_profiles(self, conn: Any) -> list[HouseholdVendorProfile]:
        self._seed_vendor_profiles(conn)
        rows = conn.execute(
            """
            SELECT vendor_key, display_name, enabled, delivery_fee, pickup_fee,
                   free_delivery_threshold, membership_monthly_fee, membership_active
            FROM household_vendor_profiles
            ORDER BY vendor_key
            """
        ).fetchall()
        return [_vendor_profile(row) for row in rows]

    @staticmethod
    def _seed_vendor_profiles(conn: Any) -> None:
        for adapter in VENDOR_ADAPTERS:
            conn.execute(
                """
                INSERT INTO household_vendor_profiles (id, vendor_key, display_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (vendor_key) DO NOTHING
                """,
                [str(uuid.uuid4()), adapter.vendor_key, adapter.display_name],
            )

    @staticmethod
    def _quotes_for_items(conn: Any, items: list[HouseholdShoppingListItem]) -> list[dict[str, Any]]:
        product_ids = [item.product_id for item in items if item.product_id]
        if not product_ids:
            return []
        rows = conn.execute(
            f"""
            WITH latest_actual AS (
                SELECT DISTINCT ON (product_id)
                       product_id,
                       package_normalized_quantity,
                       package_normalized_unit
                FROM household_product_price_observations
                WHERE product_id = ANY(%s::uuid[])
                  AND source <> 'vendor_quote'
                  AND package_normalized_quantity IS NOT NULL
                  AND package_normalized_quantity > 0
                  AND package_normalized_unit IS NOT NULL
                ORDER BY product_id, observed_date DESC, created_at DESC
            ),
            comparable_observations AS (
                SELECT o.product_id,
                       CASE
                         WHEN o.metadata->>'vendor_key' IS NOT NULL
                           THEN o.metadata->>'vendor_key'
                         WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                           LIKE '%%amazon%%' THEN 'amazon'
                         WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                           LIKE '%%walmart%%' THEN 'walmart'
                         WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                           LIKE '%%publix%%' THEN 'publix'
                         WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                           LIKE '%%aldi%%' THEN 'aldi'
                         WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                           LIKE '%%costco%%' THEN 'costco'
                         ELSE LOWER(
                           REPLACE(
                             COALESCE(m.canonical_name, m.display_name, o.source),
                             ' ',
                             '_'
                           )
                         )
                       END AS vendor_key,
                       o.total_price,
                       CAST(
                           o.total_price / NULLIF(o.package_normalized_quantity, 0)
                           AS DOUBLE PRECISION
                       ) AS normalized_unit_price,
                       CAST(
                           (
                               o.total_price / NULLIF(o.package_normalized_quantity, 0)
                           )
                           * COALESCE(
                               latest_actual.package_normalized_quantity,
                               o.package_normalized_quantity
                           )
                           AS DOUBLE PRECISION
                       ) AS comparison_price,
                       o.package_display_label,
                       o.package_normalized_unit,
                       o.observed_date,
                       COALESCE((o.metadata->>'membership_required')::boolean, false)
                           AS membership_required,
                       CAST(NULLIF(o.metadata->>'confidence', '') AS DOUBLE PRECISION)
                           AS confidence,
                       o.metadata->>'url' AS url,
                       o.source,
                       ROW_NUMBER() OVER (
                           PARTITION BY o.product_id,
                             CASE
                               WHEN o.metadata->>'vendor_key' IS NOT NULL
                                 THEN o.metadata->>'vendor_key'
                               WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                                 LIKE '%%amazon%%' THEN 'amazon'
                               WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                                 LIKE '%%walmart%%' THEN 'walmart'
                               WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                                 LIKE '%%publix%%' THEN 'publix'
                               WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                                 LIKE '%%aldi%%' THEN 'aldi'
                               WHEN LOWER(COALESCE(m.canonical_name, m.display_name, ''))
                                 LIKE '%%costco%%' THEN 'costco'
                               ELSE LOWER(
                                 REPLACE(
                                   COALESCE(m.canonical_name, m.display_name, o.source),
                                   ' ',
                                   '_'
                                 )
                               )
                             END
                           ORDER BY
                               o.observed_date DESC,
                               o.total_price / NULLIF(o.package_normalized_quantity, 0) ASC,
                               o.created_at DESC
                       ) AS quote_rank
                FROM household_product_price_observations o
                LEFT JOIN household_merchants m ON m.id = o.merchant_id
                LEFT JOIN latest_actual ON latest_actual.product_id = o.product_id
                WHERE o.product_id = ANY(%s::uuid[])
                  AND o.total_price > 0
                  AND o.package_normalized_quantity IS NOT NULL
                  AND o.package_normalized_quantity > 0
                  AND o.package_normalized_unit IS NOT NULL
                  AND (
                      latest_actual.package_normalized_unit IS NULL
                      OR latest_actual.package_normalized_unit = o.package_normalized_unit
                  )
                  AND (
                      o.source <> 'vendor_quote'
                      OR (
                          jsonb_typeof(o.metadata -> 'confidence') = 'number'
                          AND (o.metadata ->> 'confidence')::double precision
                              >= {_MIN_VENDOR_QUOTE_CONFIDENCE}
                      )
                  )
            )
            SELECT product_id, vendor_key, total_price, normalized_unit_price,
                   comparison_price, package_display_label, package_normalized_unit,
                   observed_date, membership_required, confidence, url, source
            FROM comparable_observations
            WHERE quote_rank = 1
            """,
            [product_ids, product_ids],
        ).fetchall()
        today = datetime.now(UTC).date()
        quotes = []
        for row in rows:
            observed = row[7]
            age_days = (today - observed).days if observed else _FRESH_QUOTE_DAYS + 1
            quotes.append(
                {
                    "product_id": str(row[0]),
                    "vendor_key": str(row[1]),
                    "total_price": float(row[2] or 0.0),
                    "unit_price": to_float(row[3]),
                    "comparison_price": to_float(row[4]),
                    "package_label": str(row[5]) if row[5] else None,
                    "unit_label": _unit_label(str(row[6]) if row[6] else None),
                    "observed_date": iso_or_none(row[7]),
                    "membership_required": bool(row[8]),
                    "confidence": to_float(row[9]),
                    "url": str(row[10]) if row[10] else None,
                    "source": str(row[11] or ""),
                    "is_fresh": age_days
                    <= (
                        _FRESH_QUOTE_DAYS
                        if str(row[11] or "") == "vendor_quote"
                        else _FRESH_ACTUAL_OBSERVATION_DAYS
                    ),
                }
            )
        return quotes


def parse_shopping_list_items(content: str) -> list[dict[str, Any]]:
    payload = _extract_json(content)
    raw_items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError("List parser returned no item array.")
    parsed = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        parsed.append(
            {
                "name": name,
                "quantity": _optional_float(raw.get("quantity")),
                "unit": str(raw["unit"]).strip() if raw.get("unit") else None,
            }
        )
    return parsed


def _extract_json(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if match is None:
            raise ValueError("List parser returned no JSON.") from None
        return json.loads(match.group(1))


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fallback_parse_items(text: str) -> list[dict[str, Any]]:
    """Deterministic fallback when the Agent Hub parser returns malformed text."""
    parsed: list[dict[str, Any]] = []
    for line in re.split(r"[\n;,]+", text):
        cleaned = line.strip(" -•\t")
        if not cleaned:
            continue
        match = re.match(r"^(?P<quantity>\d+(?:\.\d+)?)\s+(?P<rest>.+)$", cleaned)
        quantity = _optional_float(match.group("quantity")) if match else None
        name = match.group("rest").strip() if match else cleaned
        parsed.append({"name": name, "quantity": quantity, "unit": None})
    return parsed


def _list_model(row: Any, items: list[HouseholdShoppingListItem]) -> HouseholdShoppingList:
    raw_optimization = row[3]
    latest_optimization = (
        raw_optimization if isinstance(raw_optimization, dict) else json.loads(raw_optimization or "null")
    )
    return HouseholdShoppingList(
        id=str(row[0]),
        name=str(row[1]),
        status=str(row[2] or "active"),
        items=items,
        latest_optimization=latest_optimization,
        created_at=iso_or_none(row[4]),
        updated_at=iso_or_none(row[5]),
    )


def _item_model(row: Any) -> HouseholdShoppingListItem:
    metadata = row[9] if isinstance(row[9], dict) else json.loads(row[9] or "{}")
    return HouseholdShoppingListItem(
        id=str(row[1]),
        product_id=str(row[2]) if row[2] is not None else None,
        product_name=str(row[3]) if row[3] else None,
        free_text=str(row[4]) if row[4] else None,
        quantity=to_float(row[5]),
        unit=str(row[6]) if row[6] else None,
        status=str(row[7] or "open"),
        position=int(row[8] or 0),
        match_confidence=to_float(metadata.get("match_confidence")),
        created_at=iso_or_none(row[10]),
        updated_at=iso_or_none(row[11]),
    )


def _vendor_profile(row: Any) -> HouseholdVendorProfile:
    return HouseholdVendorProfile(
        vendor_key=str(row[0]),
        display_name=str(row[1] or row[0]),
        enabled=bool(row[2]),
        delivery_fee=to_float(row[3]),
        pickup_fee=to_float(row[4]),
        free_delivery_threshold=to_float(row[5]),
        membership_monthly_fee=to_float(row[6]),
        membership_active=bool(row[7]),
    )


def _suggestion_item(row: Any, *, days_ahead: int) -> HouseholdShoppingListSuggestionItem:
    median_gap = to_float(row[5])
    gap_stddev = to_float(row[6])
    days_until_due = int(row[8]) if row[8] is not None else None
    already_on_open_list = bool(row[16])
    confidence = _suggestion_confidence(
        purchase_count=int(row[2] or 0),
        median_gap_days=median_gap,
        gap_stddev_days=gap_stddev,
        match_confidence=to_float(row[10]),
        has_package=bool(row[14]) and bool(row[15]),
        days_until_due=days_until_due,
        days_ahead=days_ahead,
    )
    bucket = _suggestion_bucket(days_until_due, days_ahead=days_ahead)
    return HouseholdShoppingListSuggestionItem(
        product_id=str(row[0]),
        product_name=str(row[1] or ""),
        purchase_count=int(row[2] or 0),
        first_purchase_date=iso_or_none(row[3]),
        last_purchase_date=iso_or_none(row[4]),
        median_gap_days=round(median_gap, 1) if median_gap is not None else None,
        next_due_date=iso_or_none(row[7]),
        days_until_due=days_until_due,
        due_bucket=bucket,
        confidence=confidence,
        reason=_suggestion_reason(days_until_due, median_gap),
        latest_category=str(row[11]) if row[11] else None,
        latest_merchant=str(row[12]) if row[12] else None,
        latest_price=to_float(row[13]),
        package_label=str(row[14]) if row[14] else None,
        unit_label=_unit_label(str(row[15]) if row[15] else None),
        already_on_open_list=already_on_open_list,
        selected_by_default=(
            bucket in {"buy_now", "soon"}
            and confidence >= 0.65
            and not already_on_open_list
        ),
    )


def _suggestion_bucket(days_until_due: int | None, *, days_ahead: int) -> str:
    if days_until_due is None:
        return "watch"
    if days_until_due <= 0:
        return "buy_now"
    if days_until_due <= days_ahead:
        return "soon"
    return "watch"


def _suggestion_confidence(
    *,
    purchase_count: int,
    median_gap_days: float | None,
    gap_stddev_days: float | None,
    match_confidence: float | None,
    has_package: bool,
    days_until_due: int | None,
    days_ahead: int,
) -> float:
    score = 0.45
    if purchase_count >= 6:
        score += 0.18
    elif purchase_count >= 4:
        score += 0.12
    elif purchase_count >= _SUGGESTION_MIN_PURCHASE_EVENTS:
        score += 0.07

    if median_gap_days and median_gap_days > 0 and gap_stddev_days is not None:
        ratio = gap_stddev_days / median_gap_days
        if ratio <= 0.35:
            score += 0.18
        elif ratio <= 0.75:
            score += 0.10
        else:
            score += 0.03

    if match_confidence is not None:
        score += max(0.0, min(match_confidence, 1.0)) * 0.08
    if has_package:
        score += 0.05
    if days_until_due is not None and days_until_due <= days_ahead:
        score += 0.08
    if days_until_due is not None and days_until_due < -days_ahead:
        score -= 0.05
    return round(max(0.0, min(score, 0.95)), 2)


def _suggestion_reason(days_until_due: int | None, median_gap_days: float | None) -> str:
    cadence = (
        f"usually every {round(median_gap_days)} days"
        if median_gap_days is not None
        else "recurring purchase"
    )
    if days_until_due is None:
        return cadence
    if days_until_due < 0:
        return f"Overdue by {abs(days_until_due)} day{'s' if abs(days_until_due) != 1 else ''}; {cadence}."
    if days_until_due == 0:
        return f"Due today; {cadence}."
    return f"Due in {days_until_due} day{'s' if days_until_due != 1 else ''}; {cadence}."


def _optimizer_item(item: HouseholdShoppingListItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_name": item.product_name,
        "free_text": item.free_text,
        "quantity": item.quantity,
        "unit": item.unit,
        "status": item.status,
        "match_confidence": item.match_confidence,
    }


def _optimizer_profile(profile: HouseholdVendorProfile) -> dict[str, Any]:
    payload = profile.model_dump()
    payload["is_local_store"] = profile.vendor_key != "amazon"
    return payload


def _unit_label(unit: str | None) -> str | None:
    if not unit:
        return None
    return _UNIT_LABELS.get(unit, unit.replace("_", " "))
