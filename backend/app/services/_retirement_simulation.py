"""Monte Carlo retirement simulation engine (F5 internals).

Private helper to ``RetirementPlanningService`` — mirrors the
``_jenny_*`` convention. The engine is intentionally self-contained:
no DB, no app config, only numpy + the long-term return estimates
loaded from ``retirement_cma.yaml`` by the caller.

Behavior:

* Geometric-Brownian per asset class drift: ``r_t = mu_i + sigma_i * z_t``
  where ``z_t`` is a correlated standard-normal sample.
* Inflation-indexed expense path: `expenses_t = annual_expenses * (1+inf)^t`.
* Income sources start at their ``start_age`` (relative to the primary
  member). ``inflation_adjusted`` rows escalate; flat rows do not.
* Withdrawal rule: cover the year's net spend (expenses minus active
  income); short year = depletion. Track the year of first depletion
  to derive ``failure_year_distribution`` and the
  ``sequence_of_returns_risk`` metric (failure prob in years 0-5 vs
  later).
* Output: success probability, median ending balance, percentile
  ending-balance bands (10/25/50/75/90), and yearly percentile paths.

The deterministic seed pathway is the contract: same seed + same
inputs ⇒ same numbers. Tests assert ±1% stability at 10k trials.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

PERCENTILE_KEYS: tuple[tuple[str, float], ...] = (
    ("p10", 10.0),
    ("p25", 25.0),
    ("p50", 50.0),
    ("p75", 75.0),
    ("p90", 90.0),
)
SEQUENCE_OF_RETURNS_HORIZON = 5


@dataclass(slots=True)
class _IncomeStreamPlan:
    start_year: int
    monthly_amount: float
    inflation_adjusted: bool


@dataclass(slots=True)
class SimulationOutputs:
    success_probability: float
    median_ending_balance: float
    sequence_of_returns_risk: float
    percentiles: dict[str, float]
    failure_year_distribution: dict[str, int]
    ending_balance_paths: dict[str, list[float]]


def run_monte_carlo(
    *,
    portfolio_value: float,
    asset_allocation: dict[str, float],
    annual_expenses: float,
    inflation_rate: float,
    horizon_years: int,
    primary_age: int,
    retirement_age: int,
    income_sources: list[_IncomeStreamPlan],
    cma: dict[str, Any],
    trials: int,
    seed: int | None,
    annual_contribution: float = 0.0,
) -> SimulationOutputs:
    """Run the simulation. Pure function for ease of testing."""
    rng = np.random.default_rng(seed)
    classes, weights = _normalize_allocation(asset_allocation, cma)
    if not classes:
        # Cash-only fallback prevents zero-weight crash; surfaced via
        # asset_allocation == {} in inputs.
        classes = ["cash"]
        weights = np.array([1.0])

    cov = _covariance_matrix(classes, cma)
    mus = np.array([float(cma["asset_classes"][c]["expected_return"]) for c in classes])

    # One draw per (trial, year, asset class). Memory-friendly even at
    # 50k trials x 70 years x 6 classes (≈ 8MB of float64).
    samples = rng.multivariate_normal(mus, cov, size=(trials, horizon_years))
    portfolio_returns = samples @ weights  # shape (trials, years)

    inflation_factor = np.cumprod(np.full(horizon_years, 1.0 + inflation_rate))
    income_path = _income_path(
        income_sources=income_sources,
        primary_age=primary_age,
        retirement_age=retirement_age,
        horizon_years=horizon_years,
        inflation_factor=inflation_factor,
    )
    expense_path = annual_expenses * inflation_factor
    pre_retire_years = min(horizon_years, max(0, retirement_age - primary_age))
    # No withdrawals before retirement; income still flows in for any
    # source whose start_age is below retirement_age (rare, but
    # captured for completeness).
    pre_retire_mask = np.arange(horizon_years) < pre_retire_years
    expense_path = np.where(pre_retire_mask, 0.0, expense_path)

    balances = np.full(trials, float(portfolio_value))
    failure_year = np.full(trials, -1, dtype=np.int32)
    yearly_balances = np.empty((trials, horizon_years), dtype=np.float64)

    for year in range(horizon_years):
        balances *= 1.0 + portfolio_returns[:, year]
        if year < pre_retire_years and annual_contribution > 0:
            balances += annual_contribution
        net_withdrawal = expense_path[year] - income_path[year]
        if net_withdrawal > 0:
            balances -= net_withdrawal
        depleted = (balances <= 0) & (failure_year < 0)
        if depleted.any():
            failure_year[depleted] = year
            balances[depleted] = 0.0
        yearly_balances[:, year] = balances

    success_count = int(np.sum(failure_year < 0))
    success_probability = success_count / trials
    median_ending = float(np.median(yearly_balances[:, -1]))
    sor_mask = (failure_year >= 0) & (failure_year < SEQUENCE_OF_RETURNS_HORIZON)
    sequence_risk = float(np.sum(sor_mask)) / trials

    percentiles: dict[str, float] = {}
    paths: dict[str, list[float]] = {}
    for label, q in PERCENTILE_KEYS:
        col = np.percentile(yearly_balances, q, axis=0)
        percentiles[label] = float(col[-1])
        paths[label] = [float(v) for v in col]

    failure_distribution: dict[str, int] = {}
    failures = failure_year[failure_year >= 0]
    if failures.size:
        bins = np.bincount(failures, minlength=horizon_years)
        for idx, count in enumerate(bins):
            if count:
                failure_distribution[f"year_{idx + 1}"] = int(count)

    return SimulationOutputs(
        success_probability=round(success_probability, 6),
        median_ending_balance=round(median_ending, 2),
        sequence_of_returns_risk=round(sequence_risk, 6),
        percentiles={k: round(v, 2) for k, v in percentiles.items()},
        failure_year_distribution=failure_distribution,
        ending_balance_paths={k: [round(x, 2) for x in v] for k, v in paths.items()},
    )


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _normalize_allocation(
    allocation: dict[str, float], cma: dict[str, Any]
) -> tuple[list[str], NDArray[np.float64]]:
    classes_meta = cma["asset_classes"]
    pairs = [(k, float(v)) for k, v in allocation.items() if k in classes_meta and v > 0]
    if not pairs:
        return [], np.array([])
    classes = [k for k, _ in pairs]
    raw = np.array([v for _, v in pairs])
    total = raw.sum()
    if total <= 0:
        return [], np.array([])
    return classes, raw / total


def _covariance_matrix(
    classes: list[str], cma: dict[str, Any]
) -> NDArray[np.float64]:
    n = len(classes)
    sigmas = np.array(
        [float(cma["asset_classes"][c]["volatility"]) for c in classes]
    )
    cov = np.zeros((n, n), dtype=np.float64)
    correlations = cma.get("correlations", {})
    for i, ci in enumerate(classes):
        for j, cj in enumerate(classes):
            if i == j:
                cov[i, j] = sigmas[i] ** 2
                continue
            corr = _lookup_correlation(correlations, ci, cj)
            cov[i, j] = corr * sigmas[i] * sigmas[j]
    return cov


def _lookup_correlation(table: dict[str, Any], a: str, b: str) -> float:
    if a == b:
        return 1.0
    forward = table.get(a, {})
    if isinstance(forward, dict) and b in forward:
        return float(forward[b])
    backward = table.get(b, {})
    if isinstance(backward, dict) and a in backward:
        return float(backward[a])
    # Default to mild positive correlation between unspecified risk
    # assets, zero against cash.
    if a == "cash" or b == "cash":
        return 0.0
    return 0.2


def _income_path(
    *,
    income_sources: list[_IncomeStreamPlan],
    primary_age: int,
    retirement_age: int,
    horizon_years: int,
    inflation_factor: NDArray[np.float64],
) -> NDArray[np.float64]:
    del retirement_age  # primary_age + start_year is the gating condition
    income = np.zeros(horizon_years, dtype=np.float64)
    for stream in income_sources:
        years_until_start = max(0, stream.start_year - primary_age)
        if years_until_start >= horizon_years:
            continue
        annual_at_start = stream.monthly_amount * 12.0
        for year in range(years_until_start, horizon_years):
            if stream.inflation_adjusted:
                # Index from the start year so a delayed-claim Social
                # Security row tracks inflation only after it begins.
                relative = year - years_until_start
                factor = inflation_factor[relative] if relative < horizon_years else 1.0
                income[year] += annual_at_start * factor
            else:
                income[year] += annual_at_start
    return income


def income_streams_from_inputs(
    income_sources: list[Any],
) -> list[_IncomeStreamPlan]:
    """Convert ``RetirementIncomeSource`` rows to engine plans."""
    out: list[_IncomeStreamPlan] = []
    for s in income_sources:
        out.append(
            _IncomeStreamPlan(
                start_year=int(getattr(s, "start_age", 0)),
                monthly_amount=float(getattr(s, "monthly_amount", 0.0) or 0.0),
                inflation_adjusted=bool(getattr(s, "inflation_adjusted", False)),
            )
        )
    return out
