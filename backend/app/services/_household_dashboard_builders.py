"""Pure builder functions for household dashboard sections (no DB access)."""

from __future__ import annotations

import calendar
import statistics
from datetime import UTC, date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from app.models.household_finance import (
    HouseholdAffordability,
    HouseholdBudgetSnapshot,
    HouseholdIncomeAnchor,
    HouseholdIncomeAnchorMonth,
    HouseholdProfile,
    HouseholdRecurringCommitment,
    HouseholdReports,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
)
from app.services._household_recurrence import (
    BILL,
    CADENCE_DAYS,
    CADENCE_FOR_LABEL,
    LAPSED_AFTER_CYCLES,
    SUBSCRIPTION,
    RecurrencePattern,
    commitment_type_for,
)
from app.services._household_taxonomy import essentiality_for

_CADENCE_MULTIPLIERS: dict[str, int] = {
    "weekly": 52,
    "biweekly": 26,
    "monthly": 12,
    "bimonthly": 6,
    "quarterly": 4,
    "semiannual": 2,
    "annual": 1,
}

_CADENCE_OFFSETS: dict[str, timedelta | relativedelta] = {
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": relativedelta(months=1),
    "bimonthly": relativedelta(months=2),
    "quarterly": relativedelta(months=3),
    "semiannual": relativedelta(months=6),
    "annual": relativedelta(years=1),
}

# Annual belongs here even though nothing can infer it from two sightings a year
# apart: it is the cadence a household declares, and leaving it out meant a
# property tax or an HOA due once a year could never become a commitment at all,
# which is precisely the gap that under-funds the sinking fund by a twelfth of
# itself every month.
_RECURRING_CADENCES = set(_CADENCE_MULTIPLIERS)
_CADENCE_LABEL_MAP = CADENCE_FOR_LABEL
# Commitments that are obligations rather than habits. Only these count toward
# what is due soon or gets a sinking fund: a merchant the household merely
# visits on a rhythm owes nothing on a date.
_OBLIGATION_TYPES = {BILL, SUBSCRIPTION}

_CATEGORY_KEYWORDS: list[tuple[list[str], str]] = [
    (["spotify", "netflix", "prime"], "Subscriptions"),
    (["walmart", "publix", "whole foods"], "Groceries"),
    (["shell", "speedway"], "Gas"),
    (["insurance", "duke", "mortgage"], "Bills"),
]
def suggest_category(merchant: str, description: str) -> str:
    candidate = f"{merchant} {description}".lower()
    for keywords, category in _CATEGORY_KEYWORDS:
        if any(kw in candidate for kw in keywords):
            return category
    return "Household"


def suggest_essentiality(merchant: str, description: str) -> str:
    """The suggested category's own essentiality, never a second opinion.

    This used to hold its own three-category list and answer `essential` or
    `discretionary` -- never `mixed` -- which is how a Household purchase item
    came to be `discretionary` while every Household transaction was `mixed`,
    and how one category came to occupy two rows of the budget table. 1.6 made
    essentiality a function of the category; this is the last path that had not
    been told.
    """
    return essentiality_for(suggest_category(merchant, description))


def estimate_next_commitment_date(last_seen: date | datetime, cadence: str) -> str | None:
    offset = _CADENCE_OFFSETS.get(cadence)
    if offset is None:
        return None
    return (last_seen + offset).isoformat()


def _commitment_due_status(days_until_due: int | None) -> str:
    if days_until_due is None:
        return "unknown"
    if days_until_due < 0:
        return "overdue"
    if days_until_due <= 3:
        return "due_soon"
    return "upcoming"


def build_recurring_commitment(
    *,
    merchant: str,
    category: str,
    pattern: RecurrencePattern,
    today: date,
) -> HouseholdRecurringCommitment | None:
    """Turn a proven cadence into a commitment, or return None to skip."""
    if pattern.cadence not in _RECURRING_CADENCES:
        return None
    if (today - pattern.last_seen).days > LAPSED_AFTER_CYCLES * CADENCE_DAYS[pattern.cadence]:
        return None
    annualized_cost = pattern.typical_amount * _CADENCE_MULTIPLIERS[pattern.cadence]
    next_expected = estimate_next_commitment_date(pattern.last_seen, pattern.cadence)
    next_expected_date = (
        datetime.fromisoformat(next_expected).date() if next_expected is not None else None
    )
    days_until_due = (
        (next_expected_date - today).days
        if next_expected_date is not None
        else None
    )
    return HouseholdRecurringCommitment(
        merchant=merchant,
        category=category,
        cadence=pattern.label,
        average_amount=round(pattern.typical_amount, 2),
        annualized_cost=round(annualized_cost, 2),
        last_seen=pattern.last_seen.isoformat(),
        next_expected=next_expected,
        days_until_due=days_until_due,
        due_status=_commitment_due_status(days_until_due),
        due_confidence=pattern.confidence,
        commitment_type=commitment_type_for(category),
        evidence=pattern.evidence,
    )


