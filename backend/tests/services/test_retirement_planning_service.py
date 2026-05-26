"""Unit tests for the retirement Monte Carlo simulator (F5).

The simulation engine is exercised directly with a deterministic seed
to assert ±1% stability at 10k trials per the plan's acceptance bar.
``RetirementPlanningService`` is exercised via a stub storage that
returns canned planning rows so the build_inputs / run_simulation /
save_scenario / list / show round-trip can be asserted without
Postgres.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.portfolio.contracts.retirement import (
    RetirementAccountBucket,
    RetirementIncomeSource,
    RetirementInputs,
    ScenarioResults,
)
from app.services._retirement_simulation import (
    SimulationOutputs,
    _IncomeStreamPlan,
    _normalize_allocation,
    income_streams_from_inputs,
    run_monte_carlo,
)
from app.services.retirement_planning_service import (
    RetirementPlanningService,
    _append_preview_social_security,
    _estimate_social_security_monthly,
    _split_members,
)


def _args(**overrides: Any) -> dict[str, Any]:
    """Build engine kwargs without ruff's no-dict-call lint."""
    return overrides


# Compact CMA the engine tests use. Mirrors the YAML shape so the same
# code paths are hit without coupling tests to the file on disk.
_CMA: dict[str, Any] = {
    "version": "yaml-v1-test",
    "inflation_rate": 0.025,
    "asset_classes": {
        "us_equity": {"expected_return": 0.07, "volatility": 0.16},
        "bonds": {"expected_return": 0.04, "volatility": 0.06},
        "cash": {"expected_return": 0.02, "volatility": 0.005},
    },
    "correlations": {
        "us_equity": {"bonds": 0.1, "cash": 0.0},
        "bonds": {"cash": 0.3},
    },
}


# ----------------------------------------------------------------------
# engine — pure helpers
# ----------------------------------------------------------------------


def test_normalize_allocation_drops_unknown_classes() -> None:
    classes, weights = _normalize_allocation(
        {"us_equity": 0.6, "bonds": 0.4, "junk": 0.5}, _CMA
    )
    assert classes == ["us_equity", "bonds"]
    assert pytest.approx(weights.sum()) == 1.0
    assert pytest.approx(weights[0]) == 0.6


def test_income_streams_from_inputs_round_trip() -> None:
    sources = [
        RetirementIncomeSource(
            label="Social Security",
            start_age=67,
            monthly_amount=2500.0,
            inflation_adjusted=True,
        ),
        RetirementIncomeSource(
            label="Pension",
            start_age=65,
            monthly_amount=1500.0,
            inflation_adjusted=False,
        ),
    ]
    streams = income_streams_from_inputs(sources)
    assert [s.start_year for s in streams] == [67, 65]
    assert [s.inflation_adjusted for s in streams] == [True, False]


# ----------------------------------------------------------------------
# engine — determinism + headline metrics
# ----------------------------------------------------------------------


def test_seeded_run_is_reproducible() -> None:
    args: dict[str, Any] = _args(
        portfolio_value=1_000_000.0,
        asset_allocation={"us_equity": 0.6, "bonds": 0.4},
        annual_expenses=40_000.0,
        inflation_rate=0.025,
        horizon_years=30,
        primary_age=65,
        retirement_age=65,
        income_sources=[
            _IncomeStreamPlan(
                start_year=67, monthly_amount=2500.0, inflation_adjusted=True
            )
        ],
        cma=_CMA,
        trials=2_000,
        seed=42,
    )
    a = run_monte_carlo(**args)
    b = run_monte_carlo(**args)
    assert a.success_probability == b.success_probability
    assert a.median_ending_balance == b.median_ending_balance
    assert a.percentiles == b.percentiles


def test_balanced_portfolio_meets_one_percent_stability_at_10k() -> None:
    base: dict[str, Any] = _args(
        portfolio_value=1_500_000.0,
        asset_allocation={"us_equity": 0.6, "bonds": 0.4},
        annual_expenses=60_000.0,
        inflation_rate=0.025,
        horizon_years=30,
        primary_age=65,
        retirement_age=65,
        income_sources=[
            _IncomeStreamPlan(
                start_year=67, monthly_amount=2500.0, inflation_adjusted=True
            )
        ],
        cma=_CMA,
        trials=10_000,
    )
    runs = [run_monte_carlo(**base, seed=seed) for seed in (1, 2, 3, 4, 5)]
    probs = np.array([r.success_probability for r in runs])
    # ±1% stability bar: sample-to-sample swing capped at 0.02 absolute
    # (i.e. all runs land within ±1pp of the median).
    assert probs.max() - probs.min() <= 0.02, probs


