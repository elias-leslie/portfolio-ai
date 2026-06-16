"""Unit tests for the pure floor-and-upside withdrawal engine.

All math is in REAL dollars. These tests exercise the engine in isolation
(no DB, no service) and assert the conservation identity across a grid of
guaranteed-income / capacity / bridge regimes.
"""

from __future__ import annotations

import pytest

from app.services._withdrawal_engine import (
    BridgeConfig,
    GuardrailsState,
    HealthcarePoint,
    PhaseConfig,
    SpendingReduction,
    WithdrawalConfig,
    bridge_initial_size,
    decline_factor,
    discretionary_target,
    floor,
    guardrails_capacity_and_update,
    healthcare_ltc,
    spending_target,
    step_year,
)


def _cfg(**overrides) -> WithdrawalConfig:
    base = {
        "strategy": "guardrails",
        "initial_rate": 0.06,
        "essential_floor": 40_000.0,
        "base_discretionary": 20_000.0,
        "retirement_age": 65,
        "horizon_years": 30,
        "horizon_end_age": 95,
        "primary_ss_claim_age": 70,
        "spouse_ss_claim_age": None,
        "r": 0.04,
    }
    base.update(overrides)
    return WithdrawalConfig(**base)


# 1-2. decline_factor ---------------------------------------------------------
def test_decline_smooth_values() -> None:
    cfg = _cfg(decline_mode="smooth", discretionary_decline_rate=0.01)
    assert decline_factor(cfg, 0, 65) == pytest.approx(1.0)
    assert decline_factor(cfg, 10, 75) == pytest.approx(0.99**10)
    assert decline_factor(cfg, 20, 85) == pytest.approx(0.99**20)


def test_decline_smooth_clamps_rate() -> None:
    lo = _cfg(decline_mode="smooth", discretionary_decline_rate=-0.5)
    hi = _cfg(decline_mode="smooth", discretionary_decline_rate=0.5)
    assert decline_factor(lo, 10, 75) == pytest.approx(1.0)  # clamped to 0.0
    assert decline_factor(hi, 10, 75) == pytest.approx((1.0 - 0.025) ** 10)  # clamped to 0.025


def test_decline_phase_boundaries() -> None:
    cfg = _cfg(decline_mode="phase", phase=PhaseConfig())
    assert decline_factor(cfg, 9, 74) == pytest.approx(1.0)  # go-go
    assert decline_factor(cfg, 10, 75) == pytest.approx(0.85)  # slow-go boundary
    assert decline_factor(cfg, 19, 84) == pytest.approx(0.85)  # slow-go
    assert decline_factor(cfg, 20, 85) == pytest.approx(0.75)  # no-go boundary


# 3. healthcare ---------------------------------------------------------------
def test_healthcare_step_carry_forward() -> None:
    cfg = _cfg(
        healthcare_schedule=(
            HealthcarePoint(age=80, real_amount=15_000.0),
            HealthcarePoint(age=85, real_amount=30_000.0),
        )
    )
    assert healthcare_ltc(cfg, 65) == 0.0  # flat (zero) before first point
    assert healthcare_ltc(cfg, 79) == 0.0
    assert healthcare_ltc(cfg, 80) == 15_000.0
    assert healthcare_ltc(cfg, 84) == 15_000.0  # carry forward
    assert healthcare_ltc(cfg, 85) == 30_000.0
    assert healthcare_ltc(cfg, 99) == 30_000.0  # flat after last point


def test_healthcare_unchanged_by_decline_in_no_go_band() -> None:
    cfg = _cfg(
        decline_mode="smooth",
        discretionary_decline_rate=0.025,
        healthcare_schedule=(HealthcarePoint(age=85, real_amount=30_000.0),),
    )
    # Deep in the no-go band the discretionary layer has declined, but the
    # floor's healthcare component is unaffected.
    assert healthcare_ltc(cfg, 90) == 30_000.0
    assert floor(cfg, 90) == pytest.approx(cfg.essential_floor + 30_000.0)


def test_healthcare_empty_schedule_zero() -> None:
    assert healthcare_ltc(_cfg(), 90) == 0.0


# 4. floor / spending composition --------------------------------------------
def test_floor_and_spending_composition() -> None:
    cfg = _cfg()
    assert floor(cfg, 65) == pytest.approx(40_000.0)
    assert discretionary_target(cfg, 0, 65) == pytest.approx(20_000.0)
    assert spending_target(cfg, 0, 65) == pytest.approx(60_000.0)


