"""Unit tests for the pure ACA premium / PTC estimator.

Expected values are hand-computed from the verified constants: IRS Rev.
Proc. 2025-25 applicable percentages, 2025 ASPE poverty guidelines, and
the CMS federal default age curve.
"""

from __future__ import annotations

import pytest

from app.services._aca_estimator import (
    MEDICARE_DEFAULT_MONTHLY_PER_PERSON,
    ACAPerson,
    age_curve_factor,
    applicable_percentage,
    build_aca_year_plans,
    fpl_annual,
    household_premium_monthly,
    premium_tax_credit_annual,
)

# ----------------------------------------------------------------------
# applicable percentage / FPL
# ----------------------------------------------------------------------


def test_applicable_percentage_flat_below_133() -> None:
    assert applicable_percentage(0.5) == 0.0210
    assert applicable_percentage(1.32) == 0.0210


def test_applicable_percentage_interpolates_within_band() -> None:
    # Midpoint of the 133-150 band: 3.14% + half of (4.19 - 3.14).
    midpoint = (1.33 + 1.50) / 2.0
    assert applicable_percentage(midpoint) == pytest.approx(0.036_65)
    # Band edges are continuous: 150% reads 4.19 from either side.
    assert applicable_percentage(1.50) == pytest.approx(0.0419)
    assert applicable_percentage(1.75) == pytest.approx(0.053_95)


def test_applicable_percentage_flat_300_to_400_then_cliff() -> None:
    assert applicable_percentage(3.5) == 0.0996
    assert applicable_percentage(4.0) == 0.0996
    assert applicable_percentage(4.0001) is None


def test_fpl_annual_2025_guidelines() -> None:
    assert fpl_annual(1) == 15_650.0
    assert fpl_annual(2) == 21_150.0
    assert fpl_annual(4) == 32_150.0


# ----------------------------------------------------------------------
# age curve / family premium
# ----------------------------------------------------------------------


def test_age_curve_factor_anchors() -> None:
    assert age_curve_factor(10) == 0.765
    assert age_curve_factor(21) == 1.000
    assert age_curve_factor(40) == 1.278
    assert age_curve_factor(50) == 1.786
    assert age_curve_factor(60) == 2.714
    assert age_curve_factor(64) == 3.000
    assert age_curve_factor(80) == 3.000


def test_household_premium_sums_member_rates() -> None:
    # 49 + 44 + twin 14-year-olds: 1.706 + 1.397 + 0.765 + 0.765 = 4.633.
    assert household_premium_monthly(500.0, (49, 44, 14, 14)) == pytest.approx(2_316.5)


def test_household_premium_caps_children_at_three_oldest() -> None:
    # Five under-21 children: only the three oldest are charged.
    ages = (30, 10, 8, 6, 4, 2)
    expected = 500.0 * (1.135 + 0.765 * 3)
    assert household_premium_monthly(500.0, ages) == pytest.approx(expected)


# ----------------------------------------------------------------------
# premium tax credit
# ----------------------------------------------------------------------


def test_ptc_at_poverty_line_pays_2_1_percent() -> None:
    result = premium_tax_credit_annual(
        magi_annual=32_150.0, household_size=4, benchmark_annual=24_000.0
    )
    assert result.fpl_ratio == pytest.approx(1.0)
    assert result.expected_contribution == pytest.approx(675.15)
    assert result.credit == pytest.approx(23_324.85)
    assert not result.over_cliff


def test_ptc_floors_magi_at_poverty_line() -> None:
    # Below 100% FPL the household manages income up (FL non-expansion);
    # the credit matches the at-poverty-line case.
    low = premium_tax_credit_annual(
        magi_annual=5_000.0, household_size=4, benchmark_annual=24_000.0
    )
    assert low.magi_used == 32_150.0
    assert low.credit == pytest.approx(23_324.85)


def test_ptc_cliff_at_400_percent() -> None:
    at_cliff = premium_tax_credit_annual(
        magi_annual=128_600.0, household_size=4, benchmark_annual=24_000.0
    )
    assert at_cliff.credit == pytest.approx(24_000.0 - 0.0996 * 128_600.0)
    over = premium_tax_credit_annual(
        magi_annual=128_601.0, household_size=4, benchmark_annual=24_000.0
    )
    assert over.credit == 0.0
    assert over.over_cliff


def test_ptc_never_negative() -> None:
    result = premium_tax_credit_annual(
        magi_annual=128_600.0, household_size=4, benchmark_annual=5_000.0
    )
    assert result.credit == 0.0
    assert not result.over_cliff


# ----------------------------------------------------------------------
# year plans
# ----------------------------------------------------------------------

_FAMILY = (
    ACAPerson(birth_year=1977),
    ACAPerson(birth_year=1982),
    ACAPerson(birth_year=2012, covered_until_year=2034),
    ACAPerson(birth_year=2012, covered_until_year=2034),
)


