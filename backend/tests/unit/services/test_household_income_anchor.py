"""The income anchor: what a normal month brings in, and who said so (D16)."""

from __future__ import annotations

from datetime import date

from app.models.household_finance import HouseholdProfile
from app.services._household_dashboard_builders import build_income_anchor

TODAY = date(2026, 8, 24)
# The household's real shape: two large months early in the year, a thin July,
# and an August that is still running.
LIVE_INCOME = {
    "2026-01": 15244.34,
    "2026-02": 13417.47,
    "2026-03": 7091.86,
    "2026-04": 5904.13,
    "2026-05": 6067.39,
    "2026-06": 7984.87,
    "2026-07": 2804.36,
    "2026-08": 3205.47,
}


def _profile(**kwargs: object) -> HouseholdProfile:
    return HouseholdProfile(
        id="profile-1",
        household_name="Household",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        **kwargs,
    )


def test_anchor_is_the_median_of_the_last_three_complete_months() -> None:
    anchor = build_income_anchor(profile=_profile(), monthly_income=LIVE_INCOME, today=TODAY)

    assert anchor.status == "measured"
    assert anchor.monthly_income == 6067.39
    assert [m.month for m in anchor.months_used] == ["2026-05", "2026-06", "2026-07"]


def test_the_running_month_is_never_counted() -> None:
    """August is a third finished. Counting it would report a third of a month."""
    anchor = build_income_anchor(profile=_profile(), monthly_income=LIVE_INCOME, today=TODAY)

    assert "2026-08" not in [month.month for month in anchor.months_used]
    assert anchor.complete_months_available == 7


def test_a_mean_would_have_answered_differently() -> None:
    """The point of D16: one big month must not set the caps.

    May/June/July mean to $5,619 and median to $6,067; over the whole record the
    mean is $7,750 -- a cap the household could not pay in four of eight months.
    """
    anchor = build_income_anchor(profile=_profile(), monthly_income=LIVE_INCOME, today=TODAY)
    window = [month.amount for month in anchor.months_used]

    assert anchor.monthly_income != round(sum(window) / len(window), 2)
    assert anchor.monthly_income == 6067.39


def test_the_median_month_is_named_so_the_arithmetic_can_be_checked() -> None:
    anchor = build_income_anchor(profile=_profile(), monthly_income=LIVE_INCOME, today=TODAY)

    assert [month.month for month in anchor.months_used if month.is_median] == ["2026-05"]
    assert "May 2026" in anchor.detail
    assert "$6,067" in anchor.detail


def test_an_even_window_claims_no_median_month() -> None:
    """Two months average to a number that belongs to neither of them."""
    anchor = build_income_anchor(
        profile=_profile(),
        monthly_income={"2026-06": 8000.0, "2026-07": 4000.0},
        today=TODAY,
    )

    assert anchor.monthly_income == 6000.0
    assert not any(month.is_median for month in anchor.months_used)


def test_no_complete_month_reports_no_anchor_rather_than_zero() -> None:
    anchor = build_income_anchor(
        profile=_profile(), monthly_income={"2026-08": 3205.47}, today=TODAY
    )

    assert anchor.status == "insufficient_history"
    assert anchor.monthly_income is None
    assert "August 2026 is still running" in anchor.detail


def test_a_declared_anchor_wins_but_the_measurement_stays_visible() -> None:
    anchor = build_income_anchor(
        profile=_profile(
            income_anchor_override=9000.0,
            income_anchor_override_set_on="2026-08-01",
            income_anchor_override_note="SummitFlow contract starts",
        ),
        monthly_income=LIVE_INCOME,
        today=TODAY,
    )

    assert anchor.status == "declared"
    assert anchor.monthly_income == 9000.0
    assert anchor.median_monthly_income == 6067.39
    assert "SummitFlow contract starts" in anchor.detail
    assert "$6,067" in anchor.detail


def test_a_fresh_declaration_is_not_stale_for_disagreeing_with_the_past() -> None:
    """Declaring a change is *supposed* to disagree with the months before it."""
    anchor = build_income_anchor(
        profile=_profile(
            income_anchor_override=9000.0,
            income_anchor_override_set_on="2026-08-01",
        ),
        monthly_income=LIVE_INCOME,
        today=TODAY,
    )

    assert not anchor.override_stale
    assert anchor.override_drift == 2932.61


def test_a_declaration_the_ledger_never_confirmed_is_called_out() -> None:
    anchor = build_income_anchor(
        profile=_profile(
            income_anchor_override=9000.0,
            income_anchor_override_set_on="2026-05-01",
        ),
        monthly_income=LIVE_INCOME,
        today=TODAY,
    )

    assert anchor.override_stale
    assert "still $2,933 above" in anchor.override_stale_detail


def test_an_old_declaration_is_stale_on_age_alone() -> None:
    anchor = build_income_anchor(
        profile=_profile(
            income_anchor_override=6100.0,
            income_anchor_override_set_on="2026-01-05",
        ),
        monthly_income=LIVE_INCOME,
        today=TODAY,
    )

    assert anchor.override_stale
    assert "7 months ago" in anchor.override_stale_detail
    assert anchor.override_age_days == 231


def test_an_undated_declaration_cannot_be_trusted_and_says_so() -> None:
    anchor = build_income_anchor(
        profile=_profile(income_anchor_override=9000.0),
        monthly_income=LIVE_INCOME,
        today=TODAY,
    )

    assert anchor.override_stale
    assert "declared without a date" in anchor.override_stale_detail
    assert anchor.override_age_days is None


def test_the_saved_take_home_target_is_compared_not_used() -> None:
    """D16's finding: the target sits above what arrives, so caps built on it overspend."""
    anchor = build_income_anchor(
        profile=_profile(monthly_net_income_target=6283.0),
        monthly_income=LIVE_INCOME,
        today=TODAY,
    )

    assert anchor.monthly_income == 6067.39
    assert anchor.profile_target_gap == 215.61
    assert "$216 above the anchor" in anchor.profile_target_detail


def test_a_target_with_nothing_to_measure_against_says_that_instead() -> None:
    anchor = build_income_anchor(
        profile=_profile(monthly_net_income_target=6283.0),
        monthly_income={},
        today=TODAY,
    )

    assert anchor.profile_target_gap is None
    assert "nothing measured to compare it against" in anchor.profile_target_detail
