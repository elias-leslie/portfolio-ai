from datetime import date

from app.services._household_spend_periods import (
    build_spend_period,
    comparator_months,
    is_month_key,
    month_label,
    months_between,
    resolve_spend_period,
)


def test_a_closed_month_runs_to_its_last_day():
    period = build_spend_period("2026-07", today=date(2026, 8, 23))

    assert period.label == "July 2026"
    assert period.start_date == date(2026, 7, 1)
    assert period.end_date == date(2026, 7, 31)
    assert period.is_month_to_date is False
    assert period.basis == "full_month"


def test_the_running_month_stops_at_today_and_says_so():
    period = build_spend_period("2026-08", today=date(2026, 8, 23))

    assert period.end_date == date(2026, 8, 23)
    assert period.month_end == date(2026, 8, 31)
    assert period.is_month_to_date is True
    assert period.days_elapsed == 23
    assert period.days_in_month == 31
    assert period.basis == "through_day_23"
    assert period.basis_label == "through day 23 of 31"


def test_february_knows_its_own_length():
    assert build_spend_period("2028-02", today=date(2028, 3, 1)).days_in_month == 29
    assert build_spend_period("2026-02", today=date(2026, 3, 1)).days_in_month == 28


def test_an_unknown_month_falls_back_to_the_current_one():
    period = resolve_spend_period(
        "not-a-month",
        available_months=["2026-06", "2026-07"],
        today=date(2026, 8, 23),
    )

    assert period.key == "2026-08"


def test_a_requested_month_wins_over_the_default():
    period = resolve_spend_period(
        "2026-05",
        available_months=["2026-06", "2026-07"],
        today=date(2026, 8, 23),
    )

    assert period.key == "2026-05"


def test_month_keys_are_validated_not_trusted():
    assert is_month_key("2026-07") is True
    assert is_month_key("2026-13") is False
    assert is_month_key("2026-7") is False
    assert is_month_key(None) is False


def test_a_month_with_no_rows_still_appears_in_the_selector():
    assert months_between("2026-05", "2026-08") == [
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
    ]


def test_months_span_a_year_boundary():
    assert months_between("2025-11", "2026-02") == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]


def test_comparators_are_the_prior_month_and_every_earlier_month():
    period = build_spend_period("2026-07", today=date(2026, 8, 23))

    prior, average_months = comparator_months(
        period,
        covered_months=["2026-04", "2026-05", "2026-06", "2026-07", "2026-08"],
    )

    assert prior == "2026-06"
    assert average_months == ["2026-04", "2026-05", "2026-06"]


def test_the_average_never_includes_the_month_being_reported():
    period = build_spend_period("2026-08", today=date(2026, 8, 23))

    prior, average_months = comparator_months(
        period, covered_months=["2026-06", "2026-07", "2026-08"]
    )

    assert prior == "2026-07"
    assert "2026-08" not in average_months


def test_a_missing_prior_month_reports_as_missing_rather_than_zero():
    period = build_spend_period("2026-01", today=date(2026, 8, 23))

    prior, _ = comparator_months(period, covered_months=["2026-01", "2026-02"])

    assert prior is None


def test_month_labels_read_the_way_a_person_says_them():
    assert month_label("2026-01") == "January 2026"
    assert month_label("2025-12") == "December 2025"
