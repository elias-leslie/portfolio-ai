from __future__ import annotations

import pytest

from app.services._household_report_builder import _extract_package_measure


@pytest.mark.parametrize(
    ("text", "quantity", "unit", "label"),
    [
        ("Pompeian Olive Oil 101 fluid ounces", 101.0, "volume_fl_oz", "101 fl oz"),
        ("Pompeian Olive Oil 68 fl oz", 68.0, "volume_fl_oz", "68 fl oz"),
        ("Almonds 24 ounces", 24.0, "weight_oz", "24 oz"),
        ("Rice 5 pounds", 80.0, "weight_oz", "5 lb"),
        ("Dish Detergent Tablets 92 count", 92.0, "count", "92 count"),
        ("Vitamin D3 240 softgels", 240.0, "count", "240 softgels"),
    ],
)
def test_package_measure_normalizes_unit_synonyms(
    text: str,
    quantity: float,
    unit: str,
    label: str,
) -> None:
    measure = _extract_package_measure(text, {"Product Name": text})

    assert measure is not None
    assert measure.normalized_quantity == quantity
    assert measure.normalized_unit == unit
    assert measure.display_label == label


@pytest.mark.parametrize(
    ("text", "quantity", "label"),
    [
        ("ZICO Coconut Water, 11.2 fl oz (Pack of 12)", 134.4, "12 x 11.2 fl oz"),
        ("12 pack of 11.2 fluid ounces coconut water", 134.4, "12 x 11.2 fl oz"),
    ],
)
def test_package_measure_multiplies_pack_of_fluid_ounces(
    text: str,
    quantity: float,
    label: str,
) -> None:
    measure = _extract_package_measure(text, {"Product Name": text})

    assert measure is not None
    assert measure.normalized_quantity == quantity
    assert measure.normalized_unit == "volume_fl_oz"
    assert measure.display_label == label