def test_high_expenses_reduce_success_probability() -> None:
    base: dict[str, Any] = _args(
        portfolio_value=500_000.0,
        asset_allocation={"us_equity": 0.6, "bonds": 0.4},
        inflation_rate=0.025,
        horizon_years=30,
        primary_age=65,
        retirement_age=65,
        income_sources=[],
        cma=_CMA,
        trials=2_000,
        seed=99,
    )
    low = run_monte_carlo(annual_expenses=20_000.0, **base)
    high = run_monte_carlo(annual_expenses=80_000.0, **base)
    assert low.success_probability > high.success_probability


def test_pre_retirement_contributions_raise_success_probability() -> None:
    base: dict[str, Any] = _args(
        portfolio_value=250_000.0,
        asset_allocation={"us_equity": 0.6, "bonds": 0.4},
        annual_expenses=60_000.0,
        inflation_rate=0.025,
        horizon_years=30,
        primary_age=50,
        retirement_age=65,
        income_sources=[],
        cma=_CMA,
        trials=2_000,
        seed=12,
    )
    no_contribution = run_monte_carlo(**base)
    with_contribution = run_monte_carlo(**base, annual_contribution=24_000.0)
    assert with_contribution.success_probability > no_contribution.success_probability


def test_failure_year_distribution_populates_when_failures_exist() -> None:
    out = run_monte_carlo(
        portfolio_value=20_000.0,
        asset_allocation={"us_equity": 1.0},
        annual_expenses=40_000.0,
        inflation_rate=0.025,
        horizon_years=15,
        primary_age=65,
        retirement_age=65,
        income_sources=[],
        cma=_CMA,
        trials=1_000,
        seed=7,
    )
    assert out.success_probability < 0.05  # nearly certain depletion
    # All failure years should land before horizon end.
    keys = sorted(out.failure_year_distribution.keys())
    assert keys, "expected failures to populate distribution"
    for key in keys:
        year = int(key.removeprefix("year_"))
        assert 1 <= year <= 15


# ----------------------------------------------------------------------
# RetirementPlanningService — storage + cma harness
# ----------------------------------------------------------------------


class _StubConn:
    """In-memory stand-in for a Postgres connection."""

    def __init__(
        self,
        *,
        members: list[tuple[Any, ...]] | None = None,
        income_sources: list[tuple[Any, ...]] | None = None,
        positions: list[tuple[str, float]] | None = None,
        prices: dict[str, float] | None = None,
        scenarios: list[dict[str, Any]] | None = None,
        housing_total: float = 0.0,
        debt_total: float = 0.0,
        insurance_total: float = 0.0,
        monthly_savings_target: float | None = None,
    ) -> None:
        self._members = members or []
        self._income = income_sources or []
        self._positions = positions or []
        self._scenarios = scenarios if scenarios is not None else []
        self._housing = housing_total
        self._debt = debt_total
        self._insurance = insurance_total
        self._monthly_savings_target = monthly_savings_target
        self.commit = MagicMock()

    def execute(self, sql: str, params: Any = None) -> Any:
        normalized = " ".join(sql.split()).lower()
        cursor = MagicMock()
        select_sources: dict[str, Any] = {
            "from household_members": ("fetchall", self._members),
            "from household_retirement_income_sources": ("fetchall", self._income),
            "from portfolio_positions": ("fetchall", self._positions),
            "from household_housing_costs": ("fetchone", (self._housing,)),
            "from household_debt_obligations": ("fetchone", (self._debt,)),
            "from household_insurance_policies": ("fetchone", (self._insurance,)),
            "from household_profiles": ("fetchone", (self._monthly_savings_target,)),
        }
        for needle, (kind, value) in select_sources.items():
            if needle in normalized:
                getattr(cursor, kind).return_value = value
                return cursor
        if normalized.startswith("insert into retirement_scenarios"):
            return self._handle_insert_scenario(cursor, params)
        if "from retirement_scenarios" in normalized:
            return self._handle_select_scenarios(cursor, normalized, params)
        raise AssertionError(f"unhandled query: {sql}")

    def _handle_insert_scenario(self, cursor: MagicMock, params: Any) -> MagicMock:
        self._scenarios.append(
            {
                "id": params[0],
                "household_id": params[1],
                "name": params[2],
                "inputs": json.loads(params[3]),
                "results": json.loads(params[4]),
                "cma_source": params[5],
                "trial_count": params[6],
                "created_at": params[7],
            }
        )
        cursor.fetchall.return_value = []
        return cursor

    def _handle_select_scenarios(
        self, cursor: MagicMock, normalized: str, params: Any
    ) -> MagicMock:
        if "where id = " in normalized:
            target = params[0]
            row = next((s for s in self._scenarios if s["id"] == target), None)
            cursor.fetchone.return_value = None if row is None else _scenario_row_tuple(row)
            cursor.fetchall.return_value = []
            return cursor
        rows = [
            _scenario_row_tuple(row)
            for row in self._scenarios
            if row["household_id"] == params[0]
        ]
        limit = params[1] if len(params) > 1 else len(rows)
        cursor.fetchall.return_value = rows[:limit]
        return cursor


