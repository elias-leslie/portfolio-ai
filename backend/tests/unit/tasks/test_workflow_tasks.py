"""Unit tests for multi-agent workflow Celery tasks.

Tests cover:
- daily_gap_analysis_workflow (Gemini + Claude agents)
- paper_trade_validation_workflow (strategy + risk agents, backtest validation)
- research_corroboration_workflow (placeholder)
- Workflow orchestration and error handling
- Git automation integration
- Agent consensus and disagreement detection
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.workflow_tasks import (
    daily_gap_analysis_workflow,
    paper_trade_validation_workflow,
    research_corroboration_workflow,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create mock PortfolioStorage."""
    storage = MagicMock()
    storage.query.return_value.to_dicts.return_value = [{"min_date": "2024-01-01", "max_date": "2025-12-11"}]
    storage.query.return_value.is_empty.return_value = False
    return storage


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create mock WorkflowOrchestrator."""
    with patch("app.tasks.workflow_tasks.WorkflowOrchestrator") as mock_cls:
        mock_orch = MagicMock()
        mock_orch.start_workflow.return_value = {
            "status": "started",
            "workflow_id": "test-workflow-123",
        }
        mock_cls.return_value = mock_orch
        yield mock_orch


@pytest.fixture
def mock_dual_client() -> MagicMock:
    """Create mock DualProviderClient for LLM generation."""
    with patch("app.tasks.workflow_tasks.DualProviderClient") as mock_cls:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"gaps_identified": 3, "coverage_estimate": 0.65}'
        mock_client.generate.return_value = mock_response
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_git_automation() -> MagicMock:
    """Mock commit_workflow_results function."""
    with patch("app.tasks.workflow_tasks.commit_workflow_results") as mock_commit:
        mock_commit.return_value = True
        yield mock_commit


# =============================================================================
# Test Daily Gap Analysis Workflow
# =============================================================================


class TestDailyGapAnalysisWorkflow:
    """Tests for daily_gap_analysis_workflow task."""

    def test_gap_analysis_workflow_success(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
        mock_git_automation: MagicMock,
    ) -> None:
        """Test successful gap analysis workflow with both agents."""
        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            result = daily_gap_analysis_workflow()

        assert result["status"] == "completed"
        assert result["workflow_id"] == "test-workflow-123"
        assert "result" in result

        # Verify workflow started
        mock_orchestrator.start_workflow.assert_called_once()
        call_kwargs = mock_orchestrator.start_workflow.call_args[1]
        assert call_kwargs["workflow_type"] == "daily_gap_analysis"
        assert call_kwargs["agents_involved"] == ["gemini", "claude"]

        # Verify workflow status updated
        assert mock_orchestrator.update_workflow_status.call_count >= 1

        # Verify workflow completed
        mock_orchestrator.complete_workflow.assert_called_once()

        # Verify git automation called
        mock_git_automation.assert_called_once()
        git_call = mock_git_automation.call_args[1]
        assert git_call["workflow_type"] == "daily_gap_analysis"

    def test_gap_analysis_gemini_agent_execution(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
    ) -> None:
        """Test Gemini agent is called with correct prompt."""
        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            daily_gap_analysis_workflow()

        # Verify Gemini agent called
        assert mock_dual_client.generate.call_count >= 1
        first_call = mock_dual_client.generate.call_args_list[0]

        # Verify prompt contains gap analysis keywords
        prompt = first_call[1]["prompt"]
        assert "market gaps" in prompt.lower()
        assert "data gaps" in prompt.lower() or "coverage" in prompt.lower()

    def test_gap_analysis_claude_validation(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
    ) -> None:
        """Test Claude agent validates Gemini's analysis."""
        gemini_output = '{"gaps": ["gap1", "gap2"], "coverage": 0.7}'
        claude_output = '{"validated_gaps": ["gap1", "gap2"], "coverage": 0.75}'

        mock_dual_client.generate.side_effect = [
            MagicMock(content=gemini_output),
            MagicMock(content=claude_output),
        ]

        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            result = daily_gap_analysis_workflow()

        assert result["status"] == "completed"

        # Verify Claude received Gemini's output
        assert mock_dual_client.generate.call_count == 2
        claude_call = mock_dual_client.generate.call_args_list[1]
        claude_prompt = claude_call[1]["prompt"]
        assert gemini_output in claude_prompt

    def test_gap_analysis_gemini_failure_fallback(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
    ) -> None:
        """Test workflow continues if Gemini fails but Claude succeeds."""
        mock_dual_client.generate.side_effect = [
            Exception("Gemini API timeout"),
            MagicMock(content='{"analysis": "claude_only"}'),
        ]

        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            result = daily_gap_analysis_workflow()

        # Workflow should complete with Claude's output
        assert result["status"] == "completed"
        assert "claude_only" in result["result"]

        # Verify workflow completed (not failed)
        mock_orchestrator.complete_workflow.assert_called_once()

    def test_gap_analysis_both_agents_fail(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
    ) -> None:
        """Test workflow fails when both agents fail."""
        mock_dual_client.generate.side_effect = [
            RuntimeError("Gemini error"),
            ValueError("Claude error"),
        ]

        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            result = daily_gap_analysis_workflow()

        assert result["status"] == "failed"
        assert "error" in result

        # Verify workflow marked as failed
        call_args = mock_orchestrator.update_workflow_status.call_args
        assert call_args[0][0] == "test-workflow-123"
        assert call_args[1]["status"] == "failed"
        assert call_args[1]["current_step"] == "both_agents_failed"
        # Error message contains both agent errors
        assert "Gemini" in call_args[1]["error"]
        assert "Claude" in call_args[1]["error"]

    def test_gap_analysis_workflow_start_failure(
        self, mock_storage: MagicMock, mock_orchestrator: MagicMock
    ) -> None:
        """Test handles workflow start failure."""
        mock_orchestrator.start_workflow.return_value = {
            "status": "error",
            "error": "Workflow queue full",
        }

        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            result = daily_gap_analysis_workflow()

        assert result["status"] == "error"

        # Workflow should not proceed
        assert mock_orchestrator.update_workflow_status.call_count == 0
        assert mock_orchestrator.complete_workflow.call_count == 0

    def test_gap_analysis_git_automation_failure_non_blocking(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
        mock_git_automation: MagicMock,
    ) -> None:
        """Test git automation failure does not block workflow completion."""
        mock_git_automation.side_effect = OSError("Git push failed")

        with patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage):
            result = daily_gap_analysis_workflow()

        # Workflow should still complete successfully
        assert result["status"] == "completed"
        mock_orchestrator.complete_workflow.assert_called_once()


