"""Unit tests for price-check orchestration helpers (pure parts)."""

from __future__ import annotations

from app.services._price_vendor_adapters import (
    VENDOR_ADAPTERS,
    VendorQuote,
    VendorResult,
)
from app.services.household_price_check_service import (
    _completion_status,
    _finding_candidates,
    _quote_unit_cost_for_product,
    _run_vendor_checks,
)

_AMAZON = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "amazon")
_WALMART = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "walmart")

_PRODUCTS = [
    {
        "id": "p-1",
        "name": "Edamame",
        "purchase_count": 4,
        "last_paid": 3.5,
        "baseline_package_label": "1 count",
        "baseline_package_quantity": 1,
        "baseline_package_unit": "count",
    },
    {
        "id": "p-2",
        "name": "Olive Oil",
        "purchase_count": 2,
        "last_paid": None,
        "baseline_package_label": "68 fl oz",
        "baseline_package_quantity": 68,
        "baseline_package_unit": "volume_fl_oz",
    },
    {
        "id": "p-3",
        "name": "Paper Towels",
        "purchase_count": 6,
        "last_paid": 21.99,
        "baseline_package_label": "1 count",
        "baseline_package_quantity": 1,
        "baseline_package_unit": "count",
    },
]


def _quote(
    product_id: str,
    price: float,
    *,
    package_label: str = "1 count",
    unit_price: float | None = None,
    confidence: float = 0.9,
) -> VendorQuote:
    return VendorQuote(
        product_id=product_id,
        title=f"{product_id} item",
        price=price,
        package_label=package_label,
        unit_price=unit_price if unit_price is not None else price,
        confidence=confidence,
    )


def test_vendor_failure_is_isolated_per_vendor() -> None:
    def check(adapter):
        if adapter.vendor_key == "walmart":
            raise RuntimeError("agent hub down")
        return VendorResult(adapter.vendor_key, "ok", [_quote("p-1", 2.0)])

    results = _run_vendor_checks([_AMAZON, _WALMART], check)
    assert results["amazon"].status == "ok"
    assert results["walmart"].status == "error"
    assert "agent hub down" in (results["walmart"].error or "")


def test_completion_status_surfaces_degraded_vendor_results() -> None:
    clean = {"amazon": VendorResult("amazon", "ok", [_quote("p-1", 2.0)])}
    blocked = {"amazon": VendorResult("amazon", "blocked")}
    partial = {"amazon": VendorResult("amazon", "partial", [_quote("p-1", 2.0)])}

    assert _completion_status(clean) == "completed"
    assert _completion_status(blocked) == "completed_with_errors"
    assert _completion_status(partial) == "completed_with_errors"


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
    assert by_product["p-1"].unit_label == "ct"
    assert by_product["p-1"].comparison_quantity == 1
    assert by_product["p-3"].vendor_key == "amazon"
    # p-2 has no household price baseline, so it can't become a finding.
    assert "p-2" not in by_product


def test_finding_candidates_ignore_quotes_for_unknown_products() -> None:
    results = {
        "amazon": VendorResult("amazon", "ok", [_quote("p-9", 1.0)]),
        "walmart": VendorResult("walmart", "blocked"),
    }
    assert _finding_candidates(_PRODUCTS, [_AMAZON, _WALMART], results) == []


def test_finding_candidates_compare_pompeian_by_fluid_ounce_not_bottle_price() -> None:
    products = [
        {
            "id": "oil",
            "name": "Pompeian Robust Extra Virgin Olive Oil",
            "purchase_count": 3,
            "last_paid": 29.67 / 101,
            "baseline_package_label": "101 fl oz",
            "baseline_package_quantity": 101,
            "baseline_package_unit": "volume_fl_oz",
        }
    ]
    results = {
        "amazon": VendorResult("amazon", "ok", []),
        "walmart": VendorResult(
            "walmart",
            "ok",
            [
                _quote(
                    "oil",
                    21.48,
                    package_label="68 fluid ounces",
                    unit_price=0.316,
                    confidence=0.72,
                )
            ],
        ),
    }

    assert _finding_candidates(products, [_AMAZON, _WALMART], results) == []


def test_finding_candidates_keep_actual_vendor_total_but_compare_unit_basis() -> None:
    products = [
        {
            "id": "oil",
            "name": "Pompeian Robust Extra Virgin Olive Oil",
            "purchase_count": 3,
            "last_paid": 29.67 / 101,
            "baseline_package_label": "101 fl oz",
            "baseline_package_quantity": 101,
            "baseline_package_unit": "volume_fl_oz",
        }
    ]
    results = {
        "amazon": VendorResult(
            "amazon",
            "ok",
            [
                _quote(
                    "oil",
                    26.38,
                    package_label="101 fl oz",
                    unit_price=0.26,
                    confidence=0.95,
                )
            ],
        )
    }

    candidates = _finding_candidates(products, [_AMAZON], results)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.household_price == 29.67 / 101
    assert candidate.vendor_price == 0.2612
    assert candidate.vendor_total_price == 26.38
    assert candidate.comparison_quantity == 101
    assert candidate.household_equivalent_total == 29.67
    assert candidate.vendor_equivalent_total == 26.38
    assert candidate.unit_label == "fl oz"


def test_quote_unit_cost_requires_compatible_unit_and_confidence() -> None:
    product = {
        "id": "nuts",
        "baseline_package_unit": "weight_oz",
        "baseline_package_quantity": 16,
    }

    assert (
        _quote_unit_cost_for_product(
            VendorQuote(
                product_id="nuts",
                title="Nuts 1 pound",
                price=9.99,
                package_label="1 pound",
                confidence=0.9,
            ),
            product,
        )
        == 0.6244
    )
    assert (
        _quote_unit_cost_for_product(
            _quote("nuts", 9.99, package_label="60 count", confidence=0.9),
            product,
        )
        is None
    )
    assert (
        _quote_unit_cost_for_product(
            _quote("nuts", 9.99, package_label="16 ounces", confidence=0.58),
            product,
        )
        is None
    )
