"""Tests for stress testing framework (GAP-027)."""

from __future__ import annotations

import pytest

from app.analytics.stress_testing import (
    SCENARIO_DEFINITIONS,
    ScenarioShocks,
    StressScenario,
    calculate_resilience_score,
    get_stress_test_summary,
    run_all_stress_tests,
    run_stress_test,
)


@pytest.fixture
def sample_portfolio() -> list[dict[str, object]]:
    """Sample portfolio for testing."""
    return [
        {"ticker": "AAPL", "sector": "Technology", "current_value": 10000.0},
        {"ticker": "JPM", "sector": "Financial Services", "current_value": 8000.0},
        {"ticker": "XOM", "sector": "Energy", "current_value": 5000.0},
        {"ticker": "JNJ", "sector": "Healthcare", "current_value": 7000.0},
        {"ticker": "PG", "sector": "Consumer Defensive", "current_value": 5000.0},
    ]


@pytest.fixture
def tech_heavy_portfolio() -> list[dict[str, object]]:
    """Tech-concentrated portfolio."""
    return [
        {"ticker": "AAPL", "sector": "Technology", "current_value": 20000.0},
        {"ticker": "MSFT", "sector": "Technology", "current_value": 15000.0},
        {"ticker": "GOOGL", "sector": "Communication Services", "current_value": 10000.0},
        {"ticker": "META", "sector": "Communication Services", "current_value": 5000.0},
    ]


class TestScenarioDefinitions:
    """Tests for scenario definitions."""

    def test_all_scenarios_defined(self) -> None:
        """All scenarios should have definitions."""
        for scenario in StressScenario:
            assert scenario in SCENARIO_DEFINITIONS

    def test_scenario_has_required_fields(self) -> None:
        """Each scenario should have required fields."""
        for scenario, shocks in SCENARIO_DEFINITIONS.items():
            assert isinstance(shocks.name, str)
            assert isinstance(shocks.description, str)
            assert isinstance(shocks.market_shock, float)
            assert isinstance(shocks.vix_level, float)
            assert isinstance(shocks.duration_days, int)

    def test_financial_crisis_severity(self) -> None:
        """2008 crisis should be severe."""
        shocks = SCENARIO_DEFINITIONS[StressScenario.FINANCIAL_CRISIS_2008]
        assert shocks.market_shock <= -0.50  # At least 50% decline
        assert shocks.vix_level >= 60  # High VIX
        assert "Financial Services" in shocks.sector_shocks

    def test_covid_crash_is_fast(self) -> None:
        """COVID crash should be short duration."""
        shocks = SCENARIO_DEFINITIONS[StressScenario.COVID_CRASH_2020]
        assert shocks.duration_days <= 60
        assert shocks.vix_level >= 70