def build_sinking_funds(
    *, recurring_commitments: list[HouseholdRecurringCommitment]
) -> list[HouseholdSinkingFund]:
    funds: list[HouseholdSinkingFund] = []
    for commitment in recurring_commitments:
        # A sinking fund smooths an obligation the household owes. A merchant it
        # simply visits often is not one, however large the yearly total looks.
        if commitment.commitment_type not in _OBLIGATION_TYPES:
            continue
        normalized_cadence = _CADENCE_LABEL_MAP.get(commitment.cadence, commitment.cadence)
        if normalized_cadence in {"weekly", "biweekly", "monthly"} and commitment.average_amount < 150:
            continue
        monthly_target = round(commitment.annualized_cost / 12, 2)
        funds.append(
            HouseholdSinkingFund(
                name=f"{commitment.merchant} buffer",
                monthly_target=monthly_target,
                annual_cost=round(commitment.annualized_cost, 2),
                rationale="Set aside a monthly buffer so periodic or lumpy household costs stop surprising the budget.",
            )
        )
    return funds[:4]


# Retirement spending phases, in the household's own recorded terms. Ages come
# from the profile; only the ordering is fixed here.
_GO_GO = "go_go"
_SLOW_GO = "slow_go"
_NO_GO = "no_go"

_SPEND_PHASE_LABELS = {
    _GO_GO: "Go-go years",
    _SLOW_GO: "Slow-go years",
    _NO_GO: "No-go years",
}


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _money_round(value: float) -> float:
    return round(value, 2)


def _spend_phase(
    age: int, *, slow_go_age: int | None, no_go_age: int | None
) -> tuple[str | None, int | None]:
    """Which retirement spending phase an age falls in, and years to the next."""
    if no_go_age is not None and age >= no_go_age:
        return _NO_GO, None
    if slow_go_age is not None and age >= slow_go_age:
        return _SLOW_GO, (no_go_age - age if no_go_age is not None else None)
    next_age = slow_go_age if slow_go_age is not None else no_go_age
    if next_age is None:
        return None, None
    return _GO_GO, next_age - age


def build_retirement_contribution_tracker(
    *,
    profile: HouseholdProfile,
    estimated_monthly_contributions: float,
    current_age: int | None = None,
    investable_assets: float = 0.0,
    retirement_activity_visible: bool = True,
    average_monthly_spend: float = 0.0,
) -> HouseholdRetirementContributionTracker:
    """Is the plan still on track, asked in the terms the current phase calls for.

    Contribution compliance is deliberately not the verdict. It reported a pass
    from a $0 target against $0 contributions, and it was measuring $300/mo
    against roughly $19,800/mo of asset growth -- a number that is not wrong so
    much as beside the point.
    """
    monthly_target = profile.monthly_savings_target
    target_age = profile.target_retirement_age
    target_monthly_spend = profile.target_retirement_spend
    withdrawal_rate = profile.withdrawal_initial_rate

    blind_spots: list[str] = []
    if not retirement_activity_visible:
        # $0 of visible contributions is not $0 contributed. No account in the
        # ledger is labelled as an IRA, 401(k), Roth or HSA, so the figure is
        # an absence of evidence and has to say so.
        blind_spots.append("no_retirement_account_activity")
    if withdrawal_rate is None or withdrawal_rate <= 0:
        blind_spots.append("withdrawal_rate_unset")
    if target_monthly_spend is None or target_monthly_spend <= 0:
        blind_spots.append("target_retirement_spend_unset")

    sustainable_monthly_spend: float | None = None
    if withdrawal_rate is not None and withdrawal_rate > 0:
        sustainable_monthly_spend = _money_round(
            investable_assets * withdrawal_rate / 12
        )

    asset_gap = 0.0
    if (
        withdrawal_rate is not None
        and withdrawal_rate > 0
        and target_monthly_spend is not None
        and target_monthly_spend > 0
    ):
        assets_required = target_monthly_spend * 12 / withdrawal_rate
        asset_gap = _money_round(max(assets_required - investable_assets, 0.0))

    plan_holds = (
        sustainable_monthly_spend is not None
        and target_monthly_spend is not None
        and target_monthly_spend > 0
        and sustainable_monthly_spend >= target_monthly_spend
    )

    common = {
        "monthly_target": monthly_target if (monthly_target or 0) > 0 else None,
        "estimated_monthly_contributions": estimated_monthly_contributions,
        "monthly_gap": 0.0,
        "current_age": current_age,
        "target_retirement_age": target_age,
        "investable_assets": _money_round(investable_assets),
        "withdrawal_rate": withdrawal_rate,
        "sustainable_monthly_spend": sustainable_monthly_spend,
        "target_monthly_spend": target_monthly_spend,
        "asset_gap": asset_gap,
        "blind_spots": blind_spots,
    }

    if current_age is None or target_age is None:
        return HouseholdRetirementContributionTracker(
            status="phase_unknown",
            phase="phase_unknown",
            phase_label="Phase not established",
            headline="The plan has no phase yet.",
            detail=(
                "A target retirement age and a birth year are what decide "
                "whether this block asks about saving or about withdrawing. "
                "Without both, it cannot ask either."
            ),
            **common,
        )

    years_to_target = target_age - current_age
    common["years_to_target"] = years_to_target

    if years_to_target > 0:
        return _accumulating_block(
            plan_holds=plan_holds,
            years_to_target=years_to_target,
            target_age=target_age,
            estimated_monthly_contributions=estimated_monthly_contributions,
            sustainable_monthly_spend=sustainable_monthly_spend,
            target_monthly_spend=target_monthly_spend,
            asset_gap=asset_gap,
            retirement_activity_visible=retirement_activity_visible,
            common=common,
        )

    return _drawdown_block(
        current_age=current_age,
        target_age=target_age,
        years_to_target=years_to_target,
        profile=profile,
        sustainable_monthly_spend=sustainable_monthly_spend,
        target_monthly_spend=target_monthly_spend,
        average_monthly_spend=average_monthly_spend,
        retirement_activity_visible=retirement_activity_visible,
        common=common,
    )