def _scenario_row_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["id"],
        row["household_id"],
        row["name"],
        json.dumps(row["results"]),
        row["cma_source"],
        row["trial_count"],
        row["created_at"],
    )


class _StubStorage:
    def __init__(self, conn: _StubConn) -> None:
        self._conn = conn

    def connection(self) -> Any:
        class _Ctx:
            def __init__(self, conn: _StubConn) -> None:
                self._conn = conn

            def __enter__(self) -> _StubConn:
                return self._conn

            def __exit__(self, *_: Any) -> None:
                pass

        return _Ctx(self._conn)


def _make_service(conn: _StubConn) -> RetirementPlanningService:
    service = RetirementPlanningService(_StubStorage(conn))
    service._cma = _CMA
    return service


def _patch_portfolio_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    *,
    total: float,
    weights: dict[str, float],
) -> None:
    def _stub_snapshot(_service: RetirementPlanningService) -> tuple[float, dict[str, float]]:
        return total, weights

    monkeypatch.setattr(
        RetirementPlanningService,
        "_portfolio_snapshot",
        _stub_snapshot,
    )


# ------------------------------------------------------------------
# split_members
# ------------------------------------------------------------------


def test_split_members_picks_primary_and_spouse_by_role() -> None:
    members = [
        {"display_name": "Alex", "role": "primary", "birth_year": 1980, "is_dependent": False},
        {"display_name": "Jordan", "role": "spouse", "birth_year": 1982, "is_dependent": False},
        {"display_name": "Kid", "role": "child", "birth_year": 2015, "is_dependent": True},
    ]
    primary, spouse = _split_members(members, current_year=2026)
    assert primary == 46
    assert spouse == 44


def test_split_members_uses_relationship_and_birthday_notes_for_current_age() -> None:
    members = [
        {
            "display_name": "Elias",
            "role": "adult",
            "relationship": "father",
            "birth_year": 1977,
            "notes": "DOB: 1977-01-11",
            "is_dependent": False,
        },
        {
            "display_name": "Mariana",
            "role": "adult",
            "relationship": "mother",
            "birth_year": 1982,
            "notes": "DOB: 1982-06-05",
            "is_dependent": False,
        },
    ]

    primary, spouse = _split_members(members, date(2026, 5, 26))

    assert primary == 49
    assert spouse == 43


def test_split_members_falls_back_when_no_role_match() -> None:
    members = [
        {"display_name": "Alex", "role": "primary", "birth_year": None, "is_dependent": False},
    ]
    primary, spouse = _split_members(members, current_year=2026)
    assert primary == 50  # default
    assert spouse is None


# ------------------------------------------------------------------
# build_inputs / run / save / list / show
# ------------------------------------------------------------------


def test_build_inputs_assembles_from_household_and_portfolio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _StubConn(
        members=[("Alex", "primary", 1980, False), ("Jordan", "spouse", 1982, False)],
        income_sources=[
            ("SS", "social_security", "Alex", 67, 2500.0, True, None),
        ],
        housing_total=2000.0,
        debt_total=500.0,
        insurance_total=200.0,
    )
    _patch_portfolio_snapshot(
        monkeypatch, total=900_000.0, weights={"us_equity": 0.6, "bonds": 0.4}
    )
    service = _make_service(conn)
    inputs = service.build_inputs("hh-test", as_of_date=date(2026, 5, 9))
    assert inputs.primary_age == 46
    assert inputs.spouse_age == 44
    assert inputs.portfolio_value == 900_000.0
    assert inputs.annual_expenses > 0
    assert inputs.income_sources[0].label == "SS"


def test_build_inputs_uses_caller_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _StubConn(
        members=[("Alex", "primary", 1980, False)],
        income_sources=[],
    )
    _patch_portfolio_snapshot(monkeypatch, total=500_000.0, weights={"us_equity": 1.0})
    service = _make_service(conn)
    inputs = service.build_inputs(
        "hh-override",
        annual_expenses=50_000.0,
        retirement_age=70,
        horizon_years=25,
        as_of_date=date(2026, 5, 9),
    )
    assert inputs.annual_expenses == 50_000.0
    assert inputs.retirement_age == 70
    assert inputs.horizon_years == 25


