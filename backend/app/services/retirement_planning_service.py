"""Retirement Monte Carlo planning service (F5 single source of truth).

Reads household + portfolio state, runs the simulation engine in
``_retirement_simulation.py``, and persists ``ScenarioSummary`` +
``ScenarioResults`` rows in ``retirement_scenarios``. The router and
``st portfolio retirement-plan`` CLI are thin shims; no analytics live
outside this module.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import yaml

from app.logging_config import get_logger
from app.portfolio.contracts.retirement import (
    RetirementIncomeSource,
    RetirementInputs,
    ScenarioResults,
    ScenarioSummary,
)
from app.services._retirement_simulation import (
    SimulationOutputs,
    income_streams_from_inputs,
    run_monte_carlo,
)

logger = get_logger(__name__)

DEFAULT_TRIALS = 10_000
MAX_TRIALS = 50_000
DEFAULT_HORIZON_YEARS = 30
DEFAULT_RETIREMENT_AGE = 65
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
CMA_PATH = Path(__file__).parent / "retirement_cma.yaml"


def load_cma(path: Path | None = None) -> dict[str, Any]:
    """Load the long-term return estimates YAML.

    Module-level function so the simulation engine and tests can drive
    it without a service instance.
    """
    target = path or CMA_PATH
    with target.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class RetirementPlanningService:
    """High-level F5 surface used by the router, CLI, and Jenny.

    Storage is the only required dependency at the constructor; the
    household + portfolio readers are imported lazily so test seams
    remain straightforward (``patch.object`` on the storage cursor).
    """

    def __init__(self, storage: Any) -> None:
        self.storage = storage
        self._cma = load_cma()

    # ------------------------------------------------------------------
    # public surface
    # ------------------------------------------------------------------

    def build_inputs(
        self,
        household_id: str,
        *,
        annual_expenses: float | None = None,
        retirement_age: int | None = None,
        horizon_years: int | None = None,
        as_of_date: date | None = None,
    ) -> RetirementInputs:
        """Pull inputs from household_planning + portfolio totals.

        ``annual_expenses`` / ``retirement_age`` / ``horizon_years``
        are caller-overridable so the CLI and Jenny can run
        what-if scenarios without first persisting different
        household state.
        """
        anchor = as_of_date or date.today()
        members = self._load_members()
        primary, spouse = _split_members(members, anchor.year)
        income_sources = self._load_retirement_income_sources()
        if annual_expenses is None:
            annual_expenses = self._infer_annual_expenses(default_when_missing=72_000.0)
        portfolio_value, allocation = self._portfolio_snapshot()

        return RetirementInputs(
            household_id=household_id,
            primary_age=primary,
            spouse_age=spouse,
            retirement_age=retirement_age or DEFAULT_RETIREMENT_AGE,
            horizon_years=horizon_years or DEFAULT_HORIZON_YEARS,
            annual_expenses=annual_expenses,
            portfolio_value=portfolio_value,
            asset_allocation=allocation,
            income_sources=income_sources,
            inflation_rate=float(self._cma.get("inflation_rate", 0.025)),
            as_of_date=anchor,
        )

    def run_simulation(
        self,
        inputs: RetirementInputs,
        *,
        trials: int = DEFAULT_TRIALS,
        seed: int | None = None,
    ) -> SimulationOutputs:
        """Run the Monte Carlo without persisting; pure compute."""
        trials = max(1, min(trials, MAX_TRIALS))
        return run_monte_carlo(
            portfolio_value=inputs.portfolio_value,
            asset_allocation=inputs.asset_allocation,
            annual_expenses=inputs.annual_expenses,
            inflation_rate=inputs.inflation_rate,
            horizon_years=inputs.horizon_years,
            primary_age=inputs.primary_age,
            retirement_age=inputs.retirement_age,
            income_sources=income_streams_from_inputs(list(inputs.income_sources)),
            cma=self._cma,
            trials=trials,
            seed=seed,
        )

    def save_scenario(
        self,
        *,
        name: str,
        inputs: RetirementInputs,
        sim: SimulationOutputs,
        trials: int,
        cma_source: str | None = None,
    ) -> ScenarioResults:
        """Persist a scenario row and return the full result contract."""
        scenario_id = str(uuid.uuid4())
        cma_label = cma_source or str(self._cma.get("version") or "yaml-v1")
        created_at = datetime.now(UTC)
        summary = ScenarioSummary(
            id=scenario_id,
            household_id=inputs.household_id,
            name=name,
            success_probability=sim.success_probability,
            median_ending_balance=sim.median_ending_balance,
            sequence_of_returns_risk=sim.sequence_of_returns_risk,
            trial_count=trials,
            cma_source=cma_label,
            created_at=created_at,
        )
        results = ScenarioResults(
            summary=summary,
            inputs=inputs,
            percentiles=sim.percentiles,
            failure_year_distribution=sim.failure_year_distribution,
            ending_balance_paths=sim.ending_balance_paths,
            cma_snapshot=self._cma,
        )

        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO retirement_scenarios
                    (id, household_id, name, inputs, results,
                     cma_source, trial_count, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    scenario_id,
                    inputs.household_id,
                    name,
                    json.dumps(inputs.model_dump(mode="json")),
                    json.dumps(results.model_dump(mode="json")),
                    cma_label,
                    trials,
                    created_at,
                ],
            )
            conn.commit()
        return results

    def list_scenarios(
        self,
        household_id: str,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[ScenarioSummary]:
        limit = max(1, min(limit, MAX_LIST_LIMIT))
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, household_id, name, results, cma_source,
                       trial_count, created_at
                FROM retirement_scenarios
                WHERE household_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [household_id, limit],
            ).fetchall()
        out: list[ScenarioSummary] = []
        for row in rows:
            results_payload = _coerce_json(row[3]) or {}
            summary_payload = results_payload.get("summary") or {}
            out.append(
                ScenarioSummary.model_validate(
                    {
                        **summary_payload,
                        "id": str(row[0]),
                        "household_id": row[1],
                        "name": row[2],
                        "trial_count": int(row[5]),
                        "cma_source": row[4],
                        "created_at": row[6],
                    }
                )
            )
        return out

    def show_scenario(
        self,
        scenario_id: str,
        *,
        detail: bool = False,
    ) -> ScenarioResults | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT id, household_id, name, results, cma_source, trial_count, created_at"
                " FROM retirement_scenarios WHERE id = %s",
                [scenario_id],
            ).fetchone()
        if row is None:
            return None
        results_payload = _coerce_json(row[3]) or {}
        results = ScenarioResults.model_validate(results_payload)
        if not detail:
            return results.model_copy(
                update={"ending_balance_paths": None, "cma_snapshot": None}
            )
        return results

    def compare_scenarios(self, scenario_ids: list[str]) -> list[ScenarioSummary]:
        if not scenario_ids:
            return []
        with self.storage.connection() as conn:
            placeholders = ",".join(["%s"] * len(scenario_ids))
            rows = conn.execute(
                f"""
                SELECT id, household_id, name, results, cma_source,
                       trial_count, created_at
                FROM retirement_scenarios
                WHERE id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                list(scenario_ids),
            ).fetchall()
        ordered: list[ScenarioSummary] = []
        for row in rows:
            results_payload = _coerce_json(row[3]) or {}
            summary_payload = results_payload.get("summary") or {}
            ordered.append(
                ScenarioSummary.model_validate(
                    {
                        **summary_payload,
                        "id": str(row[0]),
                        "household_id": row[1],
                        "name": row[2],
                        "trial_count": int(row[5]),
                        "cma_source": row[4],
                        "created_at": row[6],
                    }
                )
            )
        return ordered

    # ------------------------------------------------------------------
    # internal readers
    # ------------------------------------------------------------------

    def _load_members(self) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT display_name, role, birth_year, is_dependent"
                " FROM household_members"
                " ORDER BY is_dependent ASC, role ASC"
            ).fetchall()
        return [
            {
                "display_name": row[0],
                "role": row[1],
                "birth_year": row[2],
                "is_dependent": bool(row[3]) if row[3] is not None else False,
            }
            for row in rows
        ]

    def _load_retirement_income_sources(self) -> tuple[RetirementIncomeSource, ...]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT label, source_type, owner_name, start_age, monthly_amount,"
                "       inflation_adjusted, survivor_benefit"
                " FROM household_retirement_income_sources"
                " ORDER BY start_age ASC"
            ).fetchall()
        sources: list[RetirementIncomeSource] = []
        for row in rows:
            start_age = int(row[3] or DEFAULT_RETIREMENT_AGE)
            monthly = float(row[4] or 0.0)
            sources.append(
                RetirementIncomeSource(
                    label=row[0] or "",
                    source_type=row[1],
                    owner_name=row[2],
                    start_age=start_age,
                    monthly_amount=monthly,
                    inflation_adjusted=bool(row[5]) if row[5] is not None else False,
                    survivor_benefit=float(row[6]) if row[6] is not None else None,
                )
            )
        return tuple(sources)

    def _portfolio_snapshot(self) -> tuple[float, dict[str, float]]:
        """Build (total_value, asset_class_weights) from current portfolio.

        Reuses :class:`AssetClassifier` so the weights are aligned with
        the F3 drift report's bucketing — runs against the same set of
        positions, same fund-lookthrough rules.
        """
        ac_mod = import_module("app.portfolio.asset_classification")
        price_mod = import_module("app.portfolio.price_fetcher")
        classifier = ac_mod.AssetClassifier(self.storage)
        price_fetcher = price_mod.PriceDataFetcher(self.storage)
        holdings = self._holdings(price_fetcher)
        if not holdings:
            return 0.0, {}
        bucketed = classifier.classify_value(
            ac_mod.HoldingValue(symbol=h["symbol"], value=h["current_value"])
            for h in holdings
        )
        total = float(bucketed.total_value or 0.0)
        if total <= 0:
            return 0.0, {}
        weights: dict[str, float] = {}
        for klass, value in bucketed.by_class.items():
            if klass == "unclassified":
                continue
            value_f = float(value or 0.0)
            if value_f <= 0:
                continue
            weights[klass] = round(value_f / total, 6)
        return round(total, 2), weights

    def _holdings(self, price_fetcher: Any) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT symbol, shares FROM portfolio_positions"
                " WHERE position_type = 'long' AND shares > 0"
            ).fetchall()
        if not rows:
            return []
        symbols = sorted({str(row[0]).upper() for row in rows})
        prices = price_fetcher.fetch_cached_price_data(symbols)
        out: list[dict[str, Any]] = []
        for row in rows:
            symbol = str(row[0]).upper()
            shares = float(row[1] or 0.0)
            info = prices.get(symbol)
            if info is None or getattr(info, "error", None):
                continue
            price = float(getattr(info, "price", 0.0) or 0.0)
            if price <= 0 or shares <= 0:
                continue
            out.append({"symbol": symbol, "current_value": shares * price})
        return out

    def _infer_annual_expenses(self, *, default_when_missing: float) -> float:
        """Sum monthly expenses across the household_planning sections.

        Falls back to ``default_when_missing`` when the user hasn't
        captured detailed expense rows yet — the simulation still runs,
        the row just gets flagged in the input snapshot for the UI.
        """
        with self.storage.connection() as conn:
            sums = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(monthly_payment,0)), 0)"
                " FROM household_housing_costs"
            ).fetchone()
            monthly_housing = float(sums[0] or 0.0) if sums else 0.0
            sums = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(monthly_payment,0)), 0)"
                " FROM household_debt_obligations"
            ).fetchone()
            monthly_debt = float(sums[0] or 0.0) if sums else 0.0
            sums = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(premium_monthly,0)), 0)"
                " FROM household_insurance_policies"
            ).fetchone()
            monthly_insurance = float(sums[0] or 0.0) if sums else 0.0
        annual = (monthly_housing + monthly_debt + monthly_insurance) * 12
        if annual <= 0:
            return float(default_when_missing)
        # Add a 50% wedge for everyday spending (food, transport, etc.)
        # so the projection isn't dominated solely by fixed costs.
        return round(annual * 1.5, 2)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _split_members(
    members: list[dict[str, Any]], current_year: int
) -> tuple[int, int | None]:
    primary_age: int | None = None
    spouse_age: int | None = None
    for row in members:
        if row.get("is_dependent"):
            continue
        birth_year = row.get("birth_year")
        if birth_year is None:
            continue
        age = max(0, current_year - int(birth_year))
        role = (row.get("role") or "").strip().lower()
        if primary_age is None and role in {"primary", "self", "owner"}:
            primary_age = age
        elif spouse_age is None and role in {"spouse", "partner"}:
            spouse_age = age
        elif primary_age is None:
            primary_age = age
    return primary_age if primary_age is not None else 50, spouse_age


def _coerce_json(value: Any) -> dict[str, Any] | None:
    if value is None or isinstance(value, dict):
        return value
    raw: str | None = None
    if isinstance(value, str):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        try:
            raw = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