def _contribution_sentence(
    *, monthly: float, visible: bool
) -> str:
    if not visible:
        return (
            "Contributions are not judged here, and could not be anyway: no "
            "account in the ledger is labelled as a retirement account, so the "
            "$0 is an absence of evidence rather than a measurement."
        )
    if monthly > 0:
        return (
            f"{_money(monthly)}/mo is going in, noted rather than graded."
        )
    return "No contributions are visible, noted rather than graded."


def _accumulating_block(
    *,
    plan_holds: bool,
    years_to_target: int,
    target_age: int,
    estimated_monthly_contributions: float,
    sustainable_monthly_spend: float | None,
    target_monthly_spend: float | None,
    asset_gap: float,
    retirement_activity_visible: bool,
    common: dict[str, object],
) -> HouseholdRetirementContributionTracker:
    year_word = "year" if years_to_target == 1 else "years"
    contributions = _contribution_sentence(
        monthly=estimated_monthly_contributions,
        visible=retirement_activity_visible,
    )
    if plan_holds:
        return HouseholdRetirementContributionTracker(
            status="plan_holds",
            phase="accumulating_growth_carrying",
            phase_label=f"Accumulating - {years_to_target} {year_word} to {target_age}",
            headline=(
                "The plan holds at a 0% savings rate. Today's investable assets "
                f"already support {_money(sustainable_monthly_spend or 0)}/mo at "
                "your own withdrawal rule."
            ),
            detail=contributions,
            **common,
        )

    if sustainable_monthly_spend is None or target_monthly_spend is None:
        return HouseholdRetirementContributionTracker(
            status="unmeasurable",
            phase="accumulating_contributions_binding",
            phase_label=f"Accumulating - {years_to_target} {year_word} to {target_age}",
            headline="Whether the plan holds cannot be answered yet.",
            detail=(
                "A target retirement spend and a withdrawal rate are what turn "
                "assets into a monthly answer. " + contributions
            ),
            **common,
        )

    return HouseholdRetirementContributionTracker(
        status="short",
        phase="accumulating_contributions_binding",
        phase_label=f"Accumulating - {years_to_target} {year_word} to {target_age}",
        headline=(
            f"Today's assets support {_money(sustainable_monthly_spend)}/mo "
            f"against a {_money(target_monthly_spend)}/mo plan - a gap of "
            f"{_money(asset_gap)} in investable assets."
        ),
        detail=(
            f"That is the distance at today's balances, with {years_to_target} "
            f"{year_word} of growth still to come; the projection that closes "
            "it lives on the Retirement tab and stays the only one. "
            + contributions
        ),
        **common,
    )


