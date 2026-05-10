"""Integration tests for the F5 retirement Monte Carlo router.

Drives the FastAPI app through a TestClient with the service stubbed
so the route-layer wiring (validation, projection, 404 path) can be
asserted without a Postgres fixture. The math is covered separately
by tests/services/test_retirement_planning_service.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.portfolio.contracts.retirement import (
    RetirementInputs,
    ScenarioResults,
    ScenarioSummary,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_results(scenario_id: str = "00000000-0000-0000-0000-000000000001") -> ScenarioResults:
    inputs = RetirementInputs(
        household_id="hh-test",
        primary_age=46,
        spouse_age=44,
        retirement_age=65,
        horizon_years=30,
        annual_expenses=72_000.0,
        portfolio_value=900_000.0,
        asset_allocation={"us_equity": 0.6, "bonds": 0.4},
        income_sources=(),
        inflation_rate=0.025,
        as_of_date=date(2026, 5, 9),
    )
    summary = ScenarioSummary(
        id=scenario_id,
        household_id="hh-test",
        name="Baseline",
        success_probability=0.82,
        median_ending_balance=1_500_000.0,
        sequence_of_returns_risk=0.05,
        trial_count=10_000,
        cma_source="yaml-v1",
        created_at=datetime(2026, 5, 9, 12, 0, tzinfo=UTC),
    )
    return ScenarioResults(
        summary=summary,
        inputs=inputs,
        percentiles={
            "p10": 200_000.0,
            "p25": 800_000.0,
            "p50": 1_500_000.0,
            "p75": 2_300_000.0,
            "p90": 3_500_000.0,
        },
        ending_balance_paths={
            "p50": [900_000.0 * (1.05**i) for i in range(30)],
        },
        cma_snapshot={"version": "yaml-v1"},
    )


@pytest.fixture
def stub_service(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from app.api import retirement_routes
    from app.services.retirement_planning_service import RetirementPlanningService

    state: dict[str, Any] = {"saved": [], "by_id": {}}

    def fake_build_inputs(self: RetirementPlanningService, household_id: str, **kwargs: Any) -> RetirementInputs:
        del self, kwargs
        return _make_results().inputs.model_copy(update={"household_id": household_id})

    def fake_run_simulation(self: RetirementPlanningService, inputs: RetirementInputs, *, trials: int, seed: int | None) -> Any:
        del self, inputs, trials, seed

        class _Sim:
            success_probability: ClassVar[float] = 0.82
            median_ending_balance: ClassVar[float] = 1_500_000.0
            sequence_of_returns_risk: ClassVar[float] = 0.05
            percentiles: ClassVar[dict[str, float]] = {"p50": 1_500_000.0}
            failure_year_distribution: ClassVar[dict[str, int]] = {}
            ending_balance_paths: ClassVar[dict[str, list[float]]] = {"p50": [1.0]}

        return _Sim()

    def fake_save_scenario(self: RetirementPlanningService, *, name: str, inputs: RetirementInputs, sim: Any, trials: int, cma_source: str | None = None) -> ScenarioResults:
        del self, sim, cma_source
        results = _make_results()
        results = results.model_copy(
            update={
                "summary": results.summary.model_copy(
                    update={"name": name, "trial_count": trials}
                ),
                "inputs": inputs,
            }
        )
        state["saved"].append(results)
        state["by_id"][results.summary.id] = results
        return results

    def fake_list_scenarios(self: RetirementPlanningService, household_id: str, *, limit: int) -> list[ScenarioSummary]:
        del self
        return [
            r.summary
            for r in state["saved"]
            if r.summary.household_id == household_id
        ][:limit]

    def fake_show_scenario(self: RetirementPlanningService, scenario_id: str, *, detail: bool) -> ScenarioResults | None:
        del self
        results = state["by_id"].get(scenario_id)
        if results is None:
            return None
        if not detail:
            return results.model_copy(
                update={"ending_balance_paths": None, "cma_snapshot": None}
            )
        return results

    monkeypatch.setattr(RetirementPlanningService, "build_inputs", fake_build_inputs)
    monkeypatch.setattr(RetirementPlanningService, "run_simulation", fake_run_simulation)
    monkeypatch.setattr(RetirementPlanningService, "save_scenario", fake_save_scenario)
    monkeypatch.setattr(RetirementPlanningService, "list_scenarios", fake_list_scenarios)
    monkeypatch.setattr(RetirementPlanningService, "show_scenario", fake_show_scenario)
    # Reset the lru_cache so a fresh service hits our patched methods.
    retirement_routes._service.cache_clear()
    return state


def test_post_runs_and_persists_scenario(
    client: TestClient, stub_service: dict[str, Any]
) -> None:
    response = client.post(
        "/api/retirement/scenarios",
        json={"household_id": "hh-test", "trials": 500, "seed": 7},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["household_id"] == "hh-test"
    assert body["summary"]["trial_count"] == 500
    assert body["summary"]["success_probability"] == 0.82
    assert "p50" in body["percentiles"]
    assert len(stub_service["saved"]) == 1


def test_post_rejects_excessive_trials(client: TestClient) -> None:
    response = client.post(
        "/api/retirement/scenarios",
        json={"household_id": "hh-test", "trials": 99_999_999},
    )
    assert response.status_code == 422


def test_get_list_filters_by_household(
    client: TestClient, stub_service: dict[str, Any]
) -> None:
    client.post("/api/retirement/scenarios", json={"household_id": "hh-test"})
    client.post("/api/retirement/scenarios", json={"household_id": "hh-other"})
    response = client.get(
        "/api/retirement/scenarios", params={"household_id": "hh-test"}
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert all(row["household_id"] == "hh-test" for row in rows)


def test_get_show_compact_drops_detail_fields(
    client: TestClient, stub_service: dict[str, Any]
) -> None:
    posted = client.post(
        "/api/retirement/scenarios", json={"household_id": "hh-test"}
    ).json()
    scenario_id = posted["summary"]["id"]
    response = client.get(f"/api/retirement/scenarios/{scenario_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ending_balance_paths"] is None
    assert body["cma_snapshot"] is None


def test_get_show_with_detail_keeps_paths(
    client: TestClient, stub_service: dict[str, Any]
) -> None:
    posted = client.post(
        "/api/retirement/scenarios", json={"household_id": "hh-test"}
    ).json()
    scenario_id = posted["summary"]["id"]
    response = client.get(
        f"/api/retirement/scenarios/{scenario_id}", params={"detail": "true"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ending_balance_paths"] is not None


def test_get_show_returns_404_for_missing_scenario(
    client: TestClient, stub_service: dict[str, Any]
) -> None:
    response = client.get("/api/retirement/scenarios/does-not-exist")
    assert response.status_code == 404
