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

    def optimize(self, list_id: str) -> HouseholdShoppingList | None:
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
            """
            SELECT DISTINCT ON (product_id, metadata->>'vendor_key')
                   product_id, metadata->>'vendor_key' AS vendor_key,
                   total_price, unit_price, observed_date,
                   COALESCE((metadata->>'membership_required')::boolean, false) AS membership_required
            FROM household_product_price_observations
            WHERE source = 'vendor_quote'
              AND product_id = ANY(%s::uuid[])
              AND metadata->>'vendor_key' IS NOT NULL
            ORDER BY product_id, metadata->>'vendor_key', observed_date DESC, created_at DESC
            """,
            [product_ids],
        ).fetchall()
        today = datetime.now(UTC).date()
        quotes = []
        for row in rows:
            observed = row[4]
            age_days = (today - observed).days if observed else _FRESH_QUOTE_DAYS + 1
            quotes.append(
                {
                    "product_id": str(row[0]),
                    "vendor_key": str(row[1]),
                    "total_price": float(row[2] or 0.0),
                    "unit_price": to_float(row[3]),
                    "observed_date": iso_or_none(row[4]),
                    "membership_required": bool(row[5]),
                    "is_fresh": age_days <= _FRESH_QUOTE_DAYS,
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
    return profile.model_dump()