def _plans(**overrides: object) -> tuple:
    args: dict[str, object] = {
        "persons": _FAMILY,
        "start_year": 2026,
        "horizon_years": 25,
        "retirement_year_index": 1,
        "chosen_age21_monthly": 500.0,
        "benchmark_age21_monthly": 500.0,
        "oop_monthly": 100.0,
        "medicare_monthly_per_person": 0.0,
        "real_inflation": 0.02,
        "plan_anchor_year": 2026,
        "planning_magi_fn": lambda _yi: 0.0,
    }
    args.update(overrides)
    return build_aca_year_plans(**args)


def test_year_plans_zero_before_retirement() -> None:
    plans = _plans()
    assert plans[0].gross_premium == 0.0
    assert plans[0].oop == 0.0
    assert plans[0].planning_net == 0.0


def test_year_plans_family_premium_and_planning_subsidy() -> None:
    # 2027: ages 50/45/15/15, household of 4, one year of +2% real growth.
    plan = _plans()[1]
    assert plan.covered_ages == (15, 15, 45, 50)
    assert plan.household_size == 4
    factors = 1.786 + 1.444 + 0.833 + 0.833
    assert plan.gross_premium == pytest.approx(500.0 * 1.02 * factors * 12.0)
    # Planning MAGI 0 floors to 100% FPL: net premium = 2.1% of FPL when
    # the chosen plan IS the benchmark.
    assert plan.planning_subsidy == pytest.approx(plan.benchmark_premium - 0.021 * 32_150.0)
    assert plan.oop == pytest.approx(100.0 * 12.0 * 1.02)
    assert plan.planning_net == pytest.approx(0.021 * 32_150.0 + plan.oop)


def test_year_plans_dependents_age_out_of_household() -> None:
    plans = _plans()
    by_year = {plan.calendar_year: plan for plan in plans}
    assert by_year[2033].household_size == 4
    assert by_year[2034].household_size == 2
    assert by_year[2034].covered_ages == (52, 57)


def test_year_plans_medicare_handoff_per_person() -> None:
    plans = _plans(horizon_years=25)
    by_year = {plan.calendar_year: plan for plan in plans}
    # 2042: primary (b. 1977) turns 65 — spouse remains solo on ACA.
    assert by_year[2042].covered_ages == (60,)
    assert by_year[2042].household_size == 2
    # 2047: spouse (b. 1982) turns 65 — premiums end, OOP continues.
    assert by_year[2047].gross_premium == 0.0
    assert by_year[2047].oop > 0.0
    assert by_year[2047].planning_net == pytest.approx(by_year[2047].oop)


def test_year_plans_cliff_planning_magi_pays_gross() -> None:
    plan = _plans(planning_magi_fn=lambda _yi: 250_000.0)[1]
    assert plan.planning_subsidy == 0.0
    assert plan.planning_net == pytest.approx(plan.gross_premium + plan.oop)


def test_year_plans_medicare_premium_per_person_from_65() -> None:
    plans = _plans(medicare_monthly_per_person=400.0)
    by_year = {plan.calendar_year: plan for plan in plans}
    # 2041: primary still 64 — no Medicare line yet.
    assert by_year[2041].medicare_premium == 0.0
    # 2042: primary (b. 1977) turns 65 — one person, +2% real growth
    # from the simulation start (today's-$ published rates).
    assert by_year[2042].medicare_premium == pytest.approx(400.0 * 12.0 * 1.02**16)
    # 2047: spouse (b. 1982) joins — two persons.
    assert by_year[2047].medicare_premium == pytest.approx(2 * 400.0 * 12.0 * 1.02**21)
    # Medicare stays out of planning_net (deterministic, no true-up).
    assert by_year[2047].planning_net == pytest.approx(by_year[2047].oop)


def test_year_plans_medicare_skips_dependents_and_working_years() -> None:
    # A dependent with an explicit coverage window leaves the household;
    # they never transition onto the modeled Medicare line.
    persons = (
        ACAPerson(birth_year=1977),
        ACAPerson(birth_year=1990, covered_until_year=2056),
    )
    plans = _plans(
        persons=persons, medicare_monthly_per_person=400.0, horizon_years=35
    )
    by_year = {plan.calendar_year: plan for plan in plans}
    # 2055: second person is 65 but window-bound — only the primary counts.
    assert by_year[2055].medicare_premium == pytest.approx(400.0 * 12.0 * 1.02**29)
    # Working years stay all-zero even at 65+.
    late_retiree = _plans(
        persons=(ACAPerson(birth_year=1977),),
        medicare_monthly_per_person=400.0,
        retirement_year_index=17,
        horizon_years=20,
    )
    assert late_retiree[16].medicare_premium == 0.0
    assert late_retiree[17].medicare_premium > 0.0


def test_medicare_default_sums_published_rates() -> None:
    # CMS Part B $202.90 + Part D BBP $38.99 + KFF Plan G average $164.
    assert pytest.approx(405.89) == MEDICARE_DEFAULT_MONTHLY_PER_PERSON