def _drawdown_block(
    *,
    current_age: int,
    target_age: int,
    years_to_target: int,
    profile: HouseholdProfile,
    sustainable_monthly_spend: float | None,
    target_monthly_spend: float | None,
    average_monthly_spend: float,
    retirement_activity_visible: bool,
    common: dict[str, object],
) -> HouseholdRetirementContributionTracker:
    spend_phase, years_to_next = _spend_phase(
        current_age,
        slow_go_age=profile.phase_slow_go_age,
        no_go_age=profile.phase_no_go_age,
    )
    common["spend_phase"] = spend_phase
    common["years_to_next_spend_phase"] = years_to_next
    phase_label = _SPEND_PHASE_LABELS.get(spend_phase or "", "In retirement")
    if years_to_next is not None:
        year_word = "year" if years_to_next == 1 else "years"
        phase_label = f"{phase_label} - {years_to_next} {year_word} to the next"

    arrived = "this year" if years_to_target == 0 else f"{-years_to_target} years ago"
    if sustainable_monthly_spend is None:
        return HouseholdRetirementContributionTracker(
            status="unmeasurable",
            phase="drawing_down",
            phase_label=phase_label,
            headline=(
                f"The plan's retirement age of {target_age} arrived {arrived}, "
                "and there is no withdrawal rule to judge spending against."
            ),
            detail=(
                "Record a withdrawal rate and this block can say whether what "
                "the household spends is sustainable."
            ),
            **common,
        )

    # The reference figure is what the household actually spends, not the
    # target: a plan assuming $7,500/mo while $10,231/mo goes out is a
    # retirement fact that a budget screen is the one place to notice.
    comparison = average_monthly_spend if average_monthly_spend > 0 else 0.0
    if comparison > 0 and comparison > sustainable_monthly_spend:
        status = "short"
        headline = (
            f"Spending runs {_money(comparison)}/mo against the "
            f"{_money(sustainable_monthly_spend)}/mo today's assets support at "
            "your own withdrawal rule."
        )
    elif comparison > 0:
        status = "plan_holds"
        headline = (
            f"Spending runs {_money(comparison)}/mo, inside the "
            f"{_money(sustainable_monthly_spend)}/mo today's assets support."
        )
    else:
        status = "unmeasurable"
        headline = (
            "There is not enough spending history to say whether the withdrawal "
            "is sustainable."
        )

    detail_parts = [
        f"The plan's retirement age of {target_age} arrived {arrived}.",
    ]
    if not retirement_activity_visible:
        # Whether a drawdown has actually started is a different question from
        # whether one would be sustainable, and only the second is answerable
        # here. Saying so is the difference between a verdict and a guess.
        detail_parts.append(
            "No retirement-account activity is visible in the ledger, so "
            "whether a drawdown has started is not something this can see - "
            "only whether one would hold."
        )
    if target_monthly_spend is not None and comparison > 0:
        drift = comparison - target_monthly_spend
        if abs(drift) >= 1:
            direction = "above" if drift > 0 else "below"
            detail_parts.append(
                f"The plan assumes {_money(target_monthly_spend)}/mo; actual "
                f"spending is {_money(abs(drift))}/mo {direction} it."
            )
    return HouseholdRetirementContributionTracker(
        status=status,
        phase="drawing_down",
        phase_label=phase_label,
        headline=headline,
        detail=" ".join(detail_parts),
        **common,
    )


def _retirement_readiness(funded_years: float) -> str:
    if funded_years >= 25:
        return "strong"
    if funded_years >= 15:
        return "developing"
    return "short"


def build_retirement_scenarios(
    *,
    retirement_assets: float,
    target_retirement_spend: float | None,
    baseline_monthly_spend: float,
) -> list[HouseholdRetirementScenario]:
    base_monthly_spend = target_retirement_spend or baseline_monthly_spend or 0.0
    if base_monthly_spend <= 0:
        return []
    scenario_inputs = [
        ("Base plan", base_monthly_spend),
        ("Higher-spend stretch", round(base_monthly_spend * 1.15, 2)),
        ("Lean floor", round(base_monthly_spend * 0.85, 2)),
    ]
    return [
        HouseholdRetirementScenario(
            name=name,
            monthly_spend=round(monthly_spend, 2),
            annual_spend=round(monthly_spend * 12, 2),
            funded_years=round(retirement_assets / (monthly_spend * 12), 1) if monthly_spend > 0 else 0.0,
            readiness=_retirement_readiness(
                retirement_assets / (monthly_spend * 12) if monthly_spend > 0 else 0.0
            ),
            detail="A plain-language spend scenario using currently visible retirement assets.",
        )
        for name, monthly_spend in scenario_inputs
    ]


def _budget_pace(
    month_to_date_spend: float,
    month_to_date_plan: float,
) -> tuple[str, str]:
    pace_delta = month_to_date_spend - month_to_date_plan
    tolerance = max(month_to_date_plan * 0.05, 100)
    if abs(pace_delta) <= tolerance:
        return "on_track", "Month-to-date spend is tracking close to the plan."
    if pace_delta > 0:
        return "running_hot", (
            f"Month-to-date spend is ahead of plan by ${pace_delta:,.0f}. "
            "Review discretionary and recurring categories before the month hardens."
        )
    return "under_plan", (
        f"Month-to-date spend is ${abs(pace_delta):,.0f} below plan. "
        "The plan still has room for remaining bills and savings."
    )


