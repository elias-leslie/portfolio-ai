"""Confirmed packages and offers for a bounded set of repeat purchases.

Shelf tags remain price evidence. Neither a comparison nor an offer creates a
purchase or infers who bought it. All conditions require an adult's confirmation.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from app.models.household_shopping_pilot import (
    ComparisonResult,
    FamilyConfirmation,
    OfferConfirmation,
    PackageConfirmation,
    PilotProduct,
    ShoppingComparison,
)
from app.services._household_price_location import shopping_today
from app.services._household_report_builder import _coerce_metadata, _extract_package_measure
from app.services.household_identity import HouseholdIdentity, require_adult
from app.services.household_unit_prices import offer_is_ready, unit_price_basis
from app.storage import get_storage

PILOT_LIMIT = 25


def _fingerprint(row: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {key: row[key] for key in ("id", "description", "total", "packages", "metadata")},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


def _actual_rows(conn: Any, product_ids: list[str]) -> list[dict[str, Any]]:
    if not product_ids:
        return []
    rows = conn.execute(
        """
        SELECT o.id::text, o.product_id::text, COALESCE(i.description,p.canonical_name),
               o.total_price, o.quantity, o.observed_date, o.source,
               COALESCE(ir.row_metadata,'{}'::jsonb) || o.metadata,
               COALESCE(m.canonical_name,''), p.canonical_name, i.transaction_id::text
        FROM household_product_price_observations o
        JOIN household_products p ON p.id=o.product_id
        LEFT JOIN household_purchase_items i ON i.id=o.purchase_item_id
        LEFT JOIN household_import_rows ir ON ir.id=i.import_row_id
        LEFT JOIN household_merchants m ON m.id=o.merchant_id
        WHERE o.product_id=ANY(%s::uuid[]) AND o.source IN ('receipt','order_history')
          AND o.total_price>0 AND o.observed_date<=CURRENT_DATE
          AND (i.id IS NULL OR i.removed IS NOT TRUE)
        ORDER BY o.observed_date DESC, o.created_at DESC
    """,
        [product_ids],
    ).fetchall()
    return [
        dict(
            zip(
                (
                    "id",
                    "product_id",
                    "description",
                    "total",
                    "packages",
                    "date",
                    "source",
                    "metadata",
                    "store",
                    "name",
                    "transaction_id",
                ),
                row,
                strict=True,
            )
        )
        for row in rows
    ]


def _basis(row: dict[str, Any]):
    return unit_price_basis(
        description=row["description"],
        metadata=_coerce_metadata(row["metadata"]),
        line_total=row["total"],
        packages=row["packages"],
        source=row["source"],
    )


def _purchase_comparison(row: dict[str, Any] | None, offers: list[Any]) -> dict[str, Any] | None:
    # Only a linked receipt is evidence of actual spending. An unmatched camera
    # upload or order history cannot establish realized savings.
    if not row or row["source"] != "receipt" or not row["transaction_id"]:
        return None
    basis = _basis(row)
    if basis is None:
        return None
    for offer in offers:
        meta = _coerce_metadata(offer[5])
        baseline_price = meta.get("baseline_unit_price")
        if not isinstance(baseline_price, (int, float)) or baseline_price <= 0:
            continue
        if (
            not 0 <= (row["date"] - offer[4]).days <= 14
            or meta.get("baseline_observation_id") == row["id"]
        ):
            continue
        offer_basis = unit_price_basis(
            description="",
            metadata={},
            line_total=offer[2],
            packages=1,
            source="vendor_quote",
            quote_package_label=offer[3] or "",
        )
        if offer_basis and offer_basis.unit == basis.unit:
            return {
                "date": str(row["date"]),
                "paid": basis.line_total,
                "difference": round(
                    (baseline_price - basis.unit_price)
                    * basis.package_quantity
                    * basis.package_count,
                    2,
                ),
                "transaction_id": row["transaction_id"],
                "explanation": "Linked receipt versus the earlier purchase price for equal contents. This measures a price difference; it does not prove the offer caused it.",
            }
    return None


class HouseholdShoppingPilot:
    def __init__(self) -> None:
        self.storage = get_storage()

    def products(self, conn: Any) -> list[PilotProduct]:
        rows = conn.execute(
            """
            SELECT p.id::text, (array_agg(i.description ORDER BY i.purchase_date DESC, i.created_at DESC))[1],
                   array_agg(DISTINCT m.canonical_name) FILTER (WHERE m.canonical_name IS NOT NULL)
            FROM household_products p JOIN household_purchase_items i ON i.product_id=p.id
            LEFT JOIN household_merchants m ON m.id=i.merchant_id
            WHERE i.removed IS NOT TRUE AND i.purchase_date>=CURRENT_DATE-INTERVAL '365 days'
              AND i.purchase_date<=CURRENT_DATE AND i.category IN ('Groceries','Household')
            GROUP BY p.id HAVING COUNT(DISTINCT i.purchase_date)>=2
            ORDER BY COUNT(DISTINCT i.purchase_date) DESC, MAX(i.purchase_date) DESC, p.id
            LIMIT %s
        """,
            [200],
        ).fetchall()
        staples = [
            row
            for row in rows
            if re.search(
                r"\b(honey|coffee|oil|rice|soap|cleanser|detergent|litter|cat food|dog food|crackers|sauce|seeds|seaweed|supplement|vitamin|vitamins|protein|collagen|creatine|magnesium|turmeric|milk|flour|sugar|pasta|oats|oatmeal|toilet paper|paper towels|beans|nuts|butter|shampoo|conditioner|toothpaste|deodorant|diapers|wipes)\b",
                row[1],
                re.I,
            )
            and not re.search(
                r"\b(dispenser|sprayer|cruet|container|jacket|case|cover)\b", row[1], re.I
            )
        ]
        return [
            PilotProduct(id=row[0], name=row[1], stores=row[2] or [])
            for row in staples[:PILOT_LIMIT]
        ]

    def review(self, identity: HouseholdIdentity) -> list[dict[str, Any]]:
        require_adult(identity)
        with self.storage.connection() as conn:
            products = self.products(conn)
            actual = _actual_rows(conn, [p.id for p in products])
            offer_rows = conn.execute(
                """SELECT id::text,product_id::text,total_price,package_display_label,
                observed_date,metadata FROM household_product_price_observations
                WHERE product_id=ANY(%s::uuid[]) AND source='vendor_quote'
                  AND metadata->>'confirmed_by' IS NOT NULL
                ORDER BY observed_date DESC,created_at DESC""",
                [[p.id for p in products]],
            ).fetchall()
            family_rows = conn.execute(
                "SELECT id::text, metadata->'comparison_family' FROM household_products WHERE id=ANY(%s::uuid[])",
                [[p.id for p in products]],
            ).fetchall()
        families = dict(family_rows)
        result = []
        for product in products:
            row = next((r for r in actual if r["product_id"] == product.id), None)
            basis = _basis(row) if row else None
            result.append(
                {
                    **product.model_dump(),
                    "family": families.get(product.id),
                    "offers": [
                        {
                            "id": q[0],
                            "price": float(q[2]),
                            "package_label": q[3] or "",
                            "date": str(q[4]),
                            "store": q[5].get("store", ""),
                            "title": q[5].get("title", ""),
                            "conditions": q[5].get("conditions", "")
                            + " · Valid through "
                            + str(q[5].get("valid_until") or "unknown"),
                            "ready": offer_is_ready(q[5], q[4], today=shopping_today()),
                        }
                        for q in offer_rows
                        if q[1] == product.id
                    ][:10],
                    "purchase_comparison": _purchase_comparison(
                        row, [q for q in offer_rows if q[1] == product.id]
                    ),
                    "baseline": {
                        "observation_id": row["id"],
                        "fingerprint": _fingerprint(row),
                        "description": row["description"],
                        "date": str(row["date"]),
                        "line_total": float(row["total"]),
                        "packages": float(row["packages"]) if row["packages"] else None,
                        "package_label": basis.package_label if basis else None,
                        "unit_price": round(basis.unit_price, 4) if basis else None,
                        "unit": basis.unit_label if basis else None,
                    }
                    if row
                    else None,
                }
            )
        return result

    def confirm_package(
        self, identity: HouseholdIdentity, product_id: str, payload: PackageConfirmation
    ) -> None:
        require_adult(identity)
        with self.storage.connection() as conn:
            if product_id not in {p.id for p in self.products(conn)}:
                raise HTTPException(404, "Choose an item in the current shopping pilot.")
            conn.execute("SELECT id FROM household_products WHERE id=%s FOR UPDATE", [product_id])
            rows = _actual_rows(conn, [product_id])
            if not rows or _fingerprint(rows[0]) != payload.fingerprint:
                raise HTTPException(
                    409, "Purchase evidence changed. Reload before confirming its package."
                )
            measure = _extract_package_measure(payload.package_label, {})
            if measure is None:
                raise HTTPException(
                    422, "Use a clear content size, such as 2 x 32 fl oz or 150 ct."
                )
            confirmation = {
                "package_label": payload.package_label,
                "packages": payload.packages,
                "evidence": payload.evidence,
                "confirmed_by": identity.member_id or "local",
                "confirmed_at": datetime.now(UTC).isoformat(),
            }
            # The line amount and original imported quantity remain untouched.
            conn.execute(
                "UPDATE household_product_price_observations SET metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb WHERE id=%s",
                [json.dumps({"package_confirmation": confirmation}), rows[0]["id"]],
            )
            conn.commit()

    def confirm_family(self, identity: HouseholdIdentity, payload: FamilyConfirmation) -> None:
        require_adult(identity)
        ids = list(dict.fromkeys(str(value) for value in payload.product_ids))
        if len(ids) < 2:
            raise HTTPException(422, "Choose two distinct products.")
        with self.storage.connection() as conn:
            if not set(ids).issubset({p.id for p in self.products(conn)}):
                raise HTTPException(422, "Choose products in the current pilot.")
            actual = _actual_rows(conn, ids)
            latest = {pid: next((r for r in actual if r["product_id"] == pid), None) for pid in ids}
            bases = [_basis(row) if row else None for row in latest.values()]
            if any(b is None for b in bases) or len({b.unit for b in bases if b}) != 1:
                raise HTTPException(
                    422, "Confirm compatible package units before grouping substitutes."
                )
            family = {
                "id": str(uuid.uuid4()),
                "name": payload.name,
                "purpose": payload.purpose,
                "confirmed_by": identity.member_id or "local",
                "confirmed_at": datetime.now(UTC).isoformat(),
            }
            conn.execute(
                "UPDATE household_products SET metadata=COALESCE(metadata,'{}'::jsonb)||%s::jsonb WHERE id=ANY(%s::uuid[])",
                [json.dumps({"comparison_family": family}), ids],
            )
            conn.commit()

    def confirm_offer(self, identity: HouseholdIdentity, payload: OfferConfirmation) -> str:
        require_adult(identity)
        today = shopping_today()
        if not 0 <= (today - payload.observed_date).days <= 14:
            raise HTTPException(422, "Confirm a price observed within the last 14 days.")
        if (
            not payload.observed_date <= today <= payload.valid_until
            or (payload.valid_until - payload.observed_date).days > 14
        ):
            raise HTTPException(
                422,
                "Use the earliest offer or coupon expiry, no more than 14 days after checking the price.",
            )
        net = round(payload.price + payload.fees - payload.coupon, 2)
        if net <= 0:
            raise HTTPException(
                422, "The price including fees and applicable coupon must be positive."
            )
        basis = unit_price_basis(
            description=payload.title,
            metadata={},
            line_total=net,
            packages=1,
            source="vendor_quote",
            quote_package_label=payload.package_label,
        )
        if basis is None:
            raise HTTPException(422, "Confirm the total package contents, including any multipack.")
        with self.storage.connection() as conn:
            if str(payload.product_id) not in {p.id for p in self.products(conn)}:
                raise HTTPException(422, "Choose an item in the current shopping pilot.")
            actual = _actual_rows(conn, [str(payload.product_id)])
            baseline = _basis(actual[0]) if actual else None
            if baseline is None or baseline.unit != basis.unit:
                raise HTTPException(
                    422, "Confirm the purchase's package size and the offer's matching unit first."
                )
            if payload.capture_id:
                capture = conn.execute(
                    "SELECT kind FROM household_captures WHERE id=%s", [str(payload.capture_id)]
                ).fetchone()
                if capture is None or capture[0] != "shelf_tag":
                    raise HTTPException(422, "Use an uploaded shelf tag as price evidence.")
            metadata = {
                **payload.model_dump(mode="json"),
                "vendor_key": payload.store.lower(),
                "confirmed_by": identity.member_id or "local",
                "confirmed_at": datetime.now(UTC).isoformat(),
                "baseline_observation_id": actual[0]["id"],
                "baseline_unit_price": baseline.unit_price,
                "quote_kind": "confirmed_shelf_price",
                "package_measure": {"evidence_text": basis.evidence_text},
            }
            offer_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL, json.dumps(payload.model_dump(mode="json"), sort_keys=True)
                )
            )
            existing = conn.execute(
                "SELECT metadata->>'withdrawn_at' FROM household_product_price_observations WHERE id=%s",
                [offer_id],
            ).fetchone()
            if existing and existing[0]:
                raise HTTPException(
                    409,
                    "This exact offer was withdrawn. Recheck its date and conditions before recording it again.",
                )
            conn.execute(
                """INSERT INTO household_product_price_observations
                (id,product_id,observed_date,total_price,quantity,unit_price,package_display_label,
                 package_normalized_quantity,package_normalized_unit,source,metadata)
                VALUES (%s,%s,%s,%s,1,%s,%s,%s,%s,'vendor_quote',%s::jsonb)
                ON CONFLICT(id) DO NOTHING
            """,
                [
                    offer_id,
                    str(payload.product_id),
                    payload.observed_date,
                    net,
                    basis.unit_price,
                    basis.package_label,
                    basis.package_quantity,
                    basis.unit,
                    json.dumps(metadata),
                ],
            )
            if payload.costco_item_number and "costco" not in payload.store.lower():
                raise HTTPException(422, "Costco item numbers apply only to Costco offers.")
            # A substitute SKU stays on the quote, not the original product.
            if payload.capture_id:
                conn.execute("""UPDATE household_captures SET status='verified', reviewed_by=%s,
                    review_note=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
                    [identity.member_id, f"Price evidence confirmed for {payload.title}. {payload.conditions} No purchase inferred.", str(payload.capture_id)])
            conn.commit()
        return offer_id

    def withdraw_offer(self, identity: HouseholdIdentity, offer_id: str) -> None:
        require_adult(identity)
        with self.storage.connection() as conn:
            cursor = conn.execute(
                """UPDATE household_product_price_observations
                SET metadata=metadata || %s::jsonb WHERE id=%s AND source='vendor_quote'
                AND metadata->>'confirmed_by' IS NOT NULL""",
                [
                    json.dumps(
                        {
                            "availability_confirmed": False,
                            "withdrawn_by": identity.member_id or "local",
                            "withdrawn_at": datetime.now(UTC).isoformat(),
                        }
                    ),
                    offer_id,
                ],
            )
            if cursor.rowcount != 1:
                raise HTTPException(404, "Confirmed offer not found.")
            conn.commit()

    def ungroup(self, identity: HouseholdIdentity, product_id: str) -> None:
        require_adult(identity)
        with self.storage.connection() as conn:
            conn.execute(
                "UPDATE household_products SET metadata=metadata-'comparison_family' WHERE id=%s",
                [product_id],
            )
            conn.commit()

    def compare(self, payload: ShoppingComparison) -> ComparisonResult:
        entered = unit_price_basis(
            description="",
            metadata={},
            line_total=payload.total_price,
            packages=1,
            source="vendor_quote",
            quote_package_label=payload.package_label,
        )
        if entered is None:
            return ComparisonResult(
                status="needs_evidence",
                explanation="Confirm the total package contents, including multipacks.",
            )
        with self.storage.connection() as conn:
            if str(payload.product_id) not in {p.id for p in self.products(conn)}:
                raise HTTPException(404, "Choose an item in the current shopping pilot.")
            rows = conn.execute(
                """
                SELECT o.total_price,o.package_display_label,o.observed_date,o.metadata
                FROM household_product_price_observations o
                JOIN household_products p ON p.id=o.product_id
                JOIN household_products target ON target.id=%s
                WHERE o.source='vendor_quote' AND (
                    o.product_id=target.id OR (
                      p.metadata->'comparison_family'->>'id' IS NOT NULL
                      AND p.metadata->'comparison_family'->>'id'=target.metadata->'comparison_family'->>'id'))
                ORDER BY o.observed_date DESC,o.created_at DESC
            """,
                [str(payload.product_id)],
            ).fetchall()
        candidates = []
        seen = set()
        for total, label, observed, metadata in rows:
            meta = _coerce_metadata(metadata)
            key = (meta.get("vendor_key"), meta.get("title"), label)
            if key in seen:
                continue
            seen.add(key)
            if not offer_is_ready(meta, observed, today=shopping_today()):
                continue
            basis = unit_price_basis(
                description="",
                metadata={},
                line_total=total,
                packages=1,
                source="vendor_quote",
                quote_package_label=label or "",
            )
            if basis and basis.unit == entered.unit:
                candidates.append((basis, observed, meta))
        if not candidates:
            return ComparisonResult(
                status="needs_evidence",
                entered_unit_price=round(entered.unit_price, 4),
                unit=entered.unit_label,
                explanation="No comparable offer with confirmed stock, package and buying conditions in the last 14 days. Save the shelf tag for adult review.",
            )
        best, observed, meta = min(candidates, key=lambda row: row[0].unit_price)
        delta = round((entered.unit_price - best.unit_price) * entered.package_quantity, 2)
        return ComparisonResult(
            status="lower_recorded_offer" if delta > 0 else "no_lower_recorded_offer",
            explanation=(
                "A lower comparable offer is recorded. Check its conditions before making another trip."
                if delta > 0
                else "No lower offer among the confirmed prices. This does not establish a market-wide best price."
            ),
            entered_unit_price=round(entered.unit_price, 4),
            unit=entered.unit_label,
            alternative_store=meta.get("store") or meta.get("vendor_key"),
            alternative_package=best.package_label,
            alternative_price=best.package_price,
            alternative_date=str(observed),
            equivalent_difference=max(0, delta),
            conditions=str(meta.get("conditions") or "")
            + " · Valid through "
            + str(meta.get("valid_until") or "unknown"),
        )
