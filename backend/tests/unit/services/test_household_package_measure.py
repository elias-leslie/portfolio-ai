"""Real descriptions must not turn model numbers or accessories into pack sizes."""

import pytest

from app.services._household_report_builder import _extract_package_measure


@pytest.mark.parametrize(
    ("title", "quantity", "unit"),
    [
        (
            "Nature Made Triple Omega 3-6-9 Softgels w. Fish, Flaxseed, Safflower & Olive Oils Value Size 150 Ct",
            150,
            "count",
        ),
        ("MoKo Case for Amazon Fire HD 10 Tablet - Kids Friendly", None, None),
        ("Olive Oil Dispenser Bottle, 16 oz", None, None),
        ("Pompeian Robust Extra Virgin Olive Oil 68 Fl Oz", 68, "volume_fl_oz"),
        ("Milk 2 x 32 fl oz", 64, "volume_fl_oz"),
        ("Milk 2-32 fl oz", None, None),
        ("Chocolate 12 oz (Pack of 3)", 36, "weight_oz"),
    ],
)
def test_package_description(title, quantity, unit):
    measure = _extract_package_measure(title, {})
    if quantity is None:
        assert measure is None
    else:
        assert (
            measure and measure.normalized_quantity == quantity and measure.normalized_unit == unit
        )
        assert measure.evidence_text and measure.parser_version == 2


def test_old_bad_cached_measure_does_not_override_the_label():
    metadata = {
        "product_enrichment": {
            "package_measure": {
                "normalized_quantity": 54,
                "normalized_unit": "count",
                "display_label": "6 x 9 softgels",
                "raw_quantity": 54,
                "raw_unit": "softgels",
            }
        }
    }
    result = _extract_package_measure("Triple Omega 3-6-9 Softgels, 150 Ct", metadata)
    assert result and result.normalized_quantity == 150


def test_cached_measure_requires_reproducible_evidence():
    metadata = {
        "product_enrichment": {
            "package_measure": {
                "normalized_quantity": 32,
                "normalized_unit": "weight_oz",
                "display_label": "32 oz",
                "raw_quantity": 32,
                "raw_unit": "oz",
                "parser_version": 2,
                "evidence_text": "32 oz",
            }
        }
    }
    result = _extract_package_measure("Honey reorder", metadata)
    assert result and result.normalized_quantity == 32
    metadata["product_enrichment"]["package_measure"]["normalized_quantity"] = 1
    assert _extract_package_measure("Honey reorder", metadata) is None


def test_price_basis_counts_every_package_without_relabeling_invoice_unit():
    from app.services.household_unit_prices import unit_price_basis

    basis = unit_price_basis(
        description="Olive oil 68 fl oz",
        metadata={},
        line_total=59.34,
        packages=2,
        source="order_history",
    )
    assert basis and basis.package_price == 29.67
    assert basis.unit_price == pytest.approx(29.67 / 68)
    assert basis.unit_label == "fl oz"
    assert (
        unit_price_basis(
            description="Olive oil 68 fl oz",
            metadata={},
            line_total=29.67,
            packages=None,
            source="receipt",
        )
        is None
    )
    assert (
        unit_price_basis(
            description="Fire HD 10 Tablet case",
            metadata={},
            line_total=12,
            packages=1,
            source="order_history",
        )
        is None
    )


def test_conflicting_sizes_need_confirmation_and_metric_rounding_uses_label_unit():
    assert _extract_package_measure("Olive oil 16 fl oz or 32 fl oz", {}) is None
    parsed = _extract_package_measure("Olive oil 101 fl oz (3 L)", {})
    assert parsed and parsed.normalized_quantity == 101
    metadata = {
        "product_enrichment": {
            "package_measure": {
                "normalized_quantity": 32,
                "normalized_unit": "weight_oz",
                "display_label": "32 oz",
                "raw_quantity": 32,
                "raw_unit": "oz",
                "parser_version": 2,
                "evidence_text": "32 oz",
            }
        }
    }
    parsed = _extract_package_measure("Honey 16 oz", metadata)
    assert parsed and parsed.normalized_quantity == 16


def test_realized_difference_requires_a_linked_receipt_not_an_unmatched_capture():
    from datetime import date

    from app.services.household_shopping_pilot import _purchase_comparison

    row = {'id':'later', 'source':'receipt', 'transaction_id':'linked', 'description':'Olive oil 68 fl oz',
           'metadata':{}, 'total':46, 'packages':2, 'date':date(2026,9,11)}
    offer = ('offer','product',23,'68 fl oz',date(2026,9,10),{'baseline_unit_price':29.67/68,'baseline_observation_id':'earlier'})
    result = _purchase_comparison(row,[offer])
    assert result and result['difference'] == 13.34 and result['paid'] == 46
    assert _purchase_comparison({**row,'transaction_id':None},[offer]) is None
    assert _purchase_comparison({**row,'source':'order_history'},[offer]) is None