def _budget_status(
    profile: HouseholdProfile,
    reports: HouseholdReports,
    *,
    plan_is_partial: bool,
    monthly_plan_total: float,
    missing_plan_components: list[str],
) -> tuple[str, str]:
    """Judge spending against the plan, or refuse to judge and say why.

    "On track" used to be the fall-through for every case the checks below did
    not catch, including the case where the targets simply were not set. That is
    how the same payload carried ``status: on_track`` next to
    ``actual_monthly_spend 10,085`` against ``monthly_plan_total 5,000``: two
    verdicts, one of them derived from nothing.
    """
    if (
        profile.monthly_essential_target is not None
        and reports.executive.average_monthly_essentials > profile.monthly_essential_target
    ):
        return "essentials_above_plan", "Essential spending is running above the current target and needs review."
    if (
        profile.monthly_discretionary_target is not None
        and reports.executive.average_monthly_discretionary > profile.monthly_discretionary_target
    ):
        return "discretionary_above_plan", "Discretionary spending is running above the current cap."
    if plan_is_partial:
        missing = _spoken_list(missing_plan_components)
        return "plan_incomplete", (
            f"No verdict yet: the monthly plan has no {missing} target, so total "
            f"spending of ${reports.executive.average_monthly_spend:,.0f}/mo cannot be "
            "judged against it."
        )
    if reports.executive.average_monthly_spend > monthly_plan_total:
        return "above_plan", (
            f"Spending averages ${reports.executive.average_monthly_spend:,.0f}/mo against a "
            f"${monthly_plan_total:,.0f}/mo plan, so the plan is not holding even though "
            "no single lane is over."
        )
    return "on_track", "The current monthly spending profile is inside the available budget guardrails."


def _spoken_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} or {items[-1]}"


# Three complete months: long enough that one payroll spike or one clawback
# cannot set the caps, short enough that a job change shows up in a quarter
# rather than a year (D16).
INCOME_ANCHOR_MONTHS = 3
# A declared anchor older than this is reported beside the measurement rather
# than instead of it -- "SummitFlow starts next month" is a fact for a while and
# then it is either true or it is not.
OVERRIDE_STALE_AFTER_DAYS = 120
# Or sooner, if what actually arrives has moved this far away from it -- but
# only once enough complete months have passed for the declared change to have
# shown up. A declaration made this month is *supposed* to disagree with the
# months before it; that is what declaring it was for.
OVERRIDE_DRIFT_TOLERANCE = 0.15
OVERRIDE_DRIFT_GRACE_DAYS = 60


def _month_label(month: str) -> str:
    """'2026-07' -> 'July 2026'. Returns the key unchanged if it is not one."""
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month


def _and_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _override_staleness(
    *,
    override: float,
    median: float | None,
    set_on: date | None,
    today: date,
) -> tuple[bool, str, int | None, float | None]:
    """Whether a declared anchor still deserves to outrank the measurement."""
    age_days = (today - set_on).days if set_on is not None else None
    drift = None if median is None else round(override - median, 2)

    if set_on is None:
        return (
            True,
            "This figure was declared without a date, so there is no way to "
            "tell whether it is current. Re-declare it to date it.",
            None,
            drift,
        )
    if age_days is not None and age_days > OVERRIDE_STALE_AFTER_DAYS:
        months = age_days // 30
        return (
            True,
            f"Declared {months} month{'s' if months != 1 else ''} ago, on "
            f"{set_on:%b %d, %Y}. Confirm it still holds or clear it.",
            age_days,
            drift,
        )
    if (
        median is not None
        and median > 0
        and drift is not None
        and age_days is not None
        and age_days >= OVERRIDE_DRIFT_GRACE_DAYS
        and abs(drift) / median > OVERRIDE_DRIFT_TOLERANCE
    ):
        direction = "above" if drift > 0 else "below"
        return (
            True,
            f"Declared on {set_on:%b %d, %Y} and still {_money(abs(drift))} "
            f"{direction} what has actually arrived over the last "
            f"{INCOME_ANCHOR_MONTHS} complete months ({_money(median)}).",
            age_days,
            drift,
        )
    return (False, "", age_days, drift)


