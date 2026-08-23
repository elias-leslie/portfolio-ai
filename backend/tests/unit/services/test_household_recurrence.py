"""What counts as a recurring commitment, using the household's own merchants.

Every series below is the real one the dashboard reads, which is the point: the
old detector needed two sightings and then ranked by size, so a fortnight in an
Airbnb outranked the electricity bill. These tests pin the five obligations that
have to appear and the four merchants that must not.
"""

from __future__ import annotations

from datetime import date

from app.services._household_recurrence import (
    BILL,
    RECURRING_PURCHASE,
    SUBSCRIPTION,
    commitment_type_for,
    detect_recurrence,
)

DUKE_ENERGY = [
    (date(2026, 1, 7), 152.90),
    (date(2026, 1, 7), 152.90),
    (date(2026, 2, 9), 202.11),
    (date(2026, 3, 9), 197.67),
    (date(2026, 4, 8), 142.25),
    (date(2026, 5, 11), 149.66),
    (date(2026, 6, 8), 170.43),
    (date(2026, 7, 8), 199.76),
    (date(2026, 8, 10), 230.76),
]
T_MOBILE = [
    (date(2026, 1, 15), 155.87),
    (date(2026, 2, 17), 148.15),
    (date(2026, 3, 16), 148.15),
    (date(2026, 4, 15), 161.61),
    (date(2026, 5, 15), 148.16),
    (date(2026, 6, 15), 148.16),
    (date(2026, 7, 15), 159.54),
    (date(2026, 8, 17), 155.00),
]
FRONTIER = [
    (date(2026, 1, 27), 34.99),
    (date(2026, 2, 27), 34.99),
    (date(2026, 3, 27), 34.99),
    (date(2026, 4, 28), 34.99),
    (date(2026, 5, 27), 34.99),
    (date(2026, 6, 29), 34.99),
    (date(2026, 7, 28), 34.99),
]
P_C_UTILITIES = [
    (date(2026, 2, 18), 209.10),
    (date(2026, 4, 20), 179.54),
    (date(2026, 6, 17), 265.94),
    (date(2026, 8, 17), 196.82),
]
WASTE_PRO = [
    (date(2025, 12, 29), 191.34),
    (date(2026, 3, 25), 194.59),
    (date(2026, 6, 24), 194.59),
]
AIRBNB = [
    (date(2026, 6, 16), 956.25),
    (date(2026, 6, 23), 636.60),
    (date(2026, 6, 30), 640.50),
]
AVIS = [(date(2026, 7, 5), 343.41)]
LUFTHANSA = [
    (date(2026, 6, 4), 1041.43),
    (date(2026, 7, 16), 90.00),
    (date(2026, 8, 2), 91.05),
]
COSTCO = [
    (date(2026, 6, 21), 65.00),
    (date(2026, 6, 24), 67.85),
    (date(2026, 7, 15), 856.99),
    (date(2026, 7, 17), 247.14),
    (date(2026, 7, 19), 59.58),
    (date(2026, 7, 23), 5831.50),
]


def test_the_five_utilities_the_household_actually_pays_are_all_detected() -> None:
    expected = {
        "Duke Energy": (DUKE_ENERGY, "monthly"),
        "T-Mobile": (T_MOBILE, "monthly"),
        "Frontier": (FRONTIER, "monthly"),
        "P C Utilities": (P_C_UTILITIES, "bimonthly"),
        "Waste Pro": (WASTE_PRO, "quarterly"),
    }
    detected = {
        name: detect_recurrence(events) for name, (events, _) in expected.items()
    }

    assert [name for name, pattern in detected.items() if pattern is None] == []
    assert {name: pattern.cadence for name, pattern in detected.items()} == {
        name: cadence for name, (_, cadence) in expected.items()
    }


def test_a_vacation_a_rental_car_and_a_warehouse_run_are_not_commitments() -> None:
    """The four merchants the old detector called bills.

    Each fails for its own reason and the reasons matter: the Airbnb kept a
    perfect weekly cadence but only for a fortnight, Avis was seen once,
    Lufthansa's charges ranged from $90 to $1,041, and Costco was neither
    regular nor stable.
    """
    assert detect_recurrence(AIRBNB) is None
    assert detect_recurrence(AVIS) is None
    assert detect_recurrence(LUFTHANSA) is None
    assert detect_recurrence(COSTCO) is None


def test_a_bill_paid_on_a_sixty_one_day_cycle_is_not_rounded_to_quarterly() -> None:
    """P C Utilities bills every two months, and the difference is money.

    Filing it as quarterly would set its sinking fund a third short of what the
    household actually owes each year.
    """
    pattern = detect_recurrence(P_C_UTILITIES)

    assert pattern is not None
    assert pattern.cadence == "bimonthly"
    assert pattern.median_interval_days == 61


def test_the_same_bill_imported_twice_on_one_day_is_counted_once() -> None:
    """Duke Energy has two rows dated 2026-01-07, both for $152.90.

    Summing them would report a $305 electricity bill the household never paid.
    """
    pattern = detect_recurrence(DUKE_ENERGY)

    assert pattern is not None
    assert pattern.sightings == 8
    assert pattern.typical_amount == 184.05


def test_one_off_cycle_charge_does_not_erase_a_year_of_evidence() -> None:
    """A gym billing $32.05 monthly plus one $54 day pass is still a gym."""
    gym = [
        (date(2026, 2, 22), 32.05),
        (date(2026, 3, 22), 32.05),
        (date(2026, 4, 23), 32.05),
        (date(2026, 5, 21), 32.05),
        (date(2026, 6, 21), 32.05),
        (date(2026, 7, 21), 32.05),
        (date(2026, 8, 2), 54.00),
        (date(2026, 8, 21), 32.05),
    ]

    pattern = detect_recurrence(gym)

    assert pattern is not None
    assert pattern.cadence == "monthly"
    assert pattern.typical_amount == 32.05


def test_a_weekly_rhythm_inside_a_single_month_is_not_a_cadence() -> None:
    """The Airbnb stay is the reference case, and it is regular and stable-ish.

    Only the observed span tells it apart from a genuine weekly commitment, so
    the span bar is what this asserts: stretch the same three charges across
    three months and it becomes a real pattern.
    """
    stretched = [
        (date(2026, 6, 16), 956.25),
        (date(2026, 7, 16), 936.60),
        (date(2026, 8, 16), 940.50),
    ]

    assert detect_recurrence(AIRBNB) is None
    assert detect_recurrence(stretched) is not None


def test_travel_and_retail_merchants_never_carry_the_bill_label() -> None:
    assert commitment_type_for("Bills") == BILL
    assert commitment_type_for("Healthcare") == BILL
    assert commitment_type_for("General Services Insurance") == BILL
    assert commitment_type_for("Subscriptions") == SUBSCRIPTION
    assert commitment_type_for("Fitness") == SUBSCRIPTION
    assert commitment_type_for("Travel") == RECURRING_PURCHASE
    assert commitment_type_for("Retail") == RECURRING_PURCHASE
    assert commitment_type_for("Groceries") == RECURRING_PURCHASE
    assert commitment_type_for(None) == RECURRING_PURCHASE


def test_a_detected_pattern_says_what_it_was_detected_from() -> None:
    pattern = detect_recurrence(FRONTIER)

    assert pattern is not None
    assert pattern.evidence == "7 charges across 7 months, about 30 days apart, typically 34.99."