class TestRunStressTest:
    """Tests for run_stress_test function."""

    def test_applies_market_shock(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should apply market shock to positions."""
        result = run_stress_test(sample_portfolio, StressScenario.FLASH_CRASH_2010)

        assert result.portfolio_loss_pct < 0  # Should be negative (loss)
        assert result.total_stressed_value < result.total_current_value

    def test_applies_sector_shocks(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should apply sector-specific shocks when defined."""
        result = run_stress_test(sample_portfolio, StressScenario.FINANCIAL_CRISIS_2008)

        # Find financial position
        fin_result = next(r for r in result.position_results if r.sector == "Financial Services")
        tech_result = next(r for r in result.position_results if r.sector == "Technology")

        # Financial should be hit harder than tech in 2008
        assert abs(fin_result.loss_pct) > abs(tech_result.loss_pct)

    def test_tech_heavy_hit_hard_in_dotcom(self, tech_heavy_portfolio: list[dict[str, object]]) -> None:
        """Tech-heavy portfolio should be devastated in dot-com bust."""
        result = run_stress_test(tech_heavy_portfolio, StressScenario.DOT_COM_BUST_2000)

        # Should lose more than market
        assert abs(result.portfolio_loss_pct) > abs(SCENARIO_DEFINITIONS[StressScenario.DOT_COM_BUST_2000].market_shock)

    def test_returns_worst_positions(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should identify worst-hit positions."""
        result = run_stress_test(sample_portfolio, StressScenario.FINANCIAL_CRISIS_2008)

        assert len(result.worst_positions) <= 5
        # Worst positions should be sorted by loss (most negative first)
        for i in range(len(result.worst_positions) - 1):
            assert result.worst_positions[i].loss_pct <= result.worst_positions[i + 1].loss_pct

    def test_includes_scenario_metadata(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should include scenario information in result."""
        result = run_stress_test(sample_portfolio, StressScenario.COVID_CRASH_2020)

        assert result.scenario == StressScenario.COVID_CRASH_2020
        assert "COVID" in result.scenario_name
        assert result.vix_level == 82.0

    def test_empty_portfolio(self) -> None:
        """Should handle empty portfolio."""
        result = run_stress_test([], StressScenario.FLASH_CRASH_2010)

        assert result.total_current_value == 0
        assert result.portfolio_loss_pct == 0
        assert len(result.position_results) == 0


class TestCalculateResilienceScore:
    """Tests for calculate_resilience_score function."""

    def test_outperforming_market_is_resilient(self) -> None:
        """Portfolio losing less than market should score high."""
        shocks = ScenarioShocks(
            name="Test", description="Test", market_shock=-0.30, vix_level=40, duration_days=30
        )
        score = calculate_resilience_score(-0.15, shocks)  # Half the loss
        assert score == 100

    def test_matching_market_is_moderate(self) -> None:
        """Portfolio matching market should score 50."""
        shocks = ScenarioShocks(
            name="Test", description="Test", market_shock=-0.30, vix_level=40, duration_days=30
        )
        score = calculate_resilience_score(-0.30, shocks)
        assert score == 50

    def test_underperforming_market_is_vulnerable(self) -> None:
        """Portfolio losing more than market should score low."""
        shocks = ScenarioShocks(
            name="Test", description="Test", market_shock=-0.30, vix_level=40, duration_days=30
        )
        score = calculate_resilience_score(-0.60, shocks)  # Double the loss
        assert score == 0

    def test_score_bounded_0_100(self) -> None:
        """Score should always be 0-100."""
        shocks = ScenarioShocks(
            name="Test", description="Test", market_shock=-0.10, vix_level=30, duration_days=30
        )
        # Extreme underperformance
        score = calculate_resilience_score(-0.90, shocks)
        assert 0 <= score <= 100


class TestRunAllStressTests:
    """Tests for run_all_stress_tests function."""

    def test_runs_all_scenarios(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should run all defined scenarios."""
        results = run_all_stress_tests(sample_portfolio)

        assert len(results) == len(StressScenario)
        scenarios_run = {r.scenario for r in results}
        assert scenarios_run == set(StressScenario)

    def test_all_results_have_resilience(self, sample_portfolio: list[dict[str, object]]) -> None:
        """All results should have resilience scores."""
        results = run_all_stress_tests(sample_portfolio)

        for result in results:
            assert 0 <= result.resilience_score <= 100


class TestGetStressTestSummary:
    """Tests for get_stress_test_summary function."""

    def test_identifies_worst_case(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should identify worst-case scenario."""
        results = run_all_stress_tests(sample_portfolio)
        summary = get_stress_test_summary(results)

        assert "worst_case_scenario" in summary
        assert "worst_case_loss_pct" in summary
        assert summary["worst_case_loss_pct"] < 0

    def test_calculates_averages(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should calculate average metrics."""
        results = run_all_stress_tests(sample_portfolio)
        summary = get_stress_test_summary(results)

        assert "average_loss_pct" in summary
        assert "average_resilience_score" in summary
        assert summary["total_scenarios"] == len(results)

    def test_assigns_rating(self, sample_portfolio: list[dict[str, object]]) -> None:
        """Should assign overall rating."""
        results = run_all_stress_tests(sample_portfolio)
        summary = get_stress_test_summary(results)

        assert summary["overall_rating"] in ("RESILIENT", "MODERATE", "VULNERABLE")

    def test_empty_results(self) -> None:
        """Should handle empty results."""
        summary = get_stress_test_summary([])
        assert "error" in summary