def build_income_anchor(
    *,
    profile: HouseholdProfile,
    monthly_income: dict[str, float],
    today: date | None = None,
) -> HouseholdIncomeAnchor:
    """What a normal month brings in -- the number every cap is priced off.

    The median, not the mean, and only complete months: this ledger holds
    $15,244 in January against $3,205 in a part-finished August, and a mean of
    that pair would set a cap neither month could pay. The months behind the
    answer are returned with it, because a household that cannot check the
    arithmetic is being asked to trust it (D16).
    """
    today = today or date.today()
    current_month = f"{today:%Y-%m}"
    complete = sorted(
        (month, amount) for month, amount in monthly_income.items() if month < current_month
    )
    window = complete[-INCOME_ANCHOR_MONTHS:]

    median = round(statistics.median([amount for _, amount in window]), 2) if window else None
    months_used = [
        HouseholdIncomeAnchorMonth(
            month=month,
            label=_month_label(month),
            amount=_money_round(amount),
            # Only an odd window has a month that *is* the median; on an even
            # one the answer is between two months and belongs to neither.
            is_median=(
                median is not None
                and len(window) % 2 == 1
                and _money_round(amount) == median
            ),
        )
        for month, amount in window
    ]

    override = profile.income_anchor_override
    set_on = _parse_date(profile.income_anchor_override_set_on)
    note = (profile.income_anchor_override_note or "").strip() or None

    target = profile.monthly_net_income_target
    anchor = HouseholdIncomeAnchor(
        median_monthly_income=median,
        months_used=months_used,
        complete_months_available=len(complete),
        override_amount=override,
        override_set_on=set_on.isoformat() if set_on is not None else None,
        override_note=note,
        profile_target=target,
    )

    window_label = _and_list([month.label for month in months_used])
    amounts_label = ", ".join(_money(month.amount) for month in months_used)

    if override is not None:
        stale, stale_detail, age_days, drift = _override_staleness(
            override=override, median=median, set_on=set_on, today=today
        )
        anchor.status = "declared"
        anchor.source = "override"
        anchor.source_label = (
            f"Declared {set_on:%b %d, %Y}" if set_on is not None else "Declared"
        )
        anchor.monthly_income = _money_round(override)
        anchor.override_age_days = age_days
        anchor.override_drift = drift
        anchor.override_stale = stale
        anchor.override_stale_detail = stale_detail
        anchor.headline = f"{_money(override)}/mo, declared."
        if median is not None:
            anchor.detail = (
                f"{note + '. ' if note else ''}What has actually arrived over "
                f"{window_label}: {amounts_label}, a median of {_money(median)}."
            )
        else:
            anchor.detail = (
                f"{note + '. ' if note else ''}No complete month of income is on "
                "record to measure this against yet."
            )
    elif median is not None:
        anchor.status = "measured"
        anchor.source = "median"
        anchor.source_label = f"Median of {len(months_used)} complete months"
        anchor.monthly_income = median
        anchor.headline = f"{_money(median)}/mo is what a normal month brings in."
        anchor.detail = (
            f"Median of {window_label}: {amounts_label}. The median, not the "
            "average, so one large or missing deposit cannot set the caps."
        )
    else:
        anchor.status = "insufficient_history"
        anchor.source = "median"
        anchor.source_label = "Not measurable yet"
        anchor.headline = "Not enough history to say what a normal month brings in."
        anchor.detail = (
            "No complete calendar month of income is on record. "
            f"{_month_label(current_month)} is still running and is not counted."
        )

    if target is not None and anchor.monthly_income is not None:
        gap = round(target - anchor.monthly_income, 2)
        anchor.profile_target_gap = gap
        if abs(gap) < 1:
            anchor.profile_target_detail = (
                f"The saved take-home target of {_money(target)} matches the anchor."
            )
        else:
            direction = "above" if gap > 0 else "below"
            anchor.profile_target_detail = (
                f"The saved take-home target of {_money(target)} is "
                f"{_money(abs(gap))} {direction} the anchor. Caps built on the "
                "target would be spending money that does not arrive."
                if gap > 0
                else f"The saved take-home target of {_money(target)} is "
                f"{_money(abs(gap))} {direction} the anchor."
            )
    elif target is not None:
        anchor.profile_target_detail = (
            f"The saved take-home target is {_money(target)}, with nothing "
            "measured to compare it against."
        )

    return anchor


