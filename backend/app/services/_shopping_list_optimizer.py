"""Pure shopping-list basket optimizer.

Given open list items, fresh vendor quotes, and user-configured vendor profiles,
compute per-vendor basket totals plus a split-basket recommendation only when
it clears the material savings threshold: max($8, 10%).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

SPLIT_MIN_SAVINGS_ABS = 8.0
SPLIT_MIN_SAVINGS_PCT = 0.10


def _money(value: float | int | None) -> float:
    return round(float(value or 0.0), 2)


def _quantity(item: dict[str, Any]) -> float:
    try:
        value = float(item.get("quantity") or 1.0)
    except (TypeError, ValueError):
        return 1.0
    return value if value > 0 else 1.0


def _quote_price(item: dict[str, Any], quote: dict[str, Any]) -> float:
    base = quote.get("unit_price") if quote.get("unit_price") is not None else quote.get("total_price")
    return _money(float(base or 0.0) * _quantity(item))


def _profile_fee(profile: dict[str, Any], subtotal: float, membership_required: bool = False) -> float:
    threshold = profile.get("free_delivery_threshold")
    if threshold is not None and subtotal >= float(threshold):
        delivery_fee = 0.0
    else:
        delivery_fee = float(profile.get("delivery_fee") or profile.get("pickup_fee") or 0.0)
    membership_fee = 0.0
    if membership_required and not bool(profile.get("membership_active")):
        membership_fee = float(profile.get("membership_monthly_fee") or 0.0)
    return _money(delivery_fee + membership_fee)


def _basket_total(profile: dict[str, Any], subtotal: float, membership_required: bool = False) -> dict[str, float]:
    fees = _profile_fee(profile, subtotal, membership_required=membership_required)
    return {"subtotal": _money(subtotal), "fees": fees, "total": _money(subtotal + fees)}


def optimize_shopping_list(
    items: list[dict[str, Any]],
    quotes: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return vendor baskets and a thresholded split recommendation."""
    open_items = [item for item in items if item.get("status", "open") == "open"]
    profiles_by_vendor = {
        str(profile["vendor_key"]): profile
        for profile in profiles
        if bool(profile.get("enabled", True))
    }
    quotes_by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stale_quote_products: set[str] = set()
    for quote in quotes:
        product_id = str(quote.get("product_id") or "")
        if not product_id:
            continue
        if quote.get("is_fresh") is False:
            stale_quote_products.add(product_id)
            continue
        vendor_key = str(quote.get("vendor_key") or "")
        if vendor_key in profiles_by_vendor:
            quotes_by_product[product_id].append(quote)

    matched_items = [item for item in open_items if item.get("product_id")]
    uncovered_items = [
        _item_label(item)
        for item in open_items
        if not item.get("product_id") or str(item.get("product_id")) not in quotes_by_product
    ]
    stale_quote_items = [
        _item_label(item)
        for item in matched_items
        if str(item.get("product_id")) in stale_quote_products
        and str(item.get("product_id")) not in quotes_by_product
    ]

    vendor_lines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in matched_items:
        for quote in quotes_by_product.get(str(item.get("product_id")), []):
            vendor_key = str(quote["vendor_key"])
            vendor_lines[vendor_key].append(
                {
                    "item_id": item.get("id"),
                    "name": _item_label(item),
                    "price": _quote_price(item, quote),
                    "membership_required": bool(quote.get("membership_required")),
                }
            )

    baskets = []
    for vendor_key, lines in vendor_lines.items():
        subtotal = sum(float(line["price"]) for line in lines)
        membership_required = any(bool(line.get("membership_required")) for line in lines)
        totals = _basket_total(
            profiles_by_vendor[vendor_key], subtotal, membership_required=membership_required
        )
        baskets.append(
            {
                "vendor_key": vendor_key,
                "display_name": profiles_by_vendor[vendor_key].get("display_name") or vendor_key,
                "item_count": len(lines),
                "uncovered_count": max(0, len(open_items) - len(lines)),
                "lines": lines,
                **totals,
            }
        )
    baskets.sort(key=lambda basket: (basket["uncovered_count"], basket["total"], basket["vendor_key"]))

    best_single = baskets[0] if baskets else None
    split = _split_recommendation(open_items, quotes_by_product, profiles_by_vendor, best_single)

    return {
        "item_count": len(open_items),
        "matched_item_count": len(matched_items),
        "uncovered_items": uncovered_items,
        "stale_quote_items": stale_quote_items,
        "vendor_baskets": baskets,
        "best_single_vendor": best_single,
        "split_recommendation": split,
    }


def _split_recommendation(
    open_items: list[dict[str, Any]],
    quotes_by_product: dict[str, list[dict[str, Any]]],
    profiles_by_vendor: dict[str, dict[str, Any]],
    best_single: dict[str, Any] | None,
) -> dict[str, Any]:
    assignments: list[dict[str, Any]] = []
    subtotals: dict[str, float] = defaultdict(float)
    membership_required_by_vendor: dict[str, bool] = defaultdict(bool)
    for item in open_items:
        product_id = str(item.get("product_id") or "")
        item_quotes = quotes_by_product.get(product_id, [])
        if not item_quotes:
            continue
        best_quote = min(item_quotes, key=lambda quote: _quote_price(item, quote))
        vendor_key = str(best_quote["vendor_key"])
        price = _quote_price(item, best_quote)
        subtotals[vendor_key] += price
        membership_required_by_vendor[vendor_key] = membership_required_by_vendor[vendor_key] or bool(
            best_quote.get("membership_required")
        )
        assignments.append(
            {
                "item_id": item.get("id"),
                "name": _item_label(item),
                "vendor_key": vendor_key,
                "price": price,
                "substitution_flag": (item.get("match_confidence") or 1.0) < 0.8,
            }
        )

    split_fees = 0.0
    for vendor_key, subtotal in subtotals.items():
        split_fees += _profile_fee(
            profiles_by_vendor[vendor_key],
            subtotal,
            membership_required=membership_required_by_vendor[vendor_key],
        )
    split_subtotal = _money(sum(subtotals.values()))
    split_total = _money(split_subtotal + split_fees)
    best_total = float(best_single.get("total") or 0.0) if best_single else 0.0
    savings = _money(best_total - split_total) if best_total else 0.0
    threshold = _money(max(SPLIT_MIN_SAVINGS_ABS, SPLIT_MIN_SAVINGS_PCT * best_total)) if best_total else 0.0

    return {
        "recommended": bool(assignments and best_single and savings >= threshold),
        "savings": savings,
        "threshold": threshold,
        "subtotal": split_subtotal,
        "fees": _money(split_fees),
        "total": split_total,
        "assignments": assignments,
    }


def _item_label(item: dict[str, Any]) -> str:
    return str(item.get("product_name") or item.get("free_text") or "Item")
