"""Basket quotes use the same confirmed package evidence as the shopping pilot."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from app.services._household_price_location import shopping_today
from app.services.household_shopping_pilot import _actual_rows, _basis
from app.services.household_unit_prices import offer_is_ready, unit_price_basis


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def confirmed_list_quotes(conn: Any, items: list[Any]) -> list[dict[str, Any]]:
    ids = list({str(item.product_id) for item in items if item.product_id})
    if not ids:
        return []
    actual = _actual_rows(conn, ids)
    baselines = {}
    for row in actual:
        if row["product_id"] not in baselines:
            baselines[row["product_id"]] = _basis(row)
    rows = conn.execute("""SELECT id::text, product_id::text, total_price, package_display_label, observed_date, metadata
        FROM household_product_price_observations WHERE product_id=ANY(%s::uuid[]) AND source='vendor_quote'
        AND metadata->>'confirmed_by' IS NOT NULL ORDER BY observed_date DESC, created_at DESC""", [ids]).fetchall()
    quotes = []
    seen = set()
    for row in rows:
        oid, pid, total, label, observed, metadata = row
        if not isinstance(metadata, dict) or not offer_is_ready(metadata, observed, today=shopping_today()):
            continue
        baseline = baselines.get(pid)
        basis = unit_price_basis(description=str(metadata.get("title") or ""), metadata=metadata, line_total=total, packages=1, source="vendor_quote", quote_package_label=label or "")
        if baseline is None or basis is None or baseline.unit != basis.unit or not math.isclose(baseline.package_quantity, basis.package_quantity, rel_tol=.001):
            continue
        vendor = str(metadata.get("vendor_key") or "").lower()
        if not vendor or (pid, vendor) in seen:
            continue
        relevant = [item for item in items if str(item.product_id) == pid]
        if any(item.match_confidence is not None and item.match_confidence < .8 for item in relevant):
            continue
        # A basket quantity counts whole packages. Unknown measures and repeated
        # one-off coupons/fees cannot be extrapolated into a basket estimate.
        if any(item.unit and item.unit.lower() not in {"package", "packages", "pack", "packs", "item", "items"} for item in relevant):
            continue
        if any(item.quantity is not None and (item.quantity <= 0 or not float(item.quantity).is_integer()) for item in relevant):
            continue
        if sum(item.quantity or 1 for item in relevant) > 1 and (metadata.get("coupon") or metadata.get("fees")):
            continue
        seen.add((pid, vendor))
        quotes.append({"product_id": pid, "vendor_key": vendor, "total_price": basis.package_price, "comparison_price": basis.package_price,
                       "unit_price": basis.unit_price, "unit_label": basis.unit_label, "package_label": basis.package_label,
                       "is_fresh": True, "source": "confirmed_offer", "price_includes_fees": True, "membership_required": False,
                       "observation_id": oid, "evidence_fingerprint": fingerprint(list(row)), "valid_until": metadata.get("valid_until")})
    return quotes


def validate_saved_estimate(conn: Any, row: Any) -> Any:
    if row is None:
        return None
    result = row[3]
    if isinstance(result, str):
        result = json.loads(result or "null")
    valid = isinstance(result, dict) and result.get("evidence_version") == 2
    proofs = result.get("quote_evidence", {}) if valid else {}
    if valid and proofs:
        current = conn.execute("""SELECT id::text, product_id::text, total_price, package_display_label, observed_date, metadata
            FROM household_product_price_observations WHERE id=ANY(%s::uuid[]) AND source='vendor_quote'""", [list(proofs)]).fetchall()
        valid = len(current) == len(proofs) and all(
            fingerprint(list(quote)) == proofs.get(quote[0])
            and isinstance(quote[5], dict)
            and offer_is_ready(quote[5], quote[4], today=shopping_today()) for quote in current
        )
    return (*row[:3], result if valid else None, *row[4:])