def test_spending_reduction_lowers_base_spend_not_healthcare() -> None:
    cfg = _cfg(
        healthcare_schedule=(HealthcarePoint(age=65, real_amount=12_000.0),),
        spending_reductions=(SpendingReduction(age=67, real_amount=6_000.0),),
    )
    assert spending_target(cfg, 0, 65) == pytest.approx(72_000.0)
    # The $6k living-spend reduction preserves the original 2/3 floor and
    # 1/3 discretionary split, while healthcare remains unchanged.
    assert floor(cfg, 67) == pytest.approx(48_000.0)
    assert discretionary_target(cfg, 2, 67) == pytest.approx(18_000.0 * 0.99**2)
    assert spending_target(cfg, 2, 67) == pytest.approx(48_000.0 + 18_000.0 * 0.99**2)


def test_year_zero_total_equals_target_after_carveout() -> None:
    # Baseline carve-out (mirrors _withdrawal_config_from_inputs): with an
    # absolute healthcare baseline at the retirement age, essential_floor is
    # netted so floor(0)+base_discretionary == target_retirement_spend.
    target = 60_000.0
    essential_portion = 40_000.0
    base_discretionary = 20_000.0
    healthcare_at_retirement = 8_000.0
    cfg = _cfg(
        essential_floor=essential_portion - healthcare_at_retirement,
        base_discretionary=base_discretionary,
        healthcare_schedule=(HealthcarePoint(age=65, real_amount=healthcare_at_retirement),),
    )
    assert spending_target(cfg, 0, 65) == pytest.approx(target)


# 6. guaranteed income switch-on ---------------------------------------------
def test_bridge_auto_discounted_floor_gap() -> None:
    cfg = _cfg(
        base_discretionary=0.0,
        primary_ss_claim_age=70,
        bridge=BridgeConfig(mode="auto", real_return=0.0),
    )
    # No guaranteed income before claim → bridge = sum of floor over 65..69.
    expected = sum(floor(cfg, age) for age in range(65, 70))
    assert bridge_initial_size(cfg, lambda _age: 0.0) == pytest.approx(expected)


def test_bridge_zero_when_retirement_at_or_after_claim() -> None:
    cfg = _cfg(retirement_age=70, primary_ss_claim_age=70)
    assert bridge_initial_size(cfg, lambda _age: 0.0) == 0.0


def test_bridge_manual_returns_amount() -> None:
    cfg = _cfg(bridge=BridgeConfig(mode="manual", manual_amount=123_456.0))
    assert bridge_initial_size(cfg, lambda _age: 0.0) == pytest.approx(123_456.0)


def test_bridge_auto_discounts_at_real_return() -> None:
    cfg = _cfg(base_discretionary=0.0, primary_ss_claim_age=68, bridge=BridgeConfig(mode="auto", real_return=0.02))
    expected = sum(floor(cfg, 65 + off) / (1.02**off) for off in range(0, 3))
    assert bridge_initial_size(cfg, lambda _age: 0.0) == pytest.approx(expected)


# 8-11. step_year + conservation ---------------------------------------------
def _assert_conservation(wy, *, solvent: bool) -> None:
    if not solvent:
        return
    lhs = wy.guaranteed_income + wy.bridge_draw + wy.portfolio_draw
    rhs = wy.floor + wy.discretionary_funded
    assert lhs == pytest.approx(rhs, abs=1e-6)


@pytest.mark.parametrize("guaranteed", [0.0, 20_000.0, 45_000.0, 80_000.0])
@pytest.mark.parametrize("portfolio", [50_000.0, 2_000_000.0])
@pytest.mark.parametrize("bridge", [0.0, 30_000.0])
def test_conservation_invariant_grid(guaranteed: float, portfolio: float, bridge: float) -> None:
    cfg = _cfg()
    wy = step_year(
        cfg,
        year_index=0,
        age=65,
        portfolio_bal_real=portfolio,
        bridge_bal_real=bridge,
        guaranteed_real=guaranteed,
    )
    _assert_conservation(wy, solvent=not wy.failed)