def test_run_simulation_caps_trials(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _StubConn(members=[("Alex", "primary", 1980, False)])
    _patch_portfolio_snapshot(monkeypatch, total=200_000.0, weights={"us_equity": 1.0})
    service = _make_service(conn)
    inputs = service.build_inputs("hh-cap", as_of_date=date(2026, 5, 9))
    out = service.run_simulation(inputs, trials=10_000_000, seed=1)
    assert out.success_probability >= 0.0
    assert out.success_probability <= 1.0


def test_save_and_show_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _StubConn(members=[("Alex", "primary", 1980, False)])
    _patch_portfolio_snapshot(
        monkeypatch, total=1_500_000.0, weights={"us_equity": 0.6, "bonds": 0.4}
    )
    service = _make_service(conn)
    inputs = service.build_inputs("hh-rt", as_of_date=date(2026, 5, 9))
    sim = service.run_simulation(inputs, trials=500, seed=42)
    saved: ScenarioResults = service.save_scenario(
        name="Baseline", inputs=inputs, sim=sim, trials=500
    )
    assert saved.summary.cma_source == "yaml-v1-test"
    fetched = service.show_scenario(saved.summary.id)
    assert fetched is not None
    assert fetched.summary.id == saved.summary.id
    # Compact view drops detail-only fields.
    assert fetched.ending_balance_paths is None
    assert fetched.cma_snapshot is None


def test_show_with_detail_returns_paths_and_cma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _StubConn(members=[("Alex", "primary", 1980, False)])
    _patch_portfolio_snapshot(
        monkeypatch, total=1_500_000.0, weights={"us_equity": 0.6, "bonds": 0.4}
    )
    service = _make_service(conn)
    inputs = service.build_inputs("hh-detail", as_of_date=date(2026, 5, 9))
    sim = service.run_simulation(inputs, trials=300, seed=11)
    saved = service.save_scenario(
        name="Detail", inputs=inputs, sim=sim, trials=300
    )
    fetched = service.show_scenario(saved.summary.id, detail=True)
    assert fetched is not None
    assert fetched.ending_balance_paths is not None
    assert "p50" in fetched.ending_balance_paths
    assert fetched.cma_snapshot is not None


def test_list_returns_most_recent_first(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _StubConn(members=[("Alex", "primary", 1980, False)])
    _patch_portfolio_snapshot(monkeypatch, total=300_000.0, weights={"us_equity": 1.0})
    service = _make_service(conn)
    inputs = service.build_inputs("hh-list", as_of_date=date(2026, 5, 9))
    sim = service.run_simulation(inputs, trials=200, seed=1)
    a = service.save_scenario(name="A", inputs=inputs, sim=sim, trials=200)
    b = service.save_scenario(name="B", inputs=inputs, sim=sim, trials=200)
    rows = service.list_scenarios("hh-list", limit=10)
    ids = [r.id for r in rows]
    assert {a.summary.id, b.summary.id} == set(ids)
    assert len(rows) == 2


def test_show_returns_none_for_missing_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _StubConn()
    service = _make_service(conn)
    assert service.show_scenario("does-not-exist") is None


def test_preview_builds_account_buckets_and_levers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _StubConn(
        members=[("Alex", "primary", 1980, False)],
        monthly_savings_target=1500.0,
    )
    _patch_portfolio_snapshot(
        monkeypatch, total=1_000_000.0, weights={"us_equity": 0.6, "bonds": 0.4}
    )
    dashboard = SimpleNamespace(
        profile=SimpleNamespace(
            id="hh-preview",
            target_retirement_spend=6_000.0,
            target_retirement_age=65,
            monthly_savings_target=1_500.0,
            effective_tax_rate=22.0,
            marginal_federal_tax_rate=None,
        ),
        account_control=SimpleNamespace(
            status="clear",
            summary="Account source controls are clear.",
            blocking_issue_count=0,
        ),
        accounts=[
            SimpleNamespace(label="Brokerage", asset_group="taxable", account_type="brokerage", current_value=250_000.0),
            SimpleNamespace(label="PCSB 457(b)", asset_group="retirement", account_type="governmental_457b", current_value=95_000.0),
            SimpleNamespace(label="IRA", asset_group="retirement", account_type="ira", current_value=400_000.0),
            SimpleNamespace(label="Roth", asset_group="retirement", account_type="roth_ira", current_value=200_000.0),
            SimpleNamespace(label="Cash", asset_group="cash", account_type="savings", current_value=50_000.0),
        ],
    )
    monkeypatch.setattr(
        RetirementPlanningService,
        "_load_money_dashboard",
        lambda _service: dashboard,
    )
    service = _make_service(conn)
    preview = service.preview(
        "hh-preview",
        retirement_age=65,
        monthly_spend=6_000.0,
        horizon_years=25,
        trials=500,
        seed=5,
        as_of_date=date(2026, 5, 9),
    )
    assert preview.trusted_totals is True
    assert preview.inputs.portfolio_value == 995_000.0
    assert {bucket.bucket_type for bucket in preview.account_buckets} == {
        "cash",
        "taxable",
        "governmental_457b",
        "pre_tax",
        "roth",
    }
    assert preview.drawdown_schedule
    assert len(preview.lever_impacts) == 3


def test_preview_adds_social_security_knobs_on_primary_age_timeline() -> None:
    inputs = RetirementInputs(
        household_id="hh-ss",
        primary_age=49,
        spouse_age=43,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=72_000.0,
        annual_contribution=0.0,
        portfolio_value=500_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 26),
    )

    updated = _append_preview_social_security(
        inputs,
        primary_monthly=2_500.0,
        spouse_monthly=1_800.0,
        primary_annual_earnings=None,
        spouse_annual_earnings=None,
        primary_start_age=67,
        spouse_start_age=67,
    )

    assert [source.label for source in updated.income_sources] == [
        "Social Security - primary",
        "Social Security - spouse at 67",
    ]
    assert updated.income_sources[0].start_age == 67
    assert updated.income_sources[1].start_age == 73


def test_social_security_estimate_from_annual_earnings_feeds_income_sources() -> None:
    inputs = RetirementInputs(
        household_id="hh-ss-estimate",
        primary_age=49,
        spouse_age=43,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=72_000.0,
        annual_contribution=0.0,
        portfolio_value=500_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 26),
    )

    updated = _append_preview_social_security(
        inputs,
        primary_monthly=None,
        spouse_monthly=None,
        primary_annual_earnings=120_000.0,
        spouse_annual_earnings=80_000.0,
        primary_start_age=67,
        spouse_start_age=67,
    )

    assert updated.income_sources[0].monthly_amount == _estimate_social_security_monthly(
        120_000.0,
        claim_age=67,
    )
    assert updated.income_sources[1].monthly_amount == _estimate_social_security_monthly(
        80_000.0,
        claim_age=67,
    )