# =============================================================================
# Test Paper Trade Validation Workflow
# =============================================================================


class TestPaperTradeValidationWorkflow:
    """Tests for paper_trade_validation_workflow task."""

    @pytest.fixture
    def mock_backtest_result(self) -> dict:
        """Mock successful backtest result."""
        return {
            "status": "completed",
            "backtest_run_id": "bt-123",
            "sharpe_ratio": 1.5,
            "win_rate": 60.0,
            "max_drawdown_pct": 15.0,
            "total_return_pct": 25.0,
            "num_trades": 10,
        }

    @pytest.fixture
    def mock_agent_tools(self, mock_backtest_result: dict) -> MagicMock:
        """Mock AgentTools for backtest and paper trade execution."""
        with patch("app.tasks.workflow_tasks.AgentTools") as mock_cls:
            mock_tools = MagicMock()
            mock_tools.execute_run_backtest.return_value = mock_backtest_result
            mock_tools.execute_create_paper_trade.return_value = {
                "status": "created",
                "trade_id": "trade-123",
            }
            mock_cls.return_value = mock_tools
            yield mock_tools

    def test_paper_trade_validation_both_agents_approve(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
        mock_agent_tools: MagicMock,
        mock_git_automation: MagicMock,
    ) -> None:
        """Test paper trade approved when both agents approve."""
        # Mock agent responses: both approve
        strategy_response = '{"decision": "APPROVE", "confidence": 85, "reasoning": "Good metrics"}'
        risk_response = '{"decision": "APPROVE", "confidence": 90, "reasoning": "Risk acceptable"}'

        mock_dual_client.generate.side_effect = [
            MagicMock(content=strategy_response),
            MagicMock(content=risk_response),
        ]

        with (
            patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage),
            patch("app.tasks.workflow_tasks.PortfolioManager"),
            patch("app.tasks.workflow_tasks.NewsService"),
            patch("app.tasks.workflow_tasks.FREDSource"),
            patch("app.tasks.workflow_tasks.PriceDataFetcher"),
            patch("app.tasks.workflow_tasks.PortfolioAnalytics"),
            patch("app.strategies.storage.get_strategy_storage") as mock_strat_storage,
        ):
            mock_strat_storage.return_value.get_active_strategy.return_value = None
            result = paper_trade_validation_workflow(
                strategy_id="strat-1",
                symbol="AAPL",
                action="buy",
                thesis="Strong momentum",
            )

        assert result["status"] == "completed"
        assert result["approved"] is True
        assert result["trade_id"] == "trade-123"
        assert result["strategy_approved"] is True
        assert result["risk_approved"] is True

        # Verify paper trade created
        mock_agent_tools.execute_create_paper_trade.assert_called_once()

    def test_paper_trade_validation_agents_disagree(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
        mock_agent_tools: MagicMock,
    ) -> None:
        """Test paper trade rejected when agents disagree."""
        # Strategy approves, Risk rejects
        strategy_response = '{"decision": "APPROVE", "confidence": 70, "reasoning": "Looks good"}'
        risk_response = '{"decision": "REJECT", "confidence": 80, "reasoning": "Too risky"}'

        mock_dual_client.generate.side_effect = [
            MagicMock(content=strategy_response),
            MagicMock(content=risk_response),
        ]

        with (
            patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage),
            patch("app.tasks.workflow_tasks.PortfolioManager"),
            patch("app.tasks.workflow_tasks.NewsService"),
            patch("app.tasks.workflow_tasks.FREDSource"),
            patch("app.tasks.workflow_tasks.PriceDataFetcher"),
            patch("app.tasks.workflow_tasks.PortfolioAnalytics"),
            patch("app.strategies.storage.get_strategy_storage") as mock_strat_storage,
        ):
            mock_strat_storage.return_value.get_active_strategy.return_value = None
            result = paper_trade_validation_workflow(
                strategy_id="strat-1",
                symbol="AAPL",
                action="buy",
                thesis="Test",
            )

        # Trade should be rejected (requires both agents to approve)
        assert result["approved"] is False
        assert result["strategy_approved"] is True
        assert result["risk_approved"] is False
        assert result["trade_id"] is None

        # Verify paper trade NOT created
        mock_agent_tools.execute_create_paper_trade.assert_not_called()

    def test_paper_trade_validation_backtest_gating_fails(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_agent_tools: MagicMock,
    ) -> None:
        """Test trade rejected when backtest metrics fail gating thresholds."""
        # Mock backtest with poor metrics
        poor_backtest = {
            "status": "completed",
            "sharpe_ratio": 0.5,  # < 1.0 threshold
            "win_rate": 45.0,  # < 50% threshold
            "max_drawdown_pct": 25.0,  # > 20% threshold
            "total_return_pct": 5.0,
            "num_trades": 8,
        }
        mock_agent_tools.execute_run_backtest.return_value = poor_backtest

        with (
            patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage),
            patch("app.tasks.workflow_tasks.PortfolioManager"),
            patch("app.tasks.workflow_tasks.NewsService"),
            patch("app.tasks.workflow_tasks.FREDSource"),
            patch("app.tasks.workflow_tasks.PriceDataFetcher"),
            patch("app.tasks.workflow_tasks.PortfolioAnalytics"),
            patch("app.strategies.storage.get_strategy_storage") as mock_strat_storage,
        ):
            mock_strat_storage.return_value.get_active_strategy.return_value = None
            result = paper_trade_validation_workflow(
                strategy_id="strat-1",
                symbol="AAPL",
                action="buy",
                thesis="Test",
            )

        # Trade rejected due to gating failure
        assert result["approved"] is False
        assert result["gating_failed"] is True
        assert "gating_reason" in result
        assert "Sharpe ratio" in result["gating_reason"]

        # Workflow completes (not failed), but trade not created
        assert result["status"] == "completed"
        mock_orchestrator.complete_workflow.assert_called_once()

    def test_paper_trade_validation_backtest_execution_fails(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_agent_tools: MagicMock,
    ) -> None:
        """Test workflow fails when backtest execution fails."""
        mock_agent_tools.execute_run_backtest.return_value = {
            "status": "failed",
            "error": "Insufficient data",
        }

        with (
            patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage),
            patch("app.tasks.workflow_tasks.PortfolioManager"),
            patch("app.tasks.workflow_tasks.NewsService"),
            patch("app.tasks.workflow_tasks.FREDSource"),
            patch("app.tasks.workflow_tasks.PriceDataFetcher"),
            patch("app.tasks.workflow_tasks.PortfolioAnalytics"),
            patch("app.strategies.storage.get_strategy_storage") as mock_strat_storage,
        ):
            mock_strat_storage.return_value.get_active_strategy.return_value = None
            result = paper_trade_validation_workflow(
                strategy_id="strat-1",
                symbol="AAPL",
                action="buy",
                thesis="Test",
            )

        assert result["status"] == "failed"
        assert "Backtest execution failed" in result["error"]

        # Verify workflow marked as failed
        mock_orchestrator.update_workflow_status.assert_called_with(
            "test-workflow-123",
            status="failed",
            current_step="backtest_failed",
            error="Insufficient data",
        )

    def test_paper_trade_validation_no_historical_data(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
    ) -> None:
        """Test workflow triggers data backfill when no historical data exists."""
        # Mock empty data range
        mock_storage.query.return_value.is_empty.return_value = True
        mock_storage.query.return_value.to_dicts.return_value = []

        with (
            patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage),
            patch(
                "app.tasks.ingestion.price_ingestion.ingest_historical_ohlcv"
            ) as mock_ingest,
        ):
            mock_ingest.delay = MagicMock()
            mock_ingest.delay.return_value = None

            result = paper_trade_validation_workflow(
                strategy_id="strat-1",
                symbol="AAPL",
                action="buy",
                thesis="Test",
            )

        assert result["status"] == "pending_data"
        assert "historical data fetch" in result["message"]

        # Verify data ingestion triggered
        mock_ingest.delay.assert_called_once_with(["AAPL"], days=1300)

    def test_paper_trade_validation_agent_consensus_logging(
        self,
        mock_storage: MagicMock,
        mock_orchestrator: MagicMock,
        mock_dual_client: MagicMock,
        mock_agent_tools: MagicMock,
    ) -> None:
        """Test workflow logs agent consensus data correctly."""
        strategy_response = '{"decision": "APPROVE", "confidence": 75, "reasoning": "Good setup"}'
        risk_response = '{"decision": "APPROVE", "confidence": 85, "reasoning": "Manageable risk"}'

        mock_dual_client.generate.side_effect = [
            MagicMock(content=strategy_response),
            MagicMock(content=risk_response),
        ]

        with (
            patch("app.tasks.workflow_tasks.PortfolioStorage", return_value=mock_storage),
            patch("app.tasks.workflow_tasks.PortfolioManager"),
            patch("app.tasks.workflow_tasks.NewsService"),
            patch("app.tasks.workflow_tasks.FREDSource"),
            patch("app.tasks.workflow_tasks.PriceDataFetcher"),
            patch("app.tasks.workflow_tasks.PortfolioAnalytics"),
            patch("app.strategies.storage.get_strategy_storage") as mock_strat_storage,
        ):
            mock_strat_storage.return_value.get_active_strategy.return_value = None
            result = paper_trade_validation_workflow(
                strategy_id="strat-1",
                symbol="AAPL",
                action="buy",
                thesis="Test",
            )

        # Verify consensus data in result
        assert result["strategy_approved"] is True
        assert result["risk_approved"] is True
        assert "backtest_metrics" in result

        # Verify workflow result includes all required data
        complete_call = mock_orchestrator.complete_workflow.call_args
        # complete_workflow is called with: (workflow_id, result=dict)
        workflow_result = complete_call[1]["result"]

        assert "strategy_confidence" in workflow_result
        assert "risk_confidence" in workflow_result
        assert "weighted_score" in workflow_result
        assert "agents_disagree" in workflow_result