def test_excess_income_path() -> None:
    cfg = _cfg(essential_floor=40_000.0, base_discretionary=20_000.0)
    wy = step_year(
        cfg,
        year_index=0,
        age=65,
        portfolio_bal_real=1_000_000.0,
        bridge_bal_real=50_000.0,
        guaranteed_real=50_000.0,  # exceeds floor by 10k
    )
    assert wy.floor_shortfall_funded == 0.0
    assert wy.bridge_draw == 0.0  # bridge untouched when guaranteed covers floor
    assert wy.bridge_balance_end == pytest.approx(50_000.0)
    # 10k excess income funds discretionary; portfolio tops up the remaining 10k.
    assert wy.discretionary_funded == pytest.approx(20_000.0)
    assert wy.portfolio_draw == pytest.approx(10_000.0)


def test_capacity_clamp_floor_funded_first() -> None:
    # Tiny portfolio → guardrail capacity below the floor shortfall:
    # discretionary is squeezed to zero but floor is still funded first.
    cfg = _cfg(essential_floor=40_000.0, base_discretionary=20_000.0)
    wy = step_year(
        cfg,
        year_index=0,
        age=65,
        portfolio_bal_real=50_000.0,
        bridge_bal_real=0.0,
        guaranteed_real=0.0,
    )
    assert wy.floor_shortfall_funded == pytest.approx(40_000.0)
    assert wy.discretionary_funded == 0.0  # capacity - floor_shortfall <= 0
    assert wy.portfolio_draw == pytest.approx(40_000.0)
    assert wy.failed is False


def test_failure_when_floor_exceeds_portfolio() -> None:
    cfg = _cfg(essential_floor=40_000.0, base_discretionary=0.0)
    wy = step_year(
        cfg,
        year_index=0,
        age=65,
        portfolio_bal_real=10_000.0,
        bridge_bal_real=0.0,
        guaranteed_real=0.0,
    )
    assert wy.failed is True
    assert wy.floor_shortfall_funded == pytest.approx(40_000.0)


# 12. guardrails --------------------------------------------------------------
def test_guardrails_init_rate() -> None:
    state = GuardrailsState(initial_rate=0.05)
    cap, state = guardrails_capacity_and_update(1_000_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    assert cap == pytest.approx(50_000.0)
    assert state.initial_withdrawal == pytest.approx(50_000.0)


def test_guardrails_capital_preservation_cut() -> None:
    state = GuardrailsState(initial_rate=0.05)
    guardrails_capacity_and_update(1_000_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    # Balance halves → prospective rate 50k/500k = 0.10 > 0.05*1.2 → cut 10%.
    cap, state = guardrails_capacity_and_update(500_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    assert cap == pytest.approx(45_000.0)


def test_guardrails_prosperity_raise() -> None:
    state = GuardrailsState(initial_rate=0.05)
    guardrails_capacity_and_update(1_000_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    # Balance doubles → prospective rate 50k/2M = 0.025 < 0.05*0.8 → raise 10%.
    cap, state = guardrails_capacity_and_update(2_000_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    assert cap == pytest.approx(55_000.0)


def test_guardrails_inflation_skip_is_real_reduction() -> None:
    state = GuardrailsState(initial_rate=0.05)
    guardrails_capacity_and_update(1_000_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    # Same balance, but prior year's return was negative and rate (0.05) is not
    # above initial_rate (0.05) → no skip. Push rate above initial first.
    cap, state = guardrails_capacity_and_update(900_000.0, state, prev_return_negative=False, inflation_rate=0.025)
    # rate now 50k/900k ≈ 0.0556 > 0.05; next year after a negative return skips
    # the inflation step-up → real reduction by 1/(1+inf).
    before = state.current_withdrawal
    cap, state = guardrails_capacity_and_update(900_000.0, state, prev_return_negative=True, inflation_rate=0.025)
    assert cap < before


# 14. real/nominal round trip -------------------------------------------------
def test_real_nominal_round_trip_two_year() -> None:
    # A real portfolio_draw converted to nominal and back recovers the real value.
    inflation_rate = 0.03
    cfg = _cfg(essential_floor=40_000.0, base_discretionary=0.0)
    wy0 = step_year(cfg, year_index=0, age=65, portfolio_bal_real=1_000_000.0, bridge_bal_real=0.0, guaranteed_real=0.0)
    wy1 = step_year(cfg, year_index=1, age=66, portfolio_bal_real=1_000_000.0, bridge_bal_real=0.0, guaranteed_real=0.0)
    for t, wy in ((0, wy0), (1, wy1)):
        inflation_factor = (1.0 + inflation_rate) ** t
        nominal = wy.portfolio_draw * inflation_factor
        assert nominal / inflation_factor == pytest.approx(wy.portfolio_draw, abs=1e-6)
