"""Unit tests for price-check finding thresholds (pure evaluate_candidates)."""

from __future__ import annotations

from typing import Any

from app.services.household_price_findings_service import (
    FindingCandidate,
    evaluate_candidates,
)


def _candidate(**overrides: object) -> FindingCandidate:
    base: dict[str, Any] = {
        "product_id": "p-1",
        "product_name": "GV Edamame",
        "purchase_count": 5,
        "household_price": 10.0,
        "vendor_key": "walmart",
        "vendor_price": 5.0,
        "vendor_url": "https://w.mt/x",
    }
    base.update(overrides)
    return FindingCandidate(**base)


def test_material_saving_yields_finding_with_payload() -> None:
    drafts = evaluate_candidates([_candidate()])
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.kind == "cheaper_elsewhere"
    assert draft.savings_estimate == 5.0
    assert draft.payload == {
        "product_name": "GV Edamame",
        "household_price": 10.0,
        "vendor_price": 5.0,
        "vendor_url": "https://w.mt/x",
        "vendor_title": None,
        "vendor_package_label": None,
        "vendor_promo_text": None,
    }


def test_savings_below_absolute_floor_are_noise() -> None:
    # $2.99 saved on a $10 item clears 15% but not the $3 floor.
    assert evaluate_candidates([_candidate(vendor_price=7.01)]) == []


def test_savings_below_percent_floor_are_noise() -> None:
    # $5 saved on a $40 item clears $3 but not 15% ($6).
    assert evaluate_candidates(
        [_candidate(household_price=40.0, vendor_price=35.0)]
    ) == []
    # $7 saved on the same item clears both.
    drafts = evaluate_candidates([_candidate(household_price=40.0, vendor_price=33.0)])
    assert len(drafts) == 1
    assert drafts[0].savings_estimate == 7.0


def test_single_purchase_products_never_alert() -> None:
    assert evaluate_candidates([_candidate(purchase_count=1)]) == []


def test_zero_household_price_is_skipped() -> None:
    assert evaluate_candidates([_candidate(household_price=0.0)]) == []


def test_rollup_threshold_boundary() -> None:
    under = evaluate_candidates(
        [
            _candidate(product_id="p-1", household_price=20.0, vendor_price=10.0),
            _candidate(product_id="p-2", household_price=20.0, vendor_price=6.01),
        ]
    )
    assert [d.kind for d in under] == ["cheaper_elsewhere", "cheaper_elsewhere"]

    over = evaluate_candidates(
        [
            _candidate(product_id="p-1", household_price=20.0, vendor_price=10.0),
            _candidate(product_id="p-2", household_price=20.0, vendor_price=5.0),
        ]
    )
    assert [d.kind for d in over] == [
        "cheaper_elsewhere",
        "cheaper_elsewhere",
        "savings_rollup",
    ]
    rollup = over[-1]
    assert rollup.savings_estimate == 25.0
    assert rollup.payload == {
        "finding_count": 2,
        "product_names": ["GV Edamame", "GV Edamame"],
    }
