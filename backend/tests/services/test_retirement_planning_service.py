"""Unit tests for the retirement Monte Carlo simulator (F5).

The unified tax-aware Monte Carlo is exercised through
``RetirementPlanningService.run_simulation`` with deterministic seeds to
assert reproducibility and seed-to-seed stability.
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
    RetirementCollegeYear,
    RetirementIncomeSource,
    RetirementInputs,
    ScenarioResults,
    WithdrawalBridgeConfig,
    WithdrawalConfig,
)
from app.services._retirement_simulation import (
    SimulationOutputs,
    _normalize_allocation,
)
from app.services.retirement_planning_service import (
    DEFAULT_DRAWDOWN_ORDER,
    DEFAULT_SPAXX_CASH_YIELD_AS_OF,
    TAXABLE_WITHDRAWAL_GAIN_RATIO,
    RetirementPlanningService,
    _account_rule_explanations,
    _aggregate_income_yield_freshness,
    _append_preview_social_security,
    _early_withdrawal_penalty_rate,
    _effective_gain_ratio,
    _estimate_social_security_monthly,
    _failure_age_distribution,
    _federal_tax_estimate,
    _rmd_amount,
    _split_members,
    _tax_assumptions,
    _tax_context_from_profile,
    _withdrawal_config_from_inputs,
    _yield_freshness,
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


# ----------------------------------------------------------------------
# engine — determinism + headline metrics (via service.run_simulation,
# the single unified tax-aware Monte Carlo path)
# ----------------------------------------------------------------------


_SS_AT_67 = (
    RetirementIncomeSource(
        label="Social Security",
        start_age=67,
        monthly_amount=2500.0,
        inflation_adjusted=True,
    ),
)


def _engine_inputs(**overrides: Any) -> RetirementInputs:
    base: dict[str, Any] = _args(
        household_id="hh-engine",
        primary_age=65,
        spouse_age=None,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=40_000.0,
        annual_contribution=0.0,
        portfolio_value=1_000_000.0,
        asset_allocation={"us_equity": 0.6, "bonds": 0.4},
        income_sources=_SS_AT_67,
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 9),
    )
    base.update(overrides)
    return RetirementInputs(**base)


def test_seeded_run_is_reproducible() -> None:
    service = _make_service(_StubConn())
    inputs = _engine_inputs()
    a = service.run_simulation(inputs, trials=800, seed=42)
    b = service.run_simulation(inputs, trials=800, seed=42)
    assert a.success_probability == b.success_probability
    assert a.median_ending_balance == b.median_ending_balance
    assert a.percentiles == b.percentiles
    assert a.median_discretionary_path == b.median_discretionary_path


def test_balanced_portfolio_success_is_seed_stable() -> None:
    service = _make_service(_StubConn())
    inputs = _engine_inputs(
        portfolio_value=900_000.0,
        annual_expenses=60_000.0,
        horizon_years=10,
        income_sources=(),
    )
    runs = [
        service.run_simulation(inputs, trials=2_000, seed=seed)
        for seed in (1, 2, 3)
    ]
    probs = np.array([r.success_probability for r in runs])
    # Seed-to-seed swing stays within 4pp at 2k trials (binomial std is
    # ≤1.1pp); the deeper 10k-trial bar lives in the plan's acceptance
    # run, not in the per-commit suite (coverage makes 10k ≈ minutes).
    assert probs.max() - probs.min() <= 0.04, probs
    assert 0.05 < probs.mean() < 0.999, "want a non-degenerate probability"


def test_high_expenses_reduce_success_probability() -> None:
    service = _make_service(_StubConn())
    low = service.run_simulation(
        _engine_inputs(
            portfolio_value=500_000.0, annual_expenses=20_000.0, income_sources=()
        ),
        trials=1_000,
        seed=99,
    )
    high = service.run_simulation(
        _engine_inputs(
            portfolio_value=500_000.0, annual_expenses=80_000.0, income_sources=()
        ),
        trials=1_000,
        seed=99,
    )
    assert low.success_probability > high.success_probability


def test_pre_retirement_contributions_raise_success_probability() -> None:
    service = _make_service(_StubConn())
    base: dict[str, Any] = _args(
        primary_age=50,
        retirement_age=65,
        portfolio_value=250_000.0,
        annual_expenses=60_000.0,
        income_sources=(),
    )
    no_contribution = service.run_simulation(
        _engine_inputs(**base), trials=1_000, seed=12
    )
    with_contribution = service.run_simulation(
        _engine_inputs(**base, annual_contribution=24_000.0), trials=1_000, seed=12
    )
    assert with_contribution.success_probability > no_contribution.success_probability


def test_failure_year_distribution_populates_when_failures_exist() -> None:
    service = _make_service(_StubConn())
    out = service.run_simulation(
        _engine_inputs(
            portfolio_value=20_000.0,
            asset_allocation={"us_equity": 1.0},
            annual_expenses=40_000.0,
            horizon_years=15,
            income_sources=(),
        ),
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


def test_median_discretionary_path_covers_horizon_and_declines() -> None:
    service = _make_service(_StubConn())
    withdrawal = WithdrawalConfig(
        strategy="vpw",
        decline_mode="smooth",
        discretionary_decline_rate=0.02,
        essential_floor=30_000.0,
        base_discretionary=20_000.0,
    )
    inputs = _engine_inputs(
        portfolio_value=5_000_000.0,
        asset_allocation={"cash": 1.0},
        annual_expenses=50_000.0,
        income_sources=(),
        withdrawal=withdrawal,
    )
    out = service.run_simulation(inputs, trials=200, seed=3)
    path = out.median_discretionary_path
    assert len(path) == inputs.horizon_years
    # Fully funded in year one (huge cash portfolio), then declining with
    # age per the smooth decline factor.
    assert path[0] == pytest.approx(20_000.0, rel=0.01)
    assert path[10] < path[0]
    assert path[-1] < path[10]


def test_median_discretionary_path_zero_before_retirement() -> None:
    service = _make_service(_StubConn())
    inputs = _engine_inputs(
        primary_age=60,
        retirement_age=65,
        horizon_years=10,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        withdrawal=WithdrawalConfig(
            essential_floor=30_000.0, base_discretionary=20_000.0
        ),
    )
    out = service.run_simulation(inputs, trials=100, seed=5)
    assert out.median_discretionary_path[:5] == [0.0] * 5
    assert any(v > 0 for v in out.median_discretionary_path[5:])


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
        tax_lots: list[tuple[Any, ...]] | None = None,
        reference_yields: list[tuple[Any, ...]] | None = None,
        healthcare_schedule: list[tuple[Any, ...]] | None = None,
    ) -> None:
        self._members = members or []
        self._income = income_sources or []
        self._healthcare = healthcare_schedule or []
        self._positions = positions or []
        self._tax_lots = tax_lots or []
        self._reference_yields = reference_yields or []
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
            "from household_retirement_healthcare_schedule": (
                "fetchall",
                self._healthcare,
            ),
            "from household_retirement_college_schedule": ("fetchall", []),
            "from portfolio_positions": ("fetchall", self._positions),
            "from household_housing_costs": ("fetchone", (self._housing,)),
            "from household_debt_obligations": ("fetchone", (self._debt,)),
            "from household_insurance_policies": ("fetchone", (self._insurance,)),
            "from household_profiles": ("fetchone", (self._monthly_savings_target,)),
            "from portfolio_tax_lots": ("fetchall", self._tax_lots),
        }
        for needle, (kind, value) in select_sources.items():
            if needle in normalized:
                getattr(cursor, kind).return_value = value
                return cursor
        if "from reference_cache" in normalized:
            symbol = params[0] if params else None
            match = next(
                (row for row in self._reference_yields if row and row[0] == symbol),
                None,
            )
            cursor.fetchone.return_value = None if match is None else match[1:]
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
            "display_name": "Alex Demo",
            "role": "adult",
            "relationship": "father",
            "birth_year": 1977,
            "notes": "DOB: 1977-01-11",
            "is_dependent": False,
        },
        {
            "display_name": "Jordan Demo",
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
        asset_allocation={"us_equity": 80, "cash": 20},
        retirement_age=70,
        horizon_years=25,
        as_of_date=date(2026, 5, 9),
    )
    assert inputs.annual_expenses == 50_000.0
    assert inputs.retirement_age == 70
    assert inputs.horizon_years == 25
    assert inputs.asset_allocation == {"us_equity": 0.8, "cash": 0.2}
    assert inputs.cash_yield == pytest.approx(0.0328)


def test_run_simulation_caps_trials(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _StubConn(members=[("Alex", "primary", 1980, False)])
    _patch_portfolio_snapshot(monkeypatch, total=200_000.0, weights={"us_equity": 1.0})
    monkeypatch.setattr(
        "app.services.retirement_planning_service.MAX_TRIALS", 250
    )
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
            SimpleNamespace(
                label="Brokerage",
                asset_group="taxable",
                account_type="brokerage",
                linked_portfolio_account_id="acct-tax",
                current_value=250_000.0,
                holdings_value=250_000.0,
                cash_balance=0.0,
                priced_position_count=1,
            ),
            SimpleNamespace(
                label="PCSB 457(b)",
                asset_group="retirement",
                account_type="governmental_457b",
                linked_portfolio_account_id=None,
                current_value=95_000.0,
                holdings_value=95_000.0,
                cash_balance=0.0,
                priced_position_count=0,
            ),
            SimpleNamespace(
                label="IRA",
                asset_group="retirement",
                account_type="ira",
                linked_portfolio_account_id=None,
                current_value=400_000.0,
                holdings_value=400_000.0,
                cash_balance=0.0,
                priced_position_count=0,
            ),
            SimpleNamespace(
                label="Roth",
                asset_group="retirement",
                account_type="roth_ira",
                linked_portfolio_account_id=None,
                current_value=200_000.0,
                holdings_value=200_000.0,
                cash_balance=0.0,
                priced_position_count=0,
            ),
            SimpleNamespace(
                label="Cash",
                asset_group="cash",
                account_type="savings",
                linked_portfolio_account_id=None,
                current_value=50_000.0,
                holdings_value=0.0,
                cash_balance=50_000.0,
                priced_position_count=0,
            ),
        ],
    )
    monkeypatch.setattr(
        RetirementPlanningService,
        "_load_money_dashboard",
        lambda _service: dashboard,
    )
    monkeypatch.setattr(
        RetirementPlanningService,
        "_priced_holdings_by_account",
        lambda _service, _account_ids: {
            "acct-tax": [{"symbol": "VTI", "current_value": 250_000.0}]
        },
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
    assert preview.inputs.asset_allocation["cash"] == pytest.approx(50_000 / 995_000, abs=1e-6)
    assert preview.inputs.cash_yield == pytest.approx(0.0328)
    assert preview.return_assumptions["cash_yield"] == pytest.approx(0.0328)
    assert preview.holdings_coverage.status == "partial"
    assert preview.holdings_coverage.exact_share == pytest.approx(300_000 / 995_000, abs=1e-6)
    assert preview.holdings_coverage.exact_value == 300_000.0
    assert preview.holdings_coverage.inferred_value == 695_000.0
    coverage_by_label = {row.label: row for row in preview.holdings_coverage.accounts}
    assert coverage_by_label["Brokerage"].coverage_status == "exact_holdings"
    assert coverage_by_label["Cash"].coverage_status == "cash"
    assert coverage_by_label["IRA"].coverage_status == "account_value_only"
    assert preview.account_allocation_coverage.status == "partial"
    assert preview.account_allocation_coverage.exact_share == pytest.approx(
        300_000 / 995_000,
        abs=1e-6,
    )
    assert preview.account_allocation_coverage.asset_allocation["cash"] == pytest.approx(
        50_000 / 995_000,
        abs=1e-6,
    )
    assert preview.account_allocation_coverage.asset_allocation["us_equity"] == pytest.approx(
        (250_000 + 695_000 * 0.6) / 995_000,
        abs=1e-6,
    )
    assert preview.account_allocation_coverage.asset_allocation["bonds"] == pytest.approx(
        (695_000 * 0.4) / 995_000,
        abs=1e-6,
    )
    allocation_by_label = {
        row.label: row for row in preview.account_allocation_coverage.accounts
    }
    assert allocation_by_label["Brokerage"].allocation_status == "exact_allocation"
    assert allocation_by_label["Brokerage"].allocation == {"us_equity": 1.0}
    assert allocation_by_label["IRA"].allocation_status == "account_value_only"
    assert allocation_by_label["IRA"].allocation["us_equity"] == pytest.approx(0.6)
    assert allocation_by_label["IRA"].allocation["bonds"] == pytest.approx(0.4)
    assert preview.inputs.asset_allocation == preview.account_allocation_coverage.asset_allocation
    assert {bucket.bucket_type for bucket in preview.account_buckets} == {
        "cash",
        "taxable",
        "governmental_457b",
        "pre_tax",
        "roth",
    }
    assert preview.drawdown_schedule
    assert len(preview.lever_impacts) == 3


def test_account_buckets_split_taxable_cash_from_invested_taxable() -> None:
    service = _make_service(_StubConn())
    dashboard = SimpleNamespace(
        accounts=[
            SimpleNamespace(
                label="Cash Management",
                asset_group="taxable",
                account_type="brokerage",
                current_value=40_000.0,
                cash_balance=40_000.0,
            ),
            SimpleNamespace(
                label="Taxable Brokerage",
                asset_group="taxable",
                account_type="brokerage",
                current_value=110_000.0,
                cash_balance=10_000.0,
            ),
        ],
    )

    buckets = service._account_buckets_from_dashboard(dashboard)

    assert sum(bucket.current_value for bucket in buckets if bucket.bucket_type == "cash") == 50_000.0
    assert sum(bucket.current_value for bucket in buckets if bucket.bucket_type == "taxable") == 100_000.0


def test_return_assumptions_use_ticker_income_yields() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-yield",
        primary_age=50,
        spouse_age=None,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=72_000.0,
        annual_contribution=0.0,
        portfolio_value=1_000_000.0,
        asset_allocation={"us_equity": 0.9, "cash": 0.1},
        cash_yield=0.0328,
        as_of_date=date(2026, 5, 9),
    )

    assumptions = service._return_assumptions(
        inputs,
        allocation_holdings=[
            {"symbol": "SCHD", "weight": 50, "dividend_yield": 3.6},
            {"symbol": "SPAXX", "weight": 50},
        ],
        tax_context=_tax_context_from_profile(
            SimpleNamespace(filing_status="married_filing_jointly", state_of_residence="FL"),
            inputs,
        ),
        buckets=(
            RetirementAccountBucket(
                bucket_type="taxable",
                label="Taxable",
                account_type="brokerage",
                tax_treatment="taxable_capital_gains_estimate",
                current_value=1_000_000.0,
                withdrawal_priority=2,
            ),
        ),
        baseline_ordinary_income=180_000.0,
    )

    assert assumptions["income_yield"] == pytest.approx((0.036 + 0.0328) / 2)
    assert assumptions["estimated_taxable_income"] > 0
    assert assumptions["estimated_income_tax_drag"] > 0
    assert assumptions["holding_income_yields"][0]["source"] == "user"
    assert assumptions["holding_income_yields"][1]["source"] == "cash_yield"


def test_drawdown_first_year_starts_at_current_bucket_values() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-start",
        primary_age=49,
        spouse_age=43,
        retirement_age=65,
        horizon_years=2,
        annual_expenses=72_000.0,
        annual_contribution=0.0,
        portfolio_value=150_000.0,
        asset_allocation={"us_equity": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 26),
    )

    rows = service._drawdown_schedule(
        inputs,
        buckets=(
            RetirementAccountBucket(
                bucket_type="taxable",
                label="Taxable",
                account_type="brokerage",
                tax_treatment="taxable_capital_gains_estimate",
                current_value=100_000.0,
                withdrawal_priority=2,
            ),
            RetirementAccountBucket(
                bucket_type="pre_tax",
                label="IRA",
                account_type="ira",
                tax_treatment="ordinary_income",
                current_value=50_000.0,
                withdrawal_priority=4,
            ),
        ),
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )

    assert rows[0].balances_by_bucket["taxable"] == 100_000.0
    assert rows[0].balances_by_bucket["pre_tax"] == 50_000.0
    assert rows[1].balances_by_bucket["taxable"] > 100_000.0


def test_federal_tax_estimate_derives_rate_from_projected_income() -> None:
    inputs = RetirementInputs(
        household_id="hh-tax",
        primary_age=65,
        spouse_age=59,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=90_000.0,
        annual_contribution=0.0,
        portfolio_value=500_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 26),
    )
    context = _tax_context_from_profile(
        SimpleNamespace(filing_status="Married filing jointly", state_of_residence="FL"),
        inputs,
    )

    tax = _federal_tax_estimate(
        context,
        ordinary_income=90_000.0,
        social_security_benefits=0.0,
        long_term_capital_gains=0.0,
        primary_age=65,
        spouse_age=59,
        inflation_factor=1.0,
    )

    assert 0.05 < tax / 90_000.0 < 0.10
    assert context.state_tax_rate == 0.0


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


def test_social_security_start_age_only_does_not_clear_saved_income_sources() -> None:
    saved_source = RetirementIncomeSource(
        label="Saved Social Security",
        source_type="social_security",
        owner_name="primary",
        start_age=67,
        monthly_amount=2_000.0,
        inflation_adjusted=True,
    )
    inputs = RetirementInputs(
        household_id="hh-ss-saved",
        primary_age=49,
        spouse_age=43,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=72_000.0,
        annual_contribution=0.0,
        portfolio_value=500_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(saved_source,),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 26),
    )

    updated = _append_preview_social_security(
        inputs,
        primary_monthly=None,
        spouse_monthly=None,
        primary_annual_earnings=None,
        spouse_annual_earnings=None,
        primary_start_age=70,
        spouse_start_age=67,
    )

    assert updated.income_sources == (saved_source,)


def test_drawdown_applies_social_security_payable_ratio_after_depletion_year() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-ss-haircut",
        primary_age=65,
        spouse_age=None,
        retirement_age=65,
        horizon_years=2,
        annual_expenses=0.0,
        annual_contribution=0.0,
        portfolio_value=0.0,
        asset_allocation={"cash": 1.0},
        income_sources=(
            RetirementIncomeSource(
                label="Social Security",
                source_type="social_security",
                owner_name="primary",
                start_age=65,
                monthly_amount=1_000.0,
                inflation_adjusted=False,
            ),
        ),
        inflation_rate=0.0,
        social_security_payable_ratio=0.77,
        social_security_depletion_year=2033,
        as_of_date=date(2032, 1, 1),
    )

    rows = service._drawdown_schedule(inputs, buckets=())

    assert rows[0].calendar_year == 2032
    assert rows[0].income == 12_000.0
    assert rows[1].calendar_year == 2033
    assert rows[1].income == 9_240.0


def test_drawdown_starts_when_later_spouse_retirement_age_arrives() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-spouse-retire",
        primary_age=50,
        spouse_age=44,
        retirement_age=50,
        spouse_retirement_age=55,
        horizon_years=12,
        annual_expenses=72_000.0,
        annual_contribution=12_000.0,
        portfolio_value=200_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.0,
        as_of_date=date(2026, 5, 26),
    )

    rows = service._drawdown_schedule(
        inputs,
        buckets=(
            RetirementAccountBucket(
                bucket_type="taxable",
                label="Brokerage",
                account_type="brokerage",
                tax_treatment="taxable_capital_gains_estimate",
                current_value=200_000.0,
                withdrawal_priority=2,
            ),
        ),
    )

    assert rows[0].primary_age == 50
    assert rows[0].spending_need == 0.0
    assert rows[10].primary_age == 60
    assert rows[10].spending_need == 0.0
    assert rows[11].primary_age == 61
    assert rows[11].spending_need == 72_000.0
    assert rows[11].gross_withdrawal > 0


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


def test_rmd_amount_uses_irs_uniform_lifetime_divisors() -> None:
    # Exact published divisors (effective 2022), not a linear approximation.
    balance = 1_000_000.0
    assert _rmd_amount(balance, 72) == pytest.approx(0.0)  # below RMD start age
    assert _rmd_amount(balance, 73) == pytest.approx(balance / 26.5)
    assert _rmd_amount(balance, 80) == pytest.approx(balance / 20.2)
    assert _rmd_amount(balance, 90) == pytest.approx(balance / 12.2)
    # Ages past the table top out at the 120+ divisor (does not over-deplete).
    assert _rmd_amount(balance, 130) == pytest.approx(balance / 2.0)
    assert _rmd_amount(0.0, 90) == pytest.approx(0.0)


def test_early_withdrawal_penalty_matches_59_and_a_half_rule() -> None:
    assert _early_withdrawal_penalty_rate("pre_tax", 58) == pytest.approx(0.10)
    assert _early_withdrawal_penalty_rate("pre_tax", 59) == pytest.approx(0.10)
    assert _early_withdrawal_penalty_rate("pre_tax", 60) == pytest.approx(0.0)
    # No early-withdrawal penalty on governmental 457(b) at any age.
    assert _early_withdrawal_penalty_rate("governmental_457b", 50) == pytest.approx(0.0)


def test_tax_aware_monte_carlo_preserves_governmental_457b_early_access() -> None:
    service = _make_service(_StubConn())
    inputs = RetirementInputs(
        household_id="hh-457b-mc",
        primary_age=55,
        spouse_age=None,
        retirement_age=55,
        horizon_years=1,
        annual_expenses=82_000.0,
        annual_contribution=0.0,
        portfolio_value=100_000.0,
        asset_allocation={"cash": 1.0},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 9),
    )
    gov_457b = (
        RetirementAccountBucket(
            bucket_type="governmental_457b",
            label="PCSB 457(b)",
            account_type="governmental_457b",
            tax_treatment="ordinary_income_no_10pct_early_penalty",
            current_value=100_000.0,
            withdrawal_priority=3,
        ),
    )
    pre_tax = (
        RetirementAccountBucket(
            bucket_type="pre_tax",
            label="Traditional IRA",
            account_type="ira",
            tax_treatment="ordinary_income",
            current_value=100_000.0,
            withdrawal_priority=4,
        ),
    )

    gov_out = service.run_simulation(inputs, buckets=gov_457b, trials=50, seed=1)
    pre_tax_out = service.run_simulation(inputs, buckets=pre_tax, trials=50, seed=1)

    assert gov_out.success_probability == 1.0
    assert pre_tax_out.success_probability == 0.0


class _FakePriceInfo:
    def __init__(self, price: float) -> None:
        self.price = price
        self.error = None


class _FakePriceFetcher:
    def __init__(self, prices: dict[str, float]) -> None:
        self._prices = prices

    def fetch_cached_price_data(self, symbols: list[str]) -> dict[str, _FakePriceInfo]:
        return {sym: _FakePriceInfo(self._prices[sym]) for sym in symbols if sym in self._prices}


def _patch_price_fetcher(monkeypatch: pytest.MonkeyPatch, prices: dict[str, float]) -> None:
    price_mod = __import__("app.portfolio.price_fetcher", fromlist=["PriceDataFetcher"])
    monkeypatch.setattr(
        price_mod, "PriceDataFetcher", lambda _storage: _FakePriceFetcher(prices)
    )


# ------------------------------------------------------------------
# yield freshness + dividend tax-character disclosure
# ------------------------------------------------------------------


def test_yield_freshness_buckets_by_age() -> None:
    anchor = date(2026, 5, 26)
    assert _yield_freshness(date(2026, 5, 20), anchor)[0] == "fresh"
    assert _yield_freshness(date(2026, 4, 20), anchor)[0] == "aging"
    assert _yield_freshness(date(2026, 1, 1), anchor)[0] == "stale"
    assert _yield_freshness(None, anchor) == ("needs_evidence", "Planning assumption")


def test_aggregate_income_yield_freshness_reports_worst() -> None:
    rows = [
        {"freshness_status": "fresh"},
        {"freshness_status": "stale"},
        {"freshness_status": "aging"},
    ]
    assert _aggregate_income_yield_freshness(rows)[0] == "stale"
    assert _aggregate_income_yield_freshness([])[0] == "needs_evidence"


def test_return_assumptions_surface_yield_freshness_and_tax_character() -> None:
    service = _make_service(
        _StubConn(reference_yields=[("VYM", 0.028, date(2026, 5, 20))])
    )
    inputs = RetirementInputs(
        household_id="hh-fresh",
        primary_age=50,
        spouse_age=None,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=72_000.0,
        annual_contribution=0.0,
        portfolio_value=1_000_000.0,
        asset_allocation={"us_equity": 0.9, "cash": 0.1},
        cash_yield=0.0328,
        as_of_date=date(2026, 5, 26),
    )
    assumptions = service._return_assumptions(
        inputs,
        allocation_holdings=[{"symbol": "VYM", "weight": 100}],
        tax_context=_tax_context_from_profile(
            SimpleNamespace(filing_status="single", state_of_residence="FL"), inputs
        ),
    )
    row = assumptions["holding_income_yields"][0]
    assert row["source"] == "reference_cache"
    assert row["as_of"] == "2026-05-20"
    assert row["freshness_status"] == "fresh"
    assert assumptions["income_yield_freshness_status"] == "fresh"
    assert assumptions["cash_yield_as_of"] == DEFAULT_SPAXX_CASH_YIELD_AS_OF.isoformat()
    assert assumptions["dividend_tax_character"]["basis"] == "assumption"


# ------------------------------------------------------------------
# taxable embedded gain ratio from tax lots
# ------------------------------------------------------------------


def test_effective_gain_ratio_prefers_lots_over_default() -> None:
    base = RetirementInputs(
        household_id="hh-g",
        primary_age=50,
        spouse_age=None,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=60_000.0,
        annual_contribution=0.0,
        portfolio_value=500_000.0,
        asset_allocation={"us_equity": 1.0},
        as_of_date=date(2026, 5, 26),
    )
    assert _effective_gain_ratio(base) == TAXABLE_WITHDRAWAL_GAIN_RATIO
    with_lots = base.model_copy(update={"taxable_gain_ratio": 0.42})
    assert _effective_gain_ratio(with_lots) == 0.42
    # A genuine zero-gain ratio must not fall back to the planning default.
    no_gain = base.model_copy(update={"taxable_gain_ratio": 0.0})
    assert _effective_gain_ratio(no_gain) == 0.0


def test_taxable_embedded_gain_ratio_from_lots(monkeypatch: pytest.MonkeyPatch) -> None:
    # 100 shares cost $60/sh ($6,000 basis), now worth $100/sh ($10,000) → 40% gain.
    conn = _StubConn(tax_lots=[("VTI", 100.0, 6_000.0)])
    service = _make_service(conn)
    _patch_price_fetcher(monkeypatch, {"VTI": 100.0})
    result = service._taxable_embedded_gain_ratio(["acct-tax"])
    assert result is not None
    ratio, meta = result
    assert ratio == pytest.approx(0.4)
    assert meta["cost_basis"] == 6_000.0
    assert meta["market_value"] == 10_000.0


def test_taxable_embedded_gain_ratio_none_without_lots() -> None:
    service = _make_service(_StubConn())
    assert service._taxable_embedded_gain_ratio(["acct-tax"]) is None
    assert service._taxable_embedded_gain_ratio([]) is None


def test_tax_assumptions_report_lots_gain_ratio() -> None:
    inputs = RetirementInputs(
        household_id="hh-t",
        primary_age=50,
        spouse_age=None,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=60_000.0,
        annual_contribution=0.0,
        portfolio_value=500_000.0,
        asset_allocation={"us_equity": 1.0},
        taxable_gain_ratio=0.4,
        as_of_date=date(2026, 5, 26),
    )
    context = _tax_context_from_profile(
        SimpleNamespace(filing_status="single", state_of_residence="FL"), inputs
    )
    assumptions = _tax_assumptions(
        context,
        inputs=inputs,
        gain_ratio_meta={"cost_basis": 6_000.0, "market_value": 10_000.0},
    )
    assert assumptions["taxable_withdrawal_gain_ratio"] == 0.4
    assert assumptions["taxable_withdrawal_gain_ratio_source"] == "tax_lots"
    assert assumptions["taxable_cost_basis"] == 6_000.0

    default_assumptions = _tax_assumptions(context, inputs=None)
    assert default_assumptions["taxable_withdrawal_gain_ratio"] == TAXABLE_WITHDRAWAL_GAIN_RATIO
    assert default_assumptions["taxable_withdrawal_gain_ratio_source"] == "planning_assumption"


# ------------------------------------------------------------------
# plan-specific rule explanations
# ------------------------------------------------------------------


def test_account_rule_explanations_cover_present_buckets() -> None:
    buckets = (
        RetirementAccountBucket(
            bucket_type="governmental_457b",
            label="PCSB 457(b)",
            account_type="governmental_457b",
            tax_treatment="ordinary_income_no_10pct_early_penalty",
            current_value=95_000.0,
            withdrawal_priority=3,
        ),
        RetirementAccountBucket(
            bucket_type="roth",
            label="Roth IRA",
            account_type="roth_ira",
            tax_treatment="tax_free_if_qualified",
            current_value=50_000.0,
            withdrawal_priority=6,
        ),
    )
    rules = _account_rule_explanations(buckets)
    by_type = {rule.bucket_type: rule for rule in rules}
    assert set(by_type) == {"governmental_457b", "roth"}
    assert "separate from service" in by_type["governmental_457b"].early_access
    assert by_type["governmental_457b"].rmd.startswith("Required minimum")
    assert "no lifetime RMDs" in by_type["roth"].rmd
    assert by_type["roth"].tax_treatment == "Tax-free if qualified"


# ----------------------------------------------------------------------
# budget-ratio floor resolution (NULL vs explicit-zero discretionary)
# ----------------------------------------------------------------------


def _budget_profile(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = _args(
        monthly_essential_target=5_000.0,
        monthly_discretionary_target=None,
        target_retirement_spend=7_500.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_null_discretionary_derived_from_retirement_spend_target() -> None:
    inputs = _engine_inputs(annual_expenses=90_000.0)
    cfg = _withdrawal_config_from_inputs(inputs, _budget_profile(), WithdrawalConfig())
    # essential share = 5000 / 7500; discretionary derived from the spend
    # target instead of collapsing to zero.
    assert cfg.essential_floor == pytest.approx(60_000.0)
    assert cfg.base_discretionary == pytest.approx(30_000.0)


def test_explicit_zero_discretionary_stays_all_floor() -> None:
    inputs = _engine_inputs(annual_expenses=90_000.0)
    profile = _budget_profile(monthly_discretionary_target=0.0)
    cfg = _withdrawal_config_from_inputs(inputs, profile, WithdrawalConfig())
    assert cfg.essential_floor == pytest.approx(90_000.0)
    assert cfg.base_discretionary == pytest.approx(0.0)


def test_null_essential_derived_from_retirement_spend_target() -> None:
    inputs = _engine_inputs(annual_expenses=90_000.0)
    profile = _budget_profile(
        monthly_essential_target=None, monthly_discretionary_target=2_500.0
    )
    cfg = _withdrawal_config_from_inputs(inputs, profile, WithdrawalConfig())
    assert cfg.essential_floor == pytest.approx(60_000.0)
    assert cfg.base_discretionary == pytest.approx(30_000.0)


def test_unset_budget_uses_default_essential_share() -> None:
    inputs = _engine_inputs(annual_expenses=90_000.0)
    profile = _budget_profile(
        monthly_essential_target=None, monthly_discretionary_target=None
    )
    cfg = _withdrawal_config_from_inputs(inputs, profile, WithdrawalConfig())
    assert cfg.essential_floor == pytest.approx(54_000.0)
    assert cfg.base_discretionary == pytest.approx(36_000.0)


# ----------------------------------------------------------------------
# lever impacts — spend_less must move the resolved floor, not just
# annual_expenses (which the floor-and-upside engine never spends)
# ----------------------------------------------------------------------


def test_spend_less_lever_raises_success_probability() -> None:
    service = _make_service(_StubConn())
    inputs = _engine_inputs(
        portfolio_value=700_000.0,
        annual_expenses=60_000.0,
        withdrawal=WithdrawalConfig(
            essential_floor=40_000.0, base_discretionary=20_000.0
        ),
    )
    base = service.run_simulation(inputs, trials=500, seed=11)
    levers = service._lever_impacts(
        inputs, base.success_probability, trials=500, seed=11
    )
    by_id = {lever.id: lever for lever in levers}
    assert by_id["spend_less"].delta_success_probability > 0


# ----------------------------------------------------------------------
# bridge sleeve visibility in balance outputs
# ----------------------------------------------------------------------


def _bridge_inputs() -> RetirementInputs:
    # Retire at 60, Social Security at 67 → a seven-year bridge carve.
    return _engine_inputs(
        primary_age=60,
        retirement_age=60,
        portfolio_value=1_000_000.0,
        asset_allocation={"cash": 1.0},
        annual_expenses=60_000.0,
        income_sources=(
            RetirementIncomeSource(
                label="Social Security",
                source_type="social_security",
                start_age=67,
                monthly_amount=2500.0,
                inflation_adjusted=True,
            ),
        ),
        withdrawal=WithdrawalConfig(
            essential_floor=50_000.0, base_discretionary=10_000.0
        ),
    )


def test_monte_carlo_balances_include_bridge_sleeve() -> None:
    service = _make_service(_StubConn())
    out = service.run_simulation(_bridge_inputs(), trials=50, seed=9)
    # The six-figure bridge carve must not read as a phantom year-0 drop.
    assert out.ending_balance_paths["p50"][0] > 800_000.0


def test_drawdown_ending_balance_includes_bridge_sleeve() -> None:
    service = _make_service(_StubConn())
    rows = service._drawdown_schedule(_bridge_inputs(), buckets=())
    first = rows[0]
    assert first.balances_by_bucket.get("bridge", 0.0) > 0.0
    assert first.ending_balance == pytest.approx(
        sum(first.balances_by_bucket.values()), abs=0.05
    )


# ----------------------------------------------------------------------
# HSA modeled as non-medical: ordinary income + 20% penalty before 65
# ----------------------------------------------------------------------


def test_hsa_penalty_rate_ends_at_65_and_drains_after_roth() -> None:
    assert _early_withdrawal_penalty_rate("hsa", 64) == pytest.approx(0.20)
    assert _early_withdrawal_penalty_rate("hsa", 65) == pytest.approx(0.0)
    assert DEFAULT_DRAWDOWN_ORDER.index("roth") < DEFAULT_DRAWDOWN_ORDER.index("hsa")


def test_drawdown_taxes_and_penalizes_hsa_before_65() -> None:
    service = _make_service(_StubConn())
    inputs = _engine_inputs(
        primary_age=60,
        retirement_age=60,
        annual_expenses=60_000.0,
        income_sources=(),
        portfolio_value=0.0,
    )
    buckets = (
        RetirementAccountBucket(
            bucket_type="hsa",
            label="HSA",
            account_type="hsa",
            tax_treatment="tax_free_for_qualified_medical",
            current_value=500_000.0,
            withdrawal_priority=6,
        ),
    )
    first = service._drawdown_schedule(inputs, buckets=buckets)[0]
    hsa_draw = first.withdrawals_by_bucket["hsa"]
    assert hsa_draw > 0.0
    assert first.penalty_estimate == pytest.approx(hsa_draw * 0.20, rel=1e-3)
    # Ordinary income tax on the draw (well above the standard deduction).
    assert first.tax_estimate > 0.0


# ----------------------------------------------------------------------
# failure-age distribution (preview contract)
# ----------------------------------------------------------------------


def test_failure_age_distribution_rekeys_by_primary_age() -> None:
    sim = SimulationOutputs(
        success_probability=0.5,
        median_ending_balance=0.0,
        sequence_of_returns_risk=0.1,
        percentiles={},
        failure_year_distribution={"year_1": 3, "year_12": 7},
        ending_balance_paths={},
    )
    inputs = _engine_inputs(primary_age=50)
    assert _failure_age_distribution(sim, inputs) == {"50": 3, "61": 7}


_ = SimulationOutputs
_ = RetirementInputs
_ = datetime
_ = UTC


def test_account_buckets_exclude_education_accounts() -> None:
    service = _make_service(_StubConn())
    dashboard = SimpleNamespace(
        accounts=[
            SimpleNamespace(
                label="Taxable Brokerage",
                asset_group="taxable",
                account_type="brokerage",
                current_value=100_000.0,
                cash_balance=0.0,
            ),
            SimpleNamespace(
                label="529 - Kid",
                asset_group="education",
                account_type="529",
                current_value=35_000.0,
                cash_balance=0.0,
            ),
        ],
    )

    buckets = service._account_buckets_from_dashboard(dashboard)

    assert sum(bucket.current_value for bucket in buckets) == 100_000.0
    assert all("529" not in bucket.label for bucket in buckets)


def _college_inputs(
    college_schedule: tuple[RetirementCollegeYear, ...],
    college_529_value: float,
    *,
    primary_age: int = 60,
    retirement_age: int = 60,
) -> RetirementInputs:
    return RetirementInputs(
        household_id="hh-college",
        primary_age=primary_age,
        spouse_age=None,
        retirement_age=retirement_age,
        horizon_years=3,
        annual_expenses=60_000.0,
        annual_contribution=0.0,
        portfolio_value=1_000_000.0,
        asset_allocation={"us_equity": 1.0},
        income_sources=(),
        inflation_rate=0.0,
        college_schedule=college_schedule,
        college_529_value=college_529_value,
        college_529_real_return=0.0,
        as_of_date=date(2026, 6, 11),
    )


_COLLEGE_BUCKETS = (
    RetirementAccountBucket(
        bucket_type="taxable",
        label="Taxable",
        account_type="brokerage",
        tax_treatment="taxable_capital_gains_estimate",
        current_value=1_000_000.0,
        withdrawal_priority=2,
    ),
)


def test_drawdown_college_drains_529_sleeve_before_portfolio() -> None:
    service = _make_service(_StubConn())
    schedule = (
        RetirementCollegeYear(calendar_year=2026, real_amount=10_000.0),
        RetirementCollegeYear(calendar_year=2027, real_amount=10_000.0),
    )

    baseline = service._drawdown_schedule(
        _college_inputs((), 0.0),
        buckets=_COLLEGE_BUCKETS,
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )
    rows = service._drawdown_schedule(
        _college_inputs(schedule, 12_000.0),
        buckets=_COLLEGE_BUCKETS,
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )

    # Year 0: sleeve covers the full cost, portfolio untouched.
    assert rows[0].college_cost == 10_000.0
    assert rows[0].college_529_draw == 10_000.0
    assert rows[0].college_529_balance == 2_000.0
    assert rows[0].gross_withdrawal == baseline[0].gross_withdrawal
    # Year 1: sleeve has 2k left, 8k overflow lands on the portfolio.
    assert rows[1].college_529_draw == 2_000.0
    assert rows[1].college_529_balance == 0.0
    assert rows[1].gross_withdrawal > baseline[1].gross_withdrawal


def test_drawdown_college_overflow_before_retirement_skips_portfolio() -> None:
    service = _make_service(_StubConn())
    schedule = (RetirementCollegeYear(calendar_year=2026, real_amount=50_000.0),)

    baseline = service._drawdown_schedule(
        _college_inputs((), 0.0, primary_age=49, retirement_age=65),
        buckets=_COLLEGE_BUCKETS,
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )
    rows = service._drawdown_schedule(
        _college_inputs(schedule, 0.0, primary_age=49, retirement_age=65),
        buckets=_COLLEGE_BUCKETS,
        ordinary_tax_rate=0.22,
        capital_gains_rate=0.15,
    )

    # Working years pay college from salary: the portfolio path is identical.
    assert rows[0].college_cost == 50_000.0
    assert rows[0].college_529_draw == 0.0
    assert [row.ending_balance for row in rows] == [row.ending_balance for row in baseline]


def test_social_security_estimate_scales_down_for_early_retirees() -> None:
    career_long = _estimate_social_security_monthly(120_000.0, claim_age=62)
    stop_at_50 = _estimate_social_security_monthly(
        120_000.0, claim_age=62, stop_work_age=50
    )

    assert career_long is not None and stop_at_50 is not None
    # 28 earning years (22->50) out of the 35-year average: AIME drops to
    # 80%, so the benefit must land strictly below the keep-working number.
    assert stop_at_50 < career_long
    aime_full = 120_000.0 / 12.0
    aime_scaled = aime_full * (28.0 / 35.0)
    assert stop_at_50 / career_long == pytest.approx(
        (
            min(aime_scaled, 1_286.0) * 0.90
            + max(min(aime_scaled, 7_749.0) - 1_286.0, 0.0) * 0.32
            + max(aime_scaled - 7_749.0, 0.0) * 0.15
        )
        / (
            min(aime_full, 1_286.0) * 0.90
            + max(min(aime_full, 7_749.0) - 1_286.0, 0.0) * 0.32
            + max(aime_full - 7_749.0, 0.0) * 0.15
        )
    )


def test_social_security_estimate_ignores_stop_work_after_35_years() -> None:
    # Stopping at 60 still yields 35+ earning years, so the stop-work-aware
    # number matches the keep-working estimate.
    assert _estimate_social_security_monthly(
        100_000.0, claim_age=67, stop_work_age=60
    ) == _estimate_social_security_monthly(100_000.0, claim_age=67)


# ----------------------------------------------------------------------
# bridge growth mode (fixed vs portfolio)
# ----------------------------------------------------------------------


def _bridge_growth_inputs(growth: str) -> RetirementInputs:
    return _bridge_inputs().model_copy(
        update={
            "asset_allocation": {"us_equity": 1.0},
            "withdrawal": WithdrawalConfig(
                essential_floor=50_000.0,
                base_discretionary=10_000.0,
                bridge=WithdrawalBridgeConfig(growth=growth),
            ),
        }
    )


def test_deterministic_bridge_portfolio_growth_uses_expected_real_return() -> None:
    service = _make_service(_StubConn())
    fixed = service._drawdown_schedule(_bridge_growth_inputs("fixed"), buckets=())
    riding = service._drawdown_schedule(_bridge_growth_inputs("portfolio"), buckets=())
    # Both start from the same carve (sizing always discounts at real_return)…
    assert fixed[0].bridge_balance == pytest.approx(riding[0].bridge_balance)
    assert fixed[0].bridge_balance > 0.0
    # …but an all-equity portfolio bridge compounds faster than 1% real.
    inputs = _bridge_growth_inputs("portfolio")
    nominal = service._expected_return(inputs.asset_allocation, inputs.cash_yield)
    r_real = (1.0 + nominal) / (1.0 + inputs.inflation_rate) - 1.0
    assert r_real > 0.011
    assert riding[1].bridge_balance > fixed[1].bridge_balance


def test_monte_carlo_bridge_portfolio_growth_changes_outcomes_and_stays_seeded() -> None:
    service = _make_service(_StubConn())
    fixed = service.run_simulation(_bridge_growth_inputs("fixed"), trials=400, seed=11)
    riding = service.run_simulation(_bridge_growth_inputs("portfolio"), trials=400, seed=11)
    riding_again = service.run_simulation(
        _bridge_growth_inputs("portfolio"), trials=400, seed=11
    )
    # The sleeve now rides the sampled returns, so outcomes must move…
    assert riding.ending_balance_paths["p50"] != fixed.ending_balance_paths["p50"]
    # …deterministically for a fixed seed.
    assert riding.success_probability == riding_again.success_probability
    assert riding.ending_balance_paths["p50"] == riding_again.ending_balance_paths["p50"]