# =============================================================================
# Test Research Corroboration Workflow (Placeholder)
# =============================================================================


class TestResearchCorroborationWorkflow:
    """Tests for research_corroboration_workflow placeholder."""

    def test_research_corroboration_not_implemented(self) -> None:
        """Test research corroboration returns not_implemented status."""
        result = research_corroboration_workflow(
            topic="AI stocks",
            sources=["source1", "source2"],
        )

        assert result["status"] == "not_implemented"
        assert result["topic"] == "AI stocks"


# =============================================================================
# Test Helper Functions
# =============================================================================


class TestWorkflowHelpers:
    """Tests for workflow helper functions."""

    def test_get_available_data_range_with_data(self) -> None:
        """Test _get_available_data_range returns date range."""
        from app.tasks.workflow_tasks import _get_available_data_range

        mock_storage = MagicMock()
        mock_storage.query.return_value.is_empty.return_value = False
        mock_storage.query.return_value.to_dicts.return_value = [
            {"min_date": "2024-01-01", "max_date": "2025-12-11"}
        ]

        min_date, max_date = _get_available_data_range(mock_storage, "AAPL")

        assert min_date == "2024-01-01"
        assert max_date == "2025-12-11"

    def test_get_available_data_range_no_data(self) -> None:
        """Test _get_available_data_range returns None for empty results."""
        from app.tasks.workflow_tasks import _get_available_data_range

        mock_storage = MagicMock()
        mock_storage.query.return_value.is_empty.return_value = True

        min_date, max_date = _get_available_data_range(mock_storage, "UNKNOWN")

        assert min_date is None
        assert max_date is None

    def test_get_available_data_range_null_dates(self) -> None:
        """Test _get_available_data_range handles NULL date values."""
        from app.tasks.workflow_tasks import _get_available_data_range

        mock_storage = MagicMock()
        mock_storage.query.return_value.is_empty.return_value = False
        mock_storage.query.return_value.to_dicts.return_value = [
            {"min_date": None, "max_date": None}
        ]

        min_date, max_date = _get_available_data_range(mock_storage, "AAPL")

        assert min_date is None
        assert max_date is None
