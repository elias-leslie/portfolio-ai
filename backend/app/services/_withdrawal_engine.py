"""Floor-and-upside retirement withdrawal engine (pure decision math).

This module owns the *spending plan* half of the retirement projection. It is
pure: no DB, no IO, no global state. It mirrors ``_retirement_simulation.py``
style — module-private helpers, ``@dataclass(slots=True)``, primitives + a
frozen config in, dataclasses out.

All amounts are **REAL** (today's) dollars. The caller (the tax seam in
``retirement_planning_service.py``) is responsible for growing balances,
subtracting the bridge draw, converting the residual portfolio draw to NOMINAL
(``* inflation_factor``), and handing it to the unchanged tax/RMD machinery.

Spending is split into a non-discretionary **floor** (essentials + an absolute
healthcare/LTC schedule) and a **discretionary** layer that declines with age
and is funded variably by either VPW (default) or Guyton-Klinger guardrails. A
non-volatile **bridge** sleeve (a scalar, not a bucket) funds the floor gap in
the pre-Social-Security years.

Funding identity (sources == uses), holds every solvent year:

    guaranteed_income + bridge_draw + portfolio_draw
        == floor + discretionary_funded

and additionally ``== spending_target`` in years where the discretionary layer
is not capacity-bound. (The plan's shorthand
``bridge_draw + floor_shortfall_funded + discretionary_funded == spending_target``
drops the guaranteed-income-applied-to-floor term; the form above is the exact
conservation law and is what the tests assert.)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

_EPS = 1e-6
# Discretionary decline is clamped to this band regardless of caller input so
# the pure function is self-protecting (the UI slider uses the same range).
_MAX_DECLINE_RATE = 0.025


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True, slots=True)
class PhaseConfig:
    """Go-go / slow-go / no-go spending bands for ``decline_mode="phase"``."""

    slow_go_age: int = 75
    no_go_age: int = 85
    go_go_pct: float = 1.0
    slow_go_pct: float = 0.85
    no_go_pct: float = 0.75


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    """Pre-Social-Security bridge sleeve sizing + (real) growth rate."""

    mode: Literal["auto", "manual"] = "auto"
    manual_amount: float | None = None
    real_return: float = 0.01


@dataclass(frozen=True, slots=True)
class HealthcarePoint:
    """One step in the absolute real healthcare/LTC schedule.

    ``real_amount`` is the absolute real annual healthcare spend that applies
    from ``age`` onward (carried forward until the next point). The baseline
    carve-out (see ``_withdrawal_config_from_inputs``) nets the value at the
    retirement age out of the essential floor so ``floor(0)`` equals the
    essential portion; later increases above that baseline produce the smile.
    """

    age: int
    real_amount: float


@dataclass(frozen=True, slots=True)
class WithdrawalConfig:
    """Frozen spending-plan configuration (real dollars unless noted).

    Carries enough self-contained context (ages, horizon, claim ages, expected
    real return) that the pure functions never need to reach back into the
    service or the ``RetirementInputs`` snapshot.
    """

    strategy: Literal["vpw", "guardrails"] = "vpw"
    initial_rate: float = 0.05
    decline_mode: Literal["smooth", "phase"] = "smooth"
    discretionary_decline_rate: float = 0.01
    phase: PhaseConfig = field(default_factory=PhaseConfig)
    bridge: BridgeConfig = field(default_factory=BridgeConfig)
    healthcare_schedule: tuple[HealthcarePoint, ...] = ()
    essential_floor: float = 0.0
    base_discretionary: float = 0.0
    # Self-contained context.
    retirement_age: int = 65
    horizon_years: int = 30
    horizon_end_age: int = 95
    primary_ss_claim_age: int = 67
    spouse_ss_claim_age: int | None = None
    r: float = 0.04

    @property
    def earliest_claim_age(self) -> int:
        ages = [self.primary_ss_claim_age]
        if self.spouse_ss_claim_age is not None:
            ages.append(self.spouse_ss_claim_age)
        return min(ages)


@dataclass(slots=True)
class GuardrailsState:
    """Mutable Guyton-Klinger state, threaded per trial / per schedule run.

    ``initial_rate`` is carried here (seeded from the config) because
    ``guardrails_capacity_and_update`` needs the threshold reference and its
    signature is intentionally config-free.
    """

    initial_rate: float = 0.05
    current_withdrawal: float = 0.0
    initial_withdrawal: float = 0.0
    prev_return_negative: bool = False


@dataclass(frozen=True, slots=True)
class WithdrawalYear:
    """Per-year decision output (real dollars)."""

    year_index: int
    age: int
    floor: float
    discretionary_target: float
    spending_target: float
    guaranteed_income: float
    bridge_draw: float
    floor_shortfall_funded: float
    discretionary_funded: float
    portfolio_draw: float
    bridge_balance_end: float
    failed: bool


def vpw_rate(n: int, r: float) -> float:
    """Variable-percentage-withdrawal rate for ``n`` remaining years at real ``r``.

    ``r/(1-(1+r)**-n)``; degenerates to ``1/n`` for ``|r| < 1e-9``. Guards
    ``n <= 0`` to ``n = 1``.
    """
    if n <= 0:
        n = 1
    if abs(r) < 1e-9:
        return 1.0 / n
    return r / (1.0 - (1.0 + r) ** (-n))


def decline_factor(cfg: WithdrawalConfig, t: int, age: int) -> float:
    """Discretionary decline multiplier at ``t`` years into retirement / ``age``.

    smooth: ``(1-rate)**t`` (rate clamped to ``[0, 0.025]``).
    phase: piecewise by band — ``age < slow_go_age`` → go-go, ``< no_go_age`` →
    slow-go, else no-go.
    """
    if cfg.decline_mode == "phase":
        phase = cfg.phase
        if age < phase.slow_go_age:
            return phase.go_go_pct
        if age < phase.no_go_age:
            return phase.slow_go_pct
        return phase.no_go_pct
    rate = _clamp(cfg.discretionary_decline_rate, 0.0, _MAX_DECLINE_RATE)
    return (1.0 - rate) ** max(0, t)


def healthcare_ltc(cfg: WithdrawalConfig, age: int) -> float:
    """Absolute real healthcare/LTC amount in effect at ``age``.

    Step / carry-forward: the most recent scheduled point with ``point.age <=
    age``. ``0.0`` before the first point and for an empty schedule. Never
    scaled by decline.
    """
    best_age: int | None = None
    best_amount = 0.0
    for point in cfg.healthcare_schedule:
        if point.age <= age and (best_age is None or point.age > best_age):
            best_age = point.age
            best_amount = point.real_amount
    return best_amount


def discretionary_target(cfg: WithdrawalConfig, t: int, age: int) -> float:
    return cfg.base_discretionary * decline_factor(cfg, t, age)


def floor(cfg: WithdrawalConfig, age: int) -> float:
    return cfg.essential_floor + healthcare_ltc(cfg, age)


def spending_target(cfg: WithdrawalConfig, t: int, age: int) -> float:
    return floor(cfg, age) + discretionary_target(cfg, t, age)


def bridge_initial_size(
    cfg: WithdrawalConfig,
    guaranteed_income_fn: Callable[[int], float],
) -> float:
    """Starting real size of the bridge sleeve.

    manual: the configured amount. auto: present value (at ``bridge.real_return``)
    of the floor gap ``max(0, floor(age) - guaranteed(age))`` across
    ``retirement_age .. earliest_claim_age - 1``; ``0`` when retirement starts at
    or after the earliest Social-Security claim.
    """
    if cfg.bridge.mode == "manual":
        return max(0.0, cfg.bridge.manual_amount or 0.0)
    earliest = cfg.earliest_claim_age
    if cfg.retirement_age >= earliest:
        return 0.0
    rr = cfg.bridge.real_return
    pv = 0.0
    for offset, age in enumerate(range(cfg.retirement_age, earliest)):
        gap = max(0.0, floor(cfg, age) - guaranteed_income_fn(age))
        pv += gap / ((1.0 + rr) ** offset)
    return pv


def vpw_capacity(portfolio_bal_real: float, age: int, cfg: WithdrawalConfig) -> float:
    """Portfolio draw the VPW schedule permits this year (real)."""
    n = max(1, cfg.horizon_end_age - age)
    return portfolio_bal_real * vpw_rate(n, cfg.r)


def guardrails_capacity_and_update(
    portfolio_bal_real: float,
    state: GuardrailsState,
    prev_return_negative: bool,
    inflation_rate: float,
) -> tuple[float, GuardrailsState]:
    """Guyton-Klinger guardrails capacity for this year + the updated state.

    Mutates and returns ``state`` (it is threaded per trial). Rules, evaluated
    in real space:

    * first call: ``current = initial = portfolio_bal * initial_rate``.
    * R4 inflation-skip: the year after a negative return, when already
      withdrawing above ``initial_rate``, skip the (real) inflation step-up,
      which in real terms is a reduction ``current *= 1/(1+inflation_rate)``.
    * capital preservation: cut 10% when ``prospective_rate > initial_rate * 1.20``.
    * prosperity: raise 10% when ``prospective_rate < initial_rate * 0.80``.
    """
    if state.initial_withdrawal <= 0.0:
        withdrawal = portfolio_bal_real * state.initial_rate
        state.current_withdrawal = withdrawal
        state.initial_withdrawal = withdrawal
        state.prev_return_negative = prev_return_negative
        return withdrawal, state

    withdrawal = state.current_withdrawal
    rate_before = withdrawal / portfolio_bal_real if portfolio_bal_real > 0 else float("inf")
    if prev_return_negative and rate_before > state.initial_rate:
        withdrawal = withdrawal / (1.0 + inflation_rate)

    prospective_rate = withdrawal / portfolio_bal_real if portfolio_bal_real > 0 else float("inf")
    if prospective_rate > state.initial_rate * 1.20:
        withdrawal *= 0.90
    elif prospective_rate < state.initial_rate * 0.80:
        withdrawal *= 1.10

    state.current_withdrawal = withdrawal
    state.prev_return_negative = prev_return_negative
    return withdrawal, state


def step_year(
    cfg: WithdrawalConfig,
    *,
    year_index: int,
    age: int,
    portfolio_bal_real: float,
    bridge_bal_real: float,
    guaranteed_real: float,
    strategy_state: GuardrailsState | None = None,
) -> WithdrawalYear:
    """Pure per-year spending decision (real dollars).

    Does NOT mutate balances or grow the portfolio — the caller applies growth,
    subtracts ``bridge_draw``, converts ``portfolio_draw`` to nominal, and feeds
    the tax seam. For guardrails the caller must update ``strategy_state`` via
    ``guardrails_capacity_and_update`` (it alone knows the realized return sign)
    before calling this; the resulting ``current_withdrawal`` is the capacity.
    """
    t = max(0, age - cfg.retirement_age)
    floor_amount = floor(cfg, age)
    disc_target = discretionary_target(cfg, t, age)
    spend_target = floor_amount + disc_target

    floor_gap = max(0.0, floor_amount - guaranteed_real)
    excess_income = max(0.0, guaranteed_real - floor_amount)
    bridge_draw = min(floor_gap, max(0.0, bridge_bal_real))
    floor_shortfall = floor_gap - bridge_draw

    if cfg.strategy == "guardrails":
        capacity = strategy_state.current_withdrawal if strategy_state is not None else 0.0
    else:
        capacity = vpw_capacity(portfolio_bal_real, age, cfg)

    disc_room = max(0.0, capacity - floor_shortfall)
    discretionary_from_portfolio = _clamp(disc_target - excess_income, 0.0, disc_room)
    discretionary_funded = excess_income + discretionary_from_portfolio
    portfolio_draw = floor_shortfall + discretionary_from_portfolio
    failed = floor_shortfall > portfolio_bal_real + _EPS

    return WithdrawalYear(
        year_index=year_index,
        age=age,
        floor=floor_amount,
        discretionary_target=disc_target,
        spending_target=spend_target,
        guaranteed_income=guaranteed_real,
        bridge_draw=bridge_draw,
        floor_shortfall_funded=floor_shortfall,
        discretionary_funded=discretionary_funded,
        portfolio_draw=portfolio_draw,
        bridge_balance_end=max(0.0, bridge_bal_real - bridge_draw),
        failed=failed,
    )
