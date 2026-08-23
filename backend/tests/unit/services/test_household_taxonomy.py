"""One category, one essentiality, and no raw Plaid enums in the legend.

The Budget legend showed "Transportation" twice and "Household" twice because
series were keyed ``category + essentiality`` and nothing made a category keep
the same essentiality from one row to the next. Beside them sat "General
Services Storage" and "General Services Insurance", straight from Plaid.
"""

from __future__ import annotations

from app.services._household_taxonomy import (
    CATEGORY_ESSENTIALITY,
    canonical_classification,
    essentiality_for,
    normalize_category,
)


def test_every_curated_category_has_exactly_one_essentiality() -> None:
    for category in CATEGORY_ESSENTIALITY:
        assert essentiality_for(category) == CATEGORY_ESSENTIALITY[category]
        assert canonical_classification(category) == (
            category,
            CATEGORY_ESSENTIALITY[category],
        )


def test_the_doubled_series_collapse_to_one_reading_each() -> None:
    """The four categories that appeared twice in the live legend."""
    doubled = ["Transportation", "Household", "Travel", "Home"]

    assert [essentiality_for(name) for name in doubled] == [
        "essential",
        "mixed",
        "discretionary",
        "discretionary",
    ]


def test_plaid_labels_land_in_the_curated_set_instead_of_beside_it() -> None:
    assert normalize_category("General Services Insurance") == "Insurance"
    assert normalize_category("General Services Storage") == "Household"
    assert normalize_category("Bank Fees Other Bank Fees") == "Bills"
    assert normalize_category("GENERAL_SERVICES_WAREHOUSING") == "Household"
    assert normalize_category("LOAN_PAYMENTS_OTHER_PAYMENT") == "Debt Payments"


def test_a_category_the_household_invented_is_kept_as_written() -> None:
    """"Girls" is a real category in this household's data.

    Flattening a name the household chose into the fallback would be a worse
    lie than the doubled series this module exists to fix, so an unrecognised
    human label survives -- and gets one stable essentiality like everything else.
    """
    assert normalize_category("Weekend Projects") == "Weekend Projects"
    assert essentiality_for("Weekend Projects") == "mixed"
    assert essentiality_for("Weekend Projects") == essentiality_for("weekend projects")


def test_the_property_tax_is_a_bill_wherever_it_was_filed() -> None:
    """Home held a $2,144.48 property tax and a garden nursery.

    Those two rows were the category's only "essential" ones, and they are what
    dragged Home between needs and wants depending which row was read. The tax
    is a bill; Home is then honestly discretionary.
    """
    assert canonical_classification(
        "Home",
        merchant="Pinellas County Tax Collector",
        description="Pinellas County property tax (2025 bill)",
    ) == ("Bills", "essential")
    assert canonical_classification(
        "Home",
        merchant="Wilcox Nursery LLC",
        description="WILCOX NURSERY LLC",
    ) == ("Home", "discretionary")


def test_an_empty_or_missing_category_is_not_a_guess() -> None:
    assert canonical_classification(None) == ("Household", "mixed")
    assert canonical_classification("   ") == ("Household", "mixed")