def test_drawdown_schedule_applies_pre_tax_rmd_estimate() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-rmd",
        primary_age=72,
        spouse_age=None,
        retirement_age=72,
        horizon_years=3,
        annual_expenses=0.0,
        annual_contribution=0.0,
        portfolio_value=274_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 9),
    )
    rows = service._drawdown_schedule(
        inputs,
        buckets=(
            RetirementAccountBucket(
                bucket_type="pre_tax",
                label="Traditional IRA",
                account_type="ira",
                tax_treatment="ordinary_income",
                current_value=274_000.0,
                withdrawal_priority=3,
            ),
        ),
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )
    age_73 = next(row for row in rows if row.primary_age == 73)
    assert age_73.rmd_applied is True
    assert age_73.withdrawals_by_bucket["pre_tax"] > 0


def test_drawdown_uses_governmental_457b_before_penalized_pre_tax_before_age_60() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-457b",
        primary_age=55,
        spouse_age=None,
        retirement_age=55,
        horizon_years=1,
        annual_expenses=90_000.0,
        annual_contribution=0.0,
        portfolio_value=120_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 9),
    )
    rows = service._drawdown_schedule(
        inputs,
        buckets=(
            RetirementAccountBucket(
                bucket_type="governmental_457b",
                label="PCSB 457(b)",
                account_type="governmental_457b",
                tax_treatment="ordinary_income_no_10pct_early_penalty",
                current_value=60_000.0,
                withdrawal_priority=3,
            ),
            RetirementAccountBucket(
                bucket_type="pre_tax",
                label="Traditional IRA",
                account_type="ira",
                tax_treatment="ordinary_income",
                current_value=60_000.0,
                withdrawal_priority=4,
            ),
        ),
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )

    first = rows[0]
    assert first.withdrawals_by_bucket["governmental_457b"] > 0
    assert first.withdrawals_by_bucket["pre_tax"] > 0
    assert first.penalty_estimate == round(first.withdrawals_by_bucket["pre_tax"] * 0.10, 2)


_ = SimulationOutputs
_ = RetirementInputs
_ = datetime
_ = UTC
