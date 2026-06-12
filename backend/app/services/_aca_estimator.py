"""ACA marketplace premium / premium-tax-credit estimator (pure decision math).

This module owns the healthcare expense stream for the retirement
projection (pre-Medicare ACA years). It is pure: no DB, no IO — premium
anchors come from ``aca_marketplace_plans`` via the caller. It mirrors
``_withdrawal_engine.py`` style: primitives + frozen dataclasses in,
dataclasses out. All amounts are **REAL** (today's) dollars unless noted.

Verified constants (never guessed):

* Applicable Percentage Table for 2026 — IRS Rev. Proc. 2025-25 §3.01
  (current law: enhanced ARPA credits expired end-2025, the 400% FPL
  cliff applies). https://www.irs.gov/pub/irs-drop/rp-25-25.pdf
* 2025 federal poverty guidelines, 48 contiguous states (govern the
  2026 coverage year) — ASPE detailed guidelines: $15,650 first person
  + $5,500 each additional. https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines
* Federal default age curve — CMS "State Specific Age Curve Variations"
  (Default Premium Ratio column). Florida uses it verbatim: the PUF
  premiums in ``aca_marketplace_plans`` reproduce these ratios exactly
  (40/21 = 1.278, 50/21 = 1.786, 60/21 = 2.714), so any age is rated as
  ``premium_age_21 x factor``.

Modeling assumptions (locked in the session-7 ACA interview):

* Subsidy law is **current law** — no PTC above 400% FPL (the cliff).
* MAGI below 100% FPL would forfeit the credit entirely in Florida
  (non-expansion, no Medicaid fallback for this household), so the
  estimator assumes income is *managed up* to 100% FPL — a small Roth
  conversion or gain harvest, essentially tax-free under the standard
  deduction — and floors MAGI at the poverty line.
* Healthcare costs grow at CPI + 2%/yr, i.e. +2%/yr in real terms.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

# 2025 poverty guidelines, 48 contiguous states (2026 coverage year).
FPL_FIRST_PERSON = 15_650.0
FPL_PER_ADDITIONAL_PERSON = 5_500.0

# Rev. Proc. 2025-25 §3.01: (upper bound of household income as a share
# of FPL, initial %, final %). Below 133% the percentage is flat; the
# statute interpolates linearly within each band; above 400% there is no
# credit at all (handled in ``applicable_percentage``).
APPLICABLE_PERCENTAGE_BANDS_2026: tuple[tuple[float, float, float], ...] = (
    (1.33, 0.0210, 0.0210),
    (1.50, 0.0314, 0.0419),
    (2.00, 0.0419, 0.0660),
    (2.50, 0.0660, 0.0844),
    (3.00, 0.0844, 0.0996),
    (4.00, 0.0996, 0.0996),
)

# CMS federal default standard age curve (premium ratio to age 21).
# 0-14 share one band (0.765); 64+ caps at 3.000.
_AGE_CURVE_15_TO_63 = {
    15: 0.833, 16: 0.859, 17: 0.885, 18: 0.913, 19: 0.941, 20: 0.970,
    21: 1.000, 22: 1.000, 23: 1.000, 24: 1.000, 25: 1.004, 26: 1.024,
    27: 1.048, 28: 1.087, 29: 1.119, 30: 1.135, 31: 1.159, 32: 1.183,
    33: 1.198, 34: 1.214, 35: 1.222, 36: 1.230, 37: 1.238, 38: 1.246,
    39: 1.262, 40: 1.278, 41: 1.302, 42: 1.325, 43: 1.357, 44: 1.397,
    45: 1.444, 46: 1.500, 47: 1.563, 48: 1.635, 49: 1.706, 50: 1.786,
    51: 1.865, 52: 1.952, 53: 2.040, 54: 2.135, 55: 2.230, 56: 2.333,
    57: 2.437, 58: 2.548, 59: 2.603, 60: 2.714, 61: 2.810, 62: 2.873,
    63: 2.952,
}

MEDICARE_AGE = 65


def age_curve_factor(age: int) -> float:
    """Federal default age-rating factor relative to the age-21 premium."""
    if age <= 14:
        return 0.765
    if age >= 64:
        return 3.000
    return _AGE_CURVE_15_TO_63[age]


def fpl_annual(household_size: int) -> float:
    """Poverty guideline for a tax household (48 contiguous states)."""
    return FPL_FIRST_PERSON + FPL_PER_ADDITIONAL_PERSON * (max(1, household_size) - 1)


def applicable_percentage(fpl_ratio: float) -> float | None:
    """Expected-contribution share of MAGI at ``fpl_ratio`` x FPL.

    ``None`` above 400% — the cliff: no credit at any income beyond it.
    Linear interpolation within each statutory band.
    """
    if fpl_ratio > 4.0:
        return None
    lower = 0.0
    for upper, pct_initial, pct_final in APPLICABLE_PERCENTAGE_BANDS_2026:
        if fpl_ratio <= upper:
            if pct_initial == pct_final or upper <= lower:
                return pct_initial
            span = (fpl_ratio - lower) / (upper - lower)
            return pct_initial + (pct_final - pct_initial) * span
        lower = upper
    return APPLICABLE_PERCENTAGE_BANDS_2026[-1][2]


def household_premium_monthly(age21_monthly: float, ages: Iterable[int]) -> float:
    """Family premium: sum of member rates off one age-21 anchor.

    ACA family rating charges every member 21+, but at most the three
    oldest children under 21.
    """
    members = list(ages)
    adults = [a for a in members if a >= 21]
    children = sorted((a for a in members if a < 21), reverse=True)[:3]
    return age21_monthly * sum(age_curve_factor(a) for a in (*adults, *children))


@dataclass(frozen=True, slots=True)
class PremiumTaxCredit:
    """One PTC evaluation, kept inspectable for the UI/endpoint."""

    magi_used: float
    fpl: float
    fpl_ratio: float
    applicable_pct: float | None
    expected_contribution: float
    credit: float
    over_cliff: bool


def premium_tax_credit_annual(
    *,
    magi_annual: float,
    household_size: int,
    benchmark_annual: float,
) -> PremiumTaxCredit:
    """Annual premium tax credit against the benchmark (SLCSP) premium.

    MAGI is floored at 100% FPL (managed-income assumption, see module
    docstring); above 400% FPL the credit is zero.
    """
    fpl = fpl_annual(household_size)
    magi_used = max(magi_annual, fpl)
    ratio = magi_used / fpl
    pct = applicable_percentage(ratio)
    if pct is None:
        return PremiumTaxCredit(
            magi_used=magi_used,
            fpl=fpl,
            fpl_ratio=ratio,
            applicable_pct=None,
            expected_contribution=0.0,
            credit=0.0,
            over_cliff=True,
        )
    expected = pct * magi_used
    return PremiumTaxCredit(
        magi_used=magi_used,
        fpl=fpl,
        fpl_ratio=ratio,
        applicable_pct=pct,
        expected_contribution=expected,
        credit=max(0.0, benchmark_annual - expected),
        over_cliff=False,
    )


@dataclass(frozen=True, slots=True)
class ACAPerson:
    """One household member for coverage/household-size purposes.

    ``covered_until_year`` is exclusive; ``None`` keeps the person
    covered (and in the tax household) until Medicare at 65. A person
    past their window leaves both the covered lives *and* the FPL
    household size (the dependent leaving the nest).
    """

    birth_year: int
    covered_until_year: int | None = None


@dataclass(frozen=True, slots=True)
class ACAYearPlan:
    """Deterministic (trial-independent) healthcare facts for one sim year.

    ``planning_*`` values price the subsidy off deterministic income
    only (guaranteed income sources; portfolio draws unknown here) —
    they seed the engine floor and bridge sizing. Per-trial truth comes
    from the tax-seam true-up against the trial's actual MAGI.
    """

    year_index: int
    calendar_year: int
    covered_ages: tuple[int, ...]
    household_size: int
    gross_premium: float
    benchmark_premium: float
    oop: float
    planning_magi: float
    planning_subsidy: float
    planning_net: float


def build_aca_year_plans(
    *,
    persons: tuple[ACAPerson, ...],
    start_year: int,
    horizon_years: int,
    retirement_year_index: int,
    chosen_age21_monthly: float,
    benchmark_age21_monthly: float,
    oop_monthly: float,
    real_inflation: float,
    plan_anchor_year: int,
    planning_magi_fn: Callable[[int], float],
) -> tuple[ACAYearPlan, ...]:
    """Dense per-year healthcare plan from retirement through the horizon.

    Working years are all-zero (employer coverage; pre-retirement
    spending never touches the portfolio). Premiums apply to covered
    members under 65; OOP runs through every retired year (Medicare
    premiums post-65 are a separate stream — retirement item E).
    """
    plans: list[ACAYearPlan] = []
    for year_index in range(horizon_years):
        calendar_year = start_year + year_index
        if year_index < retirement_year_index:
            plans.append(
                ACAYearPlan(
                    year_index=year_index,
                    calendar_year=calendar_year,
                    covered_ages=(),
                    household_size=0,
                    gross_premium=0.0,
                    benchmark_premium=0.0,
                    oop=0.0,
                    planning_magi=0.0,
                    planning_subsidy=0.0,
                    planning_net=0.0,
                )
            )
            continue
        in_window = [
            person
            for person in persons
            if person.covered_until_year is None or calendar_year < person.covered_until_year
        ]
        household_size = len(in_window)
        covered_ages = tuple(
            sorted(
                calendar_year - person.birth_year
                for person in in_window
                if 0 <= calendar_year - person.birth_year < MEDICARE_AGE
            )
        )
        # Premiums grow +2%/yr real from the PUF plan year; OOP (derived
        # from current spending) grows from the simulation start.
        premium_growth = (1.0 + real_inflation) ** (calendar_year - plan_anchor_year)
        oop_growth = (1.0 + real_inflation) ** year_index
        gross = (
            household_premium_monthly(chosen_age21_monthly * premium_growth, covered_ages) * 12.0
            if covered_ages
            else 0.0
        )
        benchmark = (
            household_premium_monthly(benchmark_age21_monthly * premium_growth, covered_ages) * 12.0
            if covered_ages
            else 0.0
        )
        oop = max(0.0, oop_monthly) * 12.0 * oop_growth
        planning_magi = max(0.0, planning_magi_fn(year_index))
        if covered_ages:
            planning_subsidy = premium_tax_credit_annual(
                magi_annual=planning_magi,
                household_size=household_size,
                benchmark_annual=benchmark,
            ).credit
        else:
            planning_subsidy = 0.0
        plans.append(
            ACAYearPlan(
                year_index=year_index,
                calendar_year=calendar_year,
                covered_ages=covered_ages,
                household_size=household_size,
                gross_premium=gross,
                benchmark_premium=benchmark,
                oop=oop,
                planning_magi=planning_magi,
                planning_subsidy=planning_subsidy,
                planning_net=max(0.0, gross - planning_subsidy) + oop,
            )
        )
    return tuple(plans)
