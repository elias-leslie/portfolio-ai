"""Unit tests for price-check orchestration helpers (pure parts)."""

from __future__ import annotations

from app.services._price_vendor_adapters import (
    VENDOR_ADAPTERS,
    VendorQuote,
    VendorResult,
)
from app.services.household_price_check_service import (
    _finding_candidates,
    _run_vendor_checks,
)

_AMAZON = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "amazon")
_WALMART = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "walmart")

_PRODUCTS = [
    {"id": "p-1", "name": "Edamame", "purchase_count": 4, "last_paid": 3.5},
    {"id": "p-2", "name": "Olive Oil", "purchase_count": 2, "last_paid": None},
    {"id": "p-3", "name": "Paper Towels", "purchase_count": 6, "last_paid": 21.99},
]


def _quote(product_id: str, price: float) -> VendorQuote:
    return VendorQuote(product_id=product_id, title=f"{product_id} item", price=price)


def test_vendor_failure_is_isolated_per_vendor() -> None:
    def check(adapter):
        if adapter.vendor_key == "walmart":
            raise RuntimeError("agent hub down")
        return VendorResult(adapter.vendor_key, "ok", [_quote("p-1", 2.0)])

    results = _run_vendor_checks([_AMAZON, _WALMART], check)
    assert results["amazon"].status == "ok"
    assert results["walmart"].status == "error"
    assert "agent hub down" in (results["walmart"].error or "")


def test_finding_candidates_pick_cheapest_quote_across_vendors() -> None:
    results = {
        "amazon": VendorResult("amazon", "ok", [_quote("p-1", 3.0), _quote("p-3", 18.0)]),
        "walmart": VendorResult("walmart", "ok", [_quote("p-1", 2.5)]),
    }
    candidates = _finding_candidates(_PRODUCTS, [_AMAZON, _WALMART], results)
    by_product = {c.product_id: c for c in candidates}
    # p-1 takes Walmart's cheaper quote; p-3 only has Amazon's.
    assert by_product["p-1"].vendor_key == "walmart"
    assert by_product["p-1"].vendor_price == 2.5
    assert by_product["p-1"].household_price == 3.5
    assert by_product["p-3"].vendor_key == "amazon"
    # p-2 has no household price baseline, so it can't become a finding.
    assert "p-2" not in by_product


def test_finding_candidates_ignore_quotes_for_unknown_products() -> None:
    results = {
        "amazon": VendorResult("amazon", "ok", [_quote("p-9", 1.0)]),
        "walmart": VendorResult("walmart", "blocked"),
    }
    assert _finding_candidates(_PRODUCTS, [_AMAZON, _WALMART], results) == []