def _parse_date(value: str | None) -> date | None:
    """Accept a date, a datetime, or nothing -- the column stores a DATE."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _budget_analysis(
    *,
    has_plan: bool,
    plan_is_partial: bool,
    monthly_plan_total: float,
    missing_plan_components: list[str],
    month_to_date_spend: float,
    profile: HouseholdProfile,
    reports: HouseholdReports,
) -> tuple[float | None, str, str, str, str]:
    """Return (mtd_plan, pace_status, pace_detail, status, summary) for budget snapshot."""
    if not has_plan:
        return (
            None, "unknown",
            "Jenny needs a monthly plan before it can judge pacing.",
            "setup_needed",
            "Set the core monthly plan so Jenny can judge whether current spending is on pace.",
        )
    today = datetime.now(UTC).date()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    month_to_date_plan = round(monthly_plan_total * (today.day / days_in_month), 2)
    status, summary = _budget_status(
        profile,
        reports,
        plan_is_partial=plan_is_partial,
        monthly_plan_total=monthly_plan_total,
        missing_plan_components=missing_plan_components,
    )
    if plan_is_partial:
        # Total spend cannot be paced against a partial plan without reading as
        # structurally "hot"; surface the partial-plan state instead of a verdict.
        return (
            month_to_date_plan,
            "partial_plan",
            "The current plan only covers part of the month, so total spend is not paced against it yet. Set the remaining targets for a real pace.",
            status,
            summary,
        )
    pace_status, pace_detail = _budget_pace(month_to_date_spend, month_to_date_plan)
    return month_to_date_plan, pace_status, pace_detail, status, summary


# An affordability answer is worthless if it only looks as far as the end of the
# month: ask on the 30th and next week's bills are invisible. The horizon is the
# rest of the calendar month or the next fortnight, whichever reaches further,
# so the figure never counts fewer obligations than either frame alone.
MIN_AFFORDABILITY_HORIZON_DAYS = 14

# Under this much left, the answer is "tight" rather than a number to spend
# against. It sits in the service because two screens ask the same question and
# a threshold copied into a component is a second opinion waiting to happen.
TIGHT_FREE_TO_SPEND = 150.0


def build_affordability(
    *,
    cash_reserve: float,
    recurring_commitments: list[HouseholdRecurringCommitment],
    essentials_baseline: float,
    month_to_date_essential_spend: float | None,
    card_balances: float | None,
    committed_fund_balances: float | None,
    today: date,
) -> HouseholdAffordability:
    """Cash, minus everything already spoken for. No targets, no assumptions."""
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    horizon = max(month_end, today + timedelta(days=MIN_AFFORDABILITY_HORIZON_DAYS))
    horizon_days = (horizon - today).days

    bills_due = round(
        sum(
            commitment.average_amount
            for commitment in recurring_commitments
            if commitment.commitment_type in _OBLIGATION_TYPES
            and commitment.days_until_due is not None
            and commitment.days_until_due <= horizon_days
        ),
        2,
    )

    missing_inputs: list[str] = []
    remaining_essentials, essentials_basis = _remaining_essentials(
        baseline=essentials_baseline,
        spent_to_date=month_to_date_essential_spend,
        today=today,
        month_end=month_end,
    )
    if month_to_date_essential_spend is None:
        missing_inputs.append("essential_spend_to_date")
    if committed_fund_balances is None:
        missing_inputs.append("sinking_fund_balances")
    if card_balances is None:
        missing_inputs.append("card_balances")

    committed = committed_fund_balances or 0.0
    cards = card_balances or 0.0
    free_to_spend = round(
        cash_reserve - bills_due - remaining_essentials - committed - cards, 2
    )
    status, headline = _affordability_verdict(free_to_spend, horizon=horizon)
    return HouseholdAffordability(
        # Deliberately not floored at zero. A household that cannot cover what it
        # already owes needs to be told the size of the hole, not shown a $0 that
        # reads like "spend nothing more" when it means "you are already short".
        free_to_spend=free_to_spend,
        cash_on_hand=round(cash_reserve, 2),
        bills_due=bills_due,
        bills_due_through=horizon.isoformat(),
        remaining_essentials=remaining_essentials,
        essentials_basis=essentials_basis,
        committed_funds=round(committed, 2),
        card_balances=round(cards, 2),
        missing_inputs=missing_inputs,
        status=status,
        headline=headline,
        detail=(
            "Cash on hand, less bills due through "
            f"{_horizon_label(horizon)}, the rest of this month's essentials, "
            "and what is owed on cards."
        ),
    )


def _horizon_label(horizon: date) -> str:
    return f"{horizon:%b} {horizon.day}"


def _affordability_verdict(free_to_spend: float, *, horizon: date) -> tuple[str, str]:
    """How the free-to-spend figure should be read, in the household's terms.

    Three states and no fourth: a household is either short, nearly short, or
    working with an estimate. There is no *safe* -- the figure is arithmetic
    about days that have not happened, and a green badge over it was the most
    dangerous thing on the old Decision Board.
    """
    through = _horizon_label(horizon)
    if free_to_spend < 0:
        return (
            "hold",
            f"${abs(free_to_spend):,.0f} short of what is already owed "
            f"through {through}.",
        )
    if free_to_spend == 0:
        return (
            "hold",
            f"Nothing left once everything owed through {through} is covered.",
        )
    if free_to_spend < TIGHT_FREE_TO_SPEND:
        return (
            "tight",
            f"${free_to_spend:,.0f} left once everything owed through "
            f"{through} is covered.",
        )
    return (
        "estimate",
        f"${free_to_spend:,.0f} free to spend once everything owed through "
        f"{through} is covered.",
    )


def _remaining_essentials(
    *,
    baseline: float,
    spent_to_date: float | None,
    today: date,
    month_end: date,
) -> tuple[float, str]:
    """Essentials still to come this month, and the sentence explaining it.

    Two readings, and the larger wins. Usually the household is part-way through
    its essentials and the remainder is what is left of the baseline. But once
    the baseline is already spent, "nothing left to buy" is plainly false with a
    week of groceries and fuel still ahead, so the days that remain are charged
    at the baseline's own daily rate.
    """
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining = (month_end - today).days
    if spent_to_date is None:
        return round(max(baseline, 0.0), 2), (
            f"No essential spend recorded for {today:%B} yet, so the whole "
            f"{baseline:,.0f} baseline is still ahead."
        )
    left_of_baseline = baseline - spent_to_date
    pace_of_remaining_days = baseline * days_remaining / days_in_month
    remaining = round(max(left_of_baseline, pace_of_remaining_days, 0.0), 2)
    if left_of_baseline >= pace_of_remaining_days:
        detail = (
            f"{spent_to_date:,.0f} of the {baseline:,.0f} essentials baseline "
            f"is covered so far in {today:%B}."
        )
    else:
        detail = (
            f"{today:%B}'s {baseline:,.0f} essentials baseline is already spent "
            f"({spent_to_date:,.0f}); this is {days_remaining} more day"
            f"{'' if days_remaining == 1 else 's'} at the same rate."
        )
    return remaining, detail


def build_budget_snapshot(
    *,
    profile: HouseholdProfile,
    reports: HouseholdReports,
    month_to_date_spend: float,
    cash_reserve: float | None = None,
    recurring_commitments: list[HouseholdRecurringCommitment] | None = None,
    month_to_date_essential_spend: float | None = None,
    card_balances: float | None = None,
    committed_fund_balances: float | None = None,
    today: date | None = None,
) -> HouseholdBudgetSnapshot:
    plan_components = (
        ("essentials", profile.monthly_essential_target),
        ("discretionary", profile.monthly_discretionary_target),
        ("savings", profile.monthly_savings_target),
    )
    plan_values = tuple(value for _, value in plan_components)
    monthly_plan_total = sum(v for v in plan_values if v is not None)
    has_plan = any(v is not None for v in plan_values)
    missing_plan_components = [name for name, value in plan_components if value is None]
    plan_is_partial = has_plan and bool(missing_plan_components)
    remaining_cash_after_plan = (
        profile.monthly_net_income_target - monthly_plan_total
        if profile.monthly_net_income_target is not None and has_plan
        else None
    )
    discretionary_headroom = (
        profile.monthly_discretionary_target - reports.executive.average_monthly_discretionary
        if profile.monthly_discretionary_target is not None
        else None
    )
    month_to_date_plan, pace_status, pace_detail, status, summary = _budget_analysis(
        has_plan=has_plan,
        plan_is_partial=plan_is_partial,
        monthly_plan_total=monthly_plan_total,
        missing_plan_components=missing_plan_components,
        month_to_date_spend=month_to_date_spend,
        profile=profile,
        reports=reports,
    )
    operating_cushion = (
        profile.monthly_essential_target
        if profile.monthly_essential_target is not None
        else reports.executive.average_monthly_essentials
    )
    due_soon_bills_total: float | None = None
    safe_to_spend: float | None = None
    safe_to_spend_constraint: str | None = None
    affordability: HouseholdAffordability | None = None
    if cash_reserve is not None and recurring_commitments is not None:
        affordability = build_affordability(
            cash_reserve=cash_reserve,
            recurring_commitments=recurring_commitments,
            essentials_baseline=operating_cushion,
            month_to_date_essential_spend=month_to_date_essential_spend,
            card_balances=card_balances,
            committed_fund_balances=committed_fund_balances,
            today=today or date.today(),
        )
        due_soon_bills_total = affordability.bills_due
        safe_to_spend = affordability.free_to_spend
        safe_to_spend_constraint = "cash_after_commitments"
    return HouseholdBudgetSnapshot(
        status=status,
        summary=summary,
        monthly_income_target=profile.monthly_net_income_target,
        monthly_plan_total=monthly_plan_total if has_plan else None,
        monthly_plan_source="household_profile_targets" if has_plan else "none",
        monthly_plan_source_label=(
            "Household profile targets" if has_plan else "No monthly plan"
        ),
        essential_target=profile.monthly_essential_target,
        discretionary_target=profile.monthly_discretionary_target,
        savings_target=profile.monthly_savings_target,
        actual_monthly_spend=reports.executive.average_monthly_spend,
        actual_essential_monthly_spend=reports.executive.average_monthly_essentials,
        actual_discretionary_monthly_spend=reports.executive.average_monthly_discretionary,
        month_to_date_spend=month_to_date_spend,
        month_to_date_plan=month_to_date_plan,
        pace_status=pace_status,
        pace_detail=pace_detail,
        plan_is_partial=plan_is_partial,
        missing_plan_components=missing_plan_components,
        remaining_cash_after_plan=remaining_cash_after_plan,
        discretionary_headroom=discretionary_headroom,
        safe_to_spend=safe_to_spend,
        safe_to_spend_constraint=safe_to_spend_constraint,
        due_soon_bills_total=due_soon_bills_total,
        operating_cushion=round(operating_cushion, 2),
        affordability=affordability,
    )
