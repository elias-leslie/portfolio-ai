"""The retirement block asks the question its phase calls for, not the same one forever.

The block it replaces measured contribution compliance and reported ``on_track``
from a $0 target against $0 contributions, while assets grew at roughly 66x the
contribution being graded. D13's decision: the boundary is the household's own
``target_retirement_age`` against the primary adult's age, read live, and the
question changes on either side of it.
"""

from __future__ import annotations

from app.models.household_finance import HouseholdProfile
from app.services._household_dashboard_builders import (
    build_retirement_contribution_tracker,
)


def _profile(
    *,
    target_retirement_age: int | None = 49,
    target_retirement_spend: float | None = 7_500.0,
    withdrawal_initial_rate: float | None = 0.05,
    savings_target: float | None = 0.0,
) -> HouseholdProfile:
    return HouseholdProfile(
        id="profile-1",
        household_name="Household",
        monthly_savings_target=savings_target,
        target_retirement_age=target_retirement_age,
        target_retirement_spend=target_retirement_spend,
        withdrawal_initial_rate=withdrawal_initial_rate,
        phase_slow_go_age=75,
        phase_no_go_age=85,
        created_at="2026-08-24T00:00:00Z",
        updated_at="2026-08-24T00:00:00Z",
    )


def _block(**overrides):
    kwargs = {
        "profile": _profile(),
        "estimated_monthly_contributions": 0.0,
        "current_age": 40,
        "investable_assets": 1_542_870.67,
        "retirement_activity_visible": True,
        "average_monthly_spend": 10_230.57,
    }
    kwargs.update(overrides)
    return build_retirement_contribution_tracker(**kwargs)


def test_growth_carrying_the_plan_stops_grading_contributions() -> None:
    """"Do we even need to save more?" is the question, and the answer can be no."""
    # $2M at a 5% rule supports $8,333/mo against a $7,500/mo plan.
    block = _block(investable_assets=2_000_000.0)

    assert block.phase == "accumulating_growth_carrying"
    assert block.status == "plan_holds"
    assert block.sustainable_monthly_spend == 8333.33
    assert "holds at a 0% savings rate" in block.headline
    assert "noted rather than graded" in block.detail


def test_a_binding_gap_is_stated_as_assets_not_as_an_invented_contribution() -> None:
    """The distance is arithmetic; the projection that closes it is not ours.

    A required-contribution figure needs a return assumption, and a second
    return assumption is a second answer to a question the Retirement tab
    already answers.
    """
    block = _block(current_age=40, investable_assets=1_542_870.67)

    assert block.phase == "accumulating_contributions_binding"
    assert block.status == "short"
    # 7,500 * 12 / 0.05 = 1,800,000 required.
    assert block.asset_gap == 257_129.33
    assert "$257,129 in investable assets" in block.headline
    assert "Retirement tab" in block.detail
    assert "/mo more" not in block.headline


def test_reaching_the_target_age_moves_the_block_to_the_drawdown_question() -> None:
    block = _block(current_age=49)

    assert block.phase == "drawing_down"
    assert block.years_to_target == 0
    assert "arrived this year" in block.detail


def test_moving_the_target_age_moves_the_boundary_and_nothing_else() -> None:
    """"49 might change so that shouldn't be static." Changing it is the only lever."""
    earlier = _block(current_age=49, profile=_profile(target_retirement_age=49))
    later = _block(current_age=49, profile=_profile(target_retirement_age=60))

    assert earlier.phase == "drawing_down"
    assert later.phase == "accumulating_contributions_binding"
    assert later.years_to_target == 11
    # Same assets, same rule, same figure -- only the question changed.
    assert earlier.sustainable_monthly_spend == later.sustainable_monthly_spend


def test_drawdown_names_the_spending_phase_and_the_years_to_the_next_one() -> None:
    go_go = _block(current_age=49)
    slow_go = _block(current_age=78)
    no_go = _block(current_age=90)

    assert go_go.spend_phase == "go_go"
    assert go_go.years_to_next_spend_phase == 26
    assert go_go.phase_label == "Go-go years - 26 years to the next"
    assert slow_go.spend_phase == "slow_go"
    assert slow_go.years_to_next_spend_phase == 7
    assert no_go.spend_phase == "no_go"
    assert no_go.years_to_next_spend_phase is None


def test_drawdown_compares_what_is_spent_against_what_the_assets_support() -> None:
    block = _block(current_age=49)

    assert block.status == "short"
    assert "$10,231/mo" in block.headline
    assert "$6,429/mo" in block.headline
    # D13's two-way link: the plan assumes one number and the ledger shows
    # another, and the review screen is where that becomes visible.
    assert "$2,731/mo above it" in block.detail


def test_an_invisible_contribution_is_not_reported_as_a_zero_one() -> None:
    """$0 contributed and $0 visible are different facts."""
    invisible = _block(current_age=40, retirement_activity_visible=False)
    visible = _block(current_age=40, retirement_activity_visible=True)

    assert "no_retirement_account_activity" in invisible.blind_spots
    assert "absence of evidence" in invisible.detail
    assert "no_retirement_account_activity" not in visible.blind_spots
    assert "No contributions are visible" in visible.detail


def test_drawdown_will_not_claim_a_withdrawal_it_cannot_see() -> None:
    block = _block(current_age=49, retirement_activity_visible=False)

    assert "whether a drawdown has started is not something this can see" in (
        block.detail
    )


def test_without_a_withdrawal_rule_the_block_says_so_instead_of_guessing_one() -> None:
    block = _block(
        current_age=49,
        profile=_profile(withdrawal_initial_rate=None),
    )

    assert block.status == "unmeasurable"
    assert block.sustainable_monthly_spend is None
    assert "withdrawal_rate_unset" in block.blind_spots
    assert "Record a withdrawal rate" in block.detail


def test_a_savings_target_is_carried_but_is_no_longer_the_verdict() -> None:
    """The number survives for whoever wants it; the pass/fail on it does not."""
    block = _block(current_age=40, profile=_profile(savings_target=800.0))

    assert block.monthly_target == 800.0
    assert block.status in {"short", "plan_holds"}
    assert block.monthly_gap == 0.0
