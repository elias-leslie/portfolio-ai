"""Pure shopping-list basket optimizer.

Given open list items, fresh vendor quotes, and user-configured vendor profiles,
compute per-vendor basket totals plus a split-basket recommendation only when
it clears the material savings threshold: max($8, 10%).
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

SPLIT_MIN_SAVINGS_ABS = 8.0
SPLIT_MIN_SAVINGS_PCT = 0.10
DEFAULT_MAX_LOCAL_STORES = 2
DELIVERY_VENDOR_KEYS = {"amazon"}


def _money(value: float | int | None) -> float:
    return round(float(value or 0.0), 2)


def _quantity(item: dict[str, Any]) -> float:
    try:
        value = float(item.get("quantity") or 1.0)
    except (TypeError, ValueError):
        return 1.0
    return value if value > 0 else 1.0


def _quote_price(item: dict[str, Any], quote: dict[str, Any]) -> float:
    base = (
        quote.get("comparison_price")
        if quote.get("comparison_price") is not None
        else quote.get("total_price")
    )
    return _money(float(base or 0.0) * _quantity(item))


def _quote_sticker_price(item: dict[str, Any], quote: dict[str, Any]) -> float:
    return _money(float(quote.get("total_price") or 0.0) * _quantity(item))


def _quote_rank_price(quote: dict[str, Any]) -> float:
    base = (
        quote.get("unit_price")
        if quote.get("unit_price") is not None
        else quote.get("comparison_price")
        if quote.get("comparison_price") is not None
        else quote.get("total_price")
    )
    return float(base or 0.0)


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


def _basket_total(
    profile: dict[str, Any],
    subtotal: float,
    *,
    cart_subtotal: float | None = None,
    membership_required: bool = False,
) -> dict[str, float]:
    fee_basis = subtotal if cart_subtotal is None else cart_subtotal
    fees = _profile_fee(profile, fee_basis, membership_required=membership_required)
    cart = subtotal if cart_subtotal is None else cart_subtotal
    return {
        "subtotal": _money(subtotal),
        "fees": fees,
        "total": _money(subtotal + fees),
        "cart_subtotal": _money(cart),
        "cart_total": _money(cart + fees),
    }


def optimize_shopping_list(
    items: list[dict[str, Any]],
    quotes: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    *,
    max_local_stores: int | None = DEFAULT_MAX_LOCAL_STORES,
) -> dict[str, Any]:
    """Return vendor baskets and a thresholded split recommendation."""
    open_items = [item for item in items if item.get("status", "open") == "open"]
    max_local = _clamped_max_local_stores(max_local_stores)
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
                _assignment_line(item, quote, include_vendor=False)
            )

    baskets = []
    for vendor_key, lines in vendor_lines.items():
        subtotal = sum(float(line["price"]) for line in lines)
        cart_subtotal = sum(float(line.get("sticker_price") or line["price"]) for line in lines)
        membership_required = any(bool(line.get("membership_required")) for line in lines)
        totals = _basket_total(
            profiles_by_vendor[vendor_key],
            subtotal,
            cart_subtotal=cart_subtotal,
            membership_required=membership_required,
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
    split = _split_recommendation(
        open_items,
        quotes_by_product,
        profiles_by_vendor,
        best_single,
        max_local_stores=max_local,
    )

    return {
        "item_count": len(open_items),
        "matched_item_count": len(matched_items),
        "max_local_stores": max_local,
        "uncovered_items": uncovered_items,
        "stale_quote_items": stale_quote_items,
        "vendor_baskets": baskets,
        "best_single_vendor": best_single,
        "split_recommendation": split,
        "strategy_notes": [
            "Prices and savings use normalized unit basis when package quantity is known.",
            "Sticker price is retained per line so larger bulk packages do not hide cash outlay.",
        ],
    }


def _split_recommendation(
    open_items: list[dict[str, Any]],
    quotes_by_product: dict[str, list[dict[str, Any]]],
    profiles_by_vendor: dict[str, dict[str, Any]],
    best_single: dict[str, Any] | None,
    *,
    max_local_stores: int,
) -> dict[str, Any]:
    vendor_keys = sorted(
        {
            str(quote.get("vendor_key") or "")
            for quotes in quotes_by_product.values()
            for quote in quotes
            if quote.get("vendor_key")
        }
    )
    local_vendors = [
        vendor_key
        for vendor_key in vendor_keys
        if _is_local_vendor(vendor_key, profiles_by_vendor[vendor_key])
    ]
    delivery_vendors = [
        vendor_key
        for vendor_key in vendor_keys
        if not _is_local_vendor(vendor_key, profiles_by_vendor[vendor_key])
    ]
    candidates = [
        _split_candidate_for_vendors(
            open_items,
            quotes_by_product,
            profiles_by_vendor,
            allowed_vendors=set(local_combo) | set(delivery_vendors),
            max_local_stores=max_local_stores,
        )
        for size in range(0, min(max_local_stores, len(local_vendors)) + 1)
        for local_combo in combinations(local_vendors, size)
    ]
    candidates = [candidate for candidate in candidates if candidate["assignments"]]
    if not candidates:
        return _empty_split(max_local_stores=max_local_stores)
    candidate = min(
        candidates,
        key=lambda item: (
            item["uncovered_count"],
            item["total"],
            item["local_store_count"],
            item["delivery_vendor_count"],
        ),
    )
    best_total = float(best_single.get("total") or 0.0) if best_single else 0.0
    best_uncovered = int(best_single.get("uncovered_count") or 0) if best_single else len(open_items)
    savings = _money(best_total - float(candidate["total"])) if best_total else 0.0
    threshold = _money(max(SPLIT_MIN_SAVINGS_ABS, SPLIT_MIN_SAVINGS_PCT * best_total)) if best_total else 0.0
    candidate["savings"] = savings
    candidate["threshold"] = threshold
    candidate["recommended"] = bool(
        best_single
        and candidate["uncovered_count"] <= best_uncovered
        and savings >= threshold
    )
    return candidate


def _split_candidate_for_vendors(
    open_items: list[dict[str, Any]],
    quotes_by_product: dict[str, list[dict[str, Any]]],
    profiles_by_vendor: dict[str, dict[str, Any]],
    *,
    allowed_vendors: set[str],
    max_local_stores: int,
) -> dict[str, Any]:
    assignments: list[dict[str, Any]] = []
    subtotals: dict[str, float] = defaultdict(float)
    cart_subtotals: dict[str, float] = defaultdict(float)
    membership_required_by_vendor: dict[str, bool] = defaultdict(bool)
    for item in open_items:
        product_id = str(item.get("product_id") or "")
        item_quotes = [
            quote
            for quote in quotes_by_product.get(product_id, [])
            if str(quote.get("vendor_key") or "") in allowed_vendors
        ]
        if not item_quotes:
            continue
        best_quote = min(
            item_quotes,
            key=lambda quote: (
                _quote_rank_price(quote),
                _quote_price(item, quote),
                str(quote.get("vendor_key") or ""),
            ),
        )
        vendor_key = str(best_quote["vendor_key"])
        price = _quote_price(item, best_quote)
        subtotals[vendor_key] += price
        cart_subtotals[vendor_key] += _quote_sticker_price(item, best_quote)
        membership_required_by_vendor[vendor_key] = membership_required_by_vendor[vendor_key] or bool(
            best_quote.get("membership_required")
        )
        assignments.append(
            _assignment_line(item, best_quote, include_vendor=True)
        )

    split_fees = 0.0
    for vendor_key in subtotals:
        split_fees += _profile_fee(
            profiles_by_vendor[vendor_key],
            cart_subtotals[vendor_key],
            membership_required=membership_required_by_vendor[vendor_key],
        )
    split_subtotal = _money(sum(subtotals.values()))
    cart_subtotal = _money(sum(cart_subtotals.values()))
    split_total = _money(split_subtotal + split_fees)
    used_vendors = sorted(subtotals)
    local_store_count = sum(
        1
        for vendor_key in used_vendors
        if _is_local_vendor(vendor_key, profiles_by_vendor[vendor_key])
    )
    delivery_vendor_count = len(used_vendors) - local_store_count

    return {
        "recommended": False,
        "savings": 0.0,
        "threshold": 0.0,
        "subtotal": split_subtotal,
        "fees": _money(split_fees),
        "total": split_total,
        "cart_subtotal": cart_subtotal,
        "cart_total": _money(cart_subtotal + split_fees),
        "max_local_stores": max_local_stores,
        "local_store_count": local_store_count,
        "delivery_vendor_count": delivery_vendor_count,
        "vendors": used_vendors,
        "uncovered_count": max(0, len(open_items) - len(assignments)),
        "assignments": assignments,
    }


def _assignment_line(
    item: dict[str, Any],
    quote: dict[str, Any],
    *,
    include_vendor: bool,
) -> dict[str, Any]:
    line = {
        "item_id": item.get("id"),
        "name": _item_label(item),
        "price": _quote_price(item, quote),
        "sticker_price": _quote_sticker_price(item, quote),
        "unit_price": quote.get("unit_price"),
        "unit_label": quote.get("unit_label"),
        "package_label": quote.get("package_label"),
        "membership_required": bool(quote.get("membership_required")),
        "substitution_flag": (item.get("match_confidence") or 1.0) < 0.8,
    }
    if include_vendor:
        line["vendor_key"] = str(quote["vendor_key"])
    return line


def _empty_split(*, max_local_stores: int) -> dict[str, Any]:
    return {
        "recommended": False,
        "savings": 0.0,
        "threshold": 0.0,
        "subtotal": 0.0,
        "fees": 0.0,
        "total": 0.0,
        "cart_subtotal": 0.0,
        "cart_total": 0.0,
        "max_local_stores": max_local_stores,
        "local_store_count": 0,
        "delivery_vendor_count": 0,
        "vendors": [],
        "uncovered_count": 0,
        "assignments": [],
    }


def _is_local_vendor(vendor_key: str, profile: dict[str, Any]) -> bool:
    if "is_local_store" in profile:
        return bool(profile["is_local_store"])
    return vendor_key not in DELIVERY_VENDOR_KEYS


def _clamped_max_local_stores(value: int | None) -> int:
    if value is None:
        return DEFAULT_MAX_LOCAL_STORES
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_LOCAL_STORES
    return max(0, min(parsed, 5))


def _item_label(item: dict[str, Any]) -> str:
    return str(item.get("product_name") or item.get("free_text") or "Item")
