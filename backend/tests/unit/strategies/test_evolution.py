"""Unit tests for Strategy Evolution Agent.

Tests cover:
1. Strategy mutation logic
2. Lineage tracking
3. Performance comparison
4. Evolution selection (MAS criteria)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.agents.strategy_evolution_agent import (
    BacktestMetrics,
    StrategyAnalysis,
    StrategyEvolutionAgent,
    StrategyMutation,
)
from app.strategies.models import StrategyDefinition


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock strategy storage."""
    storage = MagicMock()
    storage.get_strategy_by_id = Mock()
    storage.store_strategy = Mock(return_value="new-strategy-id")
    storage.archive_strategy = Mock()
    return storage


@pytest.fixture
def mock_optimizer() -> MagicMock:
    """Mock strategy optimizer."""
    return MagicMock()


@pytest.fixture
def mock_research_aggregator() -> AsyncMock:
    """Mock research aggregator."""
    from datetime import datetime

    from app.strategies.models import ResearchInsights

    aggregator = AsyncMock()
    aggregator.aggregate_research = AsyncMock(
        return_value=ResearchInsights(
            symbol="AAPL",
            as_of_date=date.today(),
            news_sentiment_trend="improving",
            news_sentiment_score=0.5,
            news_sentiment_7d_avg=0.4,
            news_sentiment_30d_avg=0.3,
            material_events=["earnings_beat"],
            news_volume=50,
            news_confidence=0.8,
            company_health="GOOD",
            fundamental_score=75,
            valuation_tier="fair",
            growth_tier="stable",
            profitability_tier="good",
            debt_tier="low",
            analyst_consensus=2.5,
            fundamental_confidence=0.9,
            trend_strength="strong_up",
            trend_duration_days=45,
            momentum_rating="steady",
            volume_profile="stable",
            rsi_zone="healthy",
            price_vs_ma={"20d": 1.05, "50d": 1.08, "200d": 1.12},
            technical_confidence=1.0,
            market_regime="bull",
            fear_greed_score=65,
            fear_greed_classification="greed",
            sector_rotation_phase="mid_cycle",
            sector="Technology",
            sector_momentum="leading",
            sector_vs_spy_30d=5.2,
            sector_rotation_signal="hold",
            overall_confidence=0.85,
            research_quality="high",
            last_updated=datetime.now(),
        )
    )
    return aggregator


@pytest.fixture
def sample_strategy() -> StrategyDefinition:
    """Sample strategy for testing."""
    return StrategyDefinition(
        id="strategy-123",
        name="AAPL_Momentum_2024Q4",
        symbol="AAPL",
        strategy_type="momentum",
        parameters={
            "weight_price_trend": 0.2,
            "weight_rsi_health": 0.15,
            "weight_momentum": 0.2,
            "weight_volume": 0.1,
            "weight_fundamentals": 0.15,
            "weight_news_sentiment": 0.1,
            "weight_sector_alignment": 0.1,
            "min_confirmations": 6,
            "min_weighted_score": 0.65,
            "stop_loss_atr_multiplier": 2.0,
            "max_holding_days": 60,
        },
        research_summary={},
        generation_reasoning="Initial strategy",
        backtest_metrics=[],
        expected_sharpe=1.5,
        expected_win_rate=Decimal("0.6"),
        expected_max_drawdown=Decimal("0.15"),
        created_by="test",
        created_at=datetime.now(),
        version=1,
        status="active",
    )


@pytest.fixture
def sample_analysis() -> StrategyAnalysis:
    """Sample strategy analysis."""
    return StrategyAnalysis(
        strategy_id="strategy-123",
        symbol="AAPL",
        days_analyzed=30,
        actual_sharpe=0.8,
        expected_sharpe=1.5,
        performance_ratio=0.533,  # 0.8 / 1.5
        trades_count=20,
        win_rate=0.5,
        avg_pnl=50.0,
        max_drawdown=0.20,
        underperforming=True,
        diagnosis="Strategy enters too early in trends",
        buy_hold_sharpe=0.7,
        beats_benchmark=True,
    )


@pytest.fixture
def sample_mutations() -> list[StrategyMutation]:
    """Sample strategy mutations."""
    return [
        StrategyMutation(
            mutation_type="threshold_change",
            parameter_changes={"min_confirmations": 7},
            reasoning="Increase confirmation threshold to reduce false entries",
            confidence=0.8,
        ),
        StrategyMutation(
            mutation_type="weight_adjustment",
            parameter_changes={
                "weight_price_trend": 0.25,
                "weight_momentum": 0.15,
            },
            reasoning="Increase weight on trend strength",
            confidence=0.75,
        ),
        StrategyMutation(
            mutation_type="risk_tightening",
            parameter_changes={"stop_loss_atr_multiplier": 1.5},
            reasoning="Tighten stop loss to reduce drawdowns",
            confidence=0.7,
        ),
    ]


class TestStrategyMutationLogic:
    """Tests for strategy mutation logic."""

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.GeminiCLIClient")
    async def test_propose_mutations_returns_valid_mutations(
        self,
        mock_client: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_analysis: StrategyAnalysis,
    ) -> None:
        """Test propose_mutations returns valid mutations from LLM."""
        # Setup
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mutations_json = json.dumps(
            [
                {
                    "mutation_type": "threshold_change",
                    "parameter_changes": {"min_confirmations": 7},
                    "reasoning": "Increase confirmation threshold",
                    "confidence": 0.8,
                },
                {
                    "mutation_type": "weight_adjustment",
                    "parameter_changes": {"weight_price_trend": 0.25},
                    "reasoning": "Increase trend weight",
                    "confidence": 0.75,
                },
            ]
        )

        mock_llm_instance = Mock()
        mock_llm_instance.generate = Mock(return_value=Mock(content=mutations_json))
        mock_client.return_value = mock_llm_instance

        # Execute
        mutations = await agent.propose_mutations(sample_strategy, sample_analysis)

        # Verify
        assert len(mutations) == 2
        assert mutations[0].mutation_type == "threshold_change"
        assert mutations[0].parameter_changes == {"min_confirmations": 7}
        assert mutations[0].confidence == 0.8
        assert mutations[1].mutation_type == "weight_adjustment"

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.GeminiCLIClient")
    async def test_propose_mutations_limits_to_five(
        self,
        mock_client: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_analysis: StrategyAnalysis,
    ) -> None:
        """Test propose_mutations limits results to 5."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        # Generate 10 mutations
        mutations_json = json.dumps(
            [
                {
                    "mutation_type": f"type_{i}",
                    "parameter_changes": {"param": i},
                    "reasoning": f"Reason {i}",
                    "confidence": 0.7,
                }
                for i in range(10)
            ]
        )

        mock_llm_instance = Mock()
        mock_llm_instance.generate = Mock(return_value=Mock(content=mutations_json))
        mock_client.return_value = mock_llm_instance

        # Execute
        mutations = await agent.propose_mutations(sample_strategy, sample_analysis)

        # Verify - should be limited to 5
        assert len(mutations) == 5

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.GeminiCLIClient")
    async def test_propose_mutations_handles_invalid_json(
        self,
        mock_client: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_analysis: StrategyAnalysis,
    ) -> None:
        """Test propose_mutations handles invalid JSON gracefully."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_llm_instance = Mock()
        mock_llm_instance.generate = Mock(return_value=Mock(content="Invalid JSON {"))
        mock_client.return_value = mock_llm_instance

        # Execute
        mutations = await agent.propose_mutations(sample_strategy, sample_analysis)

        # Verify - should return empty list on error
        assert mutations == []


class TestPerformanceComparison:
    """Tests for performance comparison and analysis."""

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_analyze_strategy_performance_calculates_metrics(
        self,
        mock_conn_manager: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
    ) -> None:
        """Test analyze_strategy_performance calculates all metrics."""
        # Setup
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock database query results
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(
                fetchone=Mock(
                    return_value=(
                        20,  # trades
                        0.6,  # win_rate
                        50.0,  # avg_pnl
                        0.8,  # actual_sharpe
                        0.15,  # max_drawdown
                    )
                )
            )
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Mock _calculate_buy_hold_sharpe and LLM diagnosis
        with (
            patch.object(agent, "_calculate_buy_hold_sharpe", return_value=0.7),
            patch.object(
                agent,
                "_llm_diagnose_performance",
                return_value="Strategy enters too early",
            ),
        ):
            # Execute
            analysis = await agent.analyze_strategy_performance("strategy-123", days=30)

        # Verify
        assert analysis.strategy_id == "strategy-123"
        assert analysis.symbol == "AAPL"
        assert analysis.days_analyzed == 30
        assert analysis.actual_sharpe == 0.8
        assert analysis.expected_sharpe == 1.5
        assert analysis.performance_ratio == pytest.approx(0.533, rel=0.01)
        assert analysis.trades_count == 20
        assert analysis.win_rate == 0.6
        assert analysis.avg_pnl == 50.0
        assert analysis.max_drawdown == 0.15
        assert analysis.underperforming is True  # <90% of expected
        assert analysis.buy_hold_sharpe == 0.7
        assert analysis.beats_benchmark is True

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_analyze_strategy_performance_raises_on_no_data(
        self,
        mock_conn_manager: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
    ) -> None:
        """Test analyze_strategy_performance raises on no performance data."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock empty result
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(fetchone=Mock(return_value=(0, None, None, None, None)))
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Execute & verify
        with pytest.raises(ValueError, match="No performance data"):
            await agent.analyze_strategy_performance("strategy-123", days=30)

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_calculate_buy_hold_sharpe(
        self,
        mock_conn_manager: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
    ) -> None:
        """Test _calculate_buy_hold_sharpe calculation."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage

        # Mock price data (simple uptrend)
        prices = [(100.0,), (101.0,), (102.0,), (103.0,), (104.0,)]
        mock_conn = Mock()
        mock_conn.execute = Mock(return_value=Mock(fetchall=Mock(return_value=prices)))
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Execute
        sharpe = await agent._calculate_buy_hold_sharpe("AAPL", 30)

        # Verify - should be positive for uptrend
        assert sharpe > 0


class TestEvolutionSelection:
    """Tests for evolution selection and MAS (Minimum Acceptable Score) criteria."""

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.run_walk_forward_validation")
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_evolve_strategy_selects_best_mutation(
        self,
        mock_conn_manager: Mock,
        mock_walk_forward: AsyncMock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_mutations: list[StrategyMutation],
    ) -> None:
        """Test evolve_strategy selects mutation with highest Sharpe."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock performance data (underperforming)
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(
                fetchone=Mock(
                    return_value=(
                        20,  # trades
                        0.5,  # win_rate
                        30.0,  # avg_pnl
                        0.8,  # actual_sharpe
                        0.20,  # max_drawdown
                    )
                )
            )
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Mock walk-forward results (increasing Sharpe for each mutation)
        mock_walk_forward.side_effect = [
            BacktestMetrics(
                sharpe_ratio=1.2, win_rate=0.55, max_drawdown=0.18, total_return=0.12, num_trades=25
            ),
            BacktestMetrics(
                sharpe_ratio=1.5, win_rate=0.60, max_drawdown=0.15, total_return=0.15, num_trades=22
            ),  # Best
            BacktestMetrics(
                sharpe_ratio=1.3, win_rate=0.58, max_drawdown=0.16, total_return=0.13, num_trades=24
            ),
        ]

        # Mock methods
        with (
            patch.object(agent, "_calculate_buy_hold_sharpe", return_value=0.7),
            patch.object(agent, "_llm_diagnose_performance", return_value="Underperforming"),
            patch.object(agent, "propose_mutations", return_value=sample_mutations),
            patch.object(agent, "_save_lineage"),
        ):
            # Execute
            result = await agent.evolve_strategy("strategy-123")

        # Verify - should select mutation with Sharpe=1.5
        assert result.success is True
        assert result.child_sharpe == 1.5
        assert result.best_mutation == sample_mutations[1]
        assert result.mutations_tested == 3

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.run_walk_forward_validation")
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_evolve_strategy_rejects_below_mas_threshold(
        self,
        mock_conn_manager: Mock,
        mock_walk_forward: AsyncMock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_mutations: list[StrategyMutation],
    ) -> None:
        """Test evolve_strategy rejects mutations below MAS threshold."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock performance data
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(
                fetchone=Mock(
                    return_value=(
                        20,  # trades
                        0.5,  # win_rate
                        30.0,  # avg_pnl
                        0.8,  # actual_sharpe
                        0.20,  # max_drawdown
                    )
                )
            )
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Mock walk-forward with poor results (all below MAS)
        # MAS = max(1.5 * 0.9, 0.7) = 1.35
        mock_walk_forward.side_effect = [
            BacktestMetrics(sharpe_ratio=1.0, win_rate=0.5, max_drawdown=0.2, total_return=0.1, num_trades=20),
            BacktestMetrics(sharpe_ratio=1.1, win_rate=0.52, max_drawdown=0.19, total_return=0.11, num_trades=21),
            BacktestMetrics(sharpe_ratio=1.2, win_rate=0.54, max_drawdown=0.18, total_return=0.12, num_trades=22),
        ]

        with (
            patch.object(agent, "_calculate_buy_hold_sharpe", return_value=0.7),
            patch.object(agent, "_llm_diagnose_performance", return_value="Underperforming"),
            patch.object(agent, "propose_mutations", return_value=sample_mutations),
        ):
            # Execute
            result = await agent.evolve_strategy("strategy-123")

        # Verify - should fail (best Sharpe 1.2 < MAS 1.35)
        assert result.success is False
        assert result.child_sharpe == 1.2
        assert "below MAS threshold" in result.message

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_evolve_strategy_skips_non_underperforming(
        self,
        mock_conn_manager: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
    ) -> None:
        """Test evolve_strategy skips strategies that are not underperforming."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock performance data (performing well)
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(
                fetchone=Mock(
                    return_value=(
                        20,  # trades
                        0.65,  # win_rate
                        80.0,  # avg_pnl
                        1.4,  # actual_sharpe (93% of expected 1.5)
                        0.12,  # max_drawdown
                    )
                )
            )
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        with (
            patch.object(agent, "_calculate_buy_hold_sharpe", return_value=0.7),
            patch.object(agent, "_llm_diagnose_performance", return_value="Performing well"),
        ):
            # Execute
            result = await agent.evolve_strategy("strategy-123")

        # Verify - should skip evolution
        assert result.success is False
        assert result.mutations_tested == 0
        assert "not underperforming" in result.message


class TestLineageTracking:
    """Tests for strategy lineage tracking."""

    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    def test_save_lineage_records_parent_child_relationship(
        self,
        mock_conn_manager: Mock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
    ) -> None:
        """Test _save_lineage records parent-child relationship."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage

        mock_conn = Mock()
        mock_conn.execute = Mock()
        mock_conn.commit = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Execute
        agent._save_lineage(
            child_strategy_id="child-123",
            parent_strategy_id="parent-456",
            changes_description="Increased confirmation threshold",
            evolution_reason="underperforming",
            metrics_before={"sharpe": 0.8, "win_rate": 0.5},
            metrics_after={"sharpe": 1.5, "win_rate": 0.6},
        )

        # Verify
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO strategy_lineage" in call_args[0][0]
        assert call_args[0][1][0] == "child-123"
        assert call_args[0][1][1] == "parent-456"
        assert call_args[0][1][2] == "Increased confirmation threshold"
        assert call_args[0][1][3] == "underperforming"

        # Verify metrics are JSON serialized
        metrics_before_json = call_args[0][1][4]
        metrics_after_json = call_args[0][1][5]
        assert json.loads(metrics_before_json) == {"sharpe": 0.8, "win_rate": 0.5}
        assert json.loads(metrics_after_json) == {"sharpe": 1.5, "win_rate": 0.6}

        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.run_walk_forward_validation")
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_evolve_strategy_saves_lineage_on_success(
        self,
        mock_conn_manager: Mock,
        mock_walk_forward: AsyncMock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_mutations: list[StrategyMutation],
    ) -> None:
        """Test evolve_strategy saves lineage on successful evolution."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock performance data
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(
                fetchone=Mock(
                    return_value=(20, 0.5, 30.0, 0.8, 0.20)
                )
            )
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Mock successful mutation
        mock_walk_forward.return_value = BacktestMetrics(
            sharpe_ratio=1.5, win_rate=0.6, max_drawdown=0.15, total_return=0.15, num_trades=22
        )

        with (
            patch.object(agent, "_calculate_buy_hold_sharpe", return_value=0.7),
            patch.object(agent, "_llm_diagnose_performance", return_value="Underperforming"),
            patch.object(agent, "propose_mutations", return_value=[sample_mutations[0]]),
            patch.object(agent, "_save_lineage") as mock_save_lineage,
        ):
            # Execute
            result = await agent.evolve_strategy("strategy-123")

        # Verify lineage was saved
        assert result.success is True
        mock_save_lineage.assert_called_once()
        call_args = mock_save_lineage.call_args[1]
        assert call_args["child_strategy_id"] == "new-strategy-id"
        assert call_args["parent_strategy_id"] == "strategy-123"
        assert "metrics_before" in call_args
        assert "metrics_after" in call_args
        assert call_args["metrics_before"]["sharpe"] == 0.8
        assert call_args["metrics_after"]["sharpe"] == 1.5

    @pytest.mark.asyncio
    @patch("app.agents.strategy_evolution_agent.run_walk_forward_validation")
    @patch("app.agents.strategy_evolution_agent.get_connection_manager")
    async def test_evolve_strategy_archives_parent_on_success(
        self,
        mock_conn_manager: Mock,
        mock_walk_forward: AsyncMock,
        mock_storage: MagicMock,
        mock_optimizer: MagicMock,
        mock_research_aggregator: AsyncMock,
        sample_strategy: StrategyDefinition,
        sample_mutations: list[StrategyMutation],
    ) -> None:
        """Test evolve_strategy archives parent strategy on successful evolution."""
        agent = StrategyEvolutionAgent()
        agent.strategy_storage = mock_storage
        agent.optimizer = mock_optimizer
        agent.research_aggregator = mock_research_aggregator

        mock_storage.get_strategy_by_id.return_value = sample_strategy

        # Mock performance data
        mock_conn = Mock()
        mock_conn.execute = Mock(
            return_value=Mock(fetchone=Mock(return_value=(20, 0.5, 30.0, 0.8, 0.20)))
        )
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn_manager.return_value.connection.return_value = mock_conn

        # Mock successful mutation
        mock_walk_forward.return_value = BacktestMetrics(
            sharpe_ratio=1.5, win_rate=0.6, max_drawdown=0.15, total_return=0.15, num_trades=22
        )

        with (
            patch.object(agent, "_calculate_buy_hold_sharpe", return_value=0.7),
            patch.object(agent, "_llm_diagnose_performance", return_value="Underperforming"),
            patch.object(agent, "propose_mutations", return_value=[sample_mutations[0]]),
            patch.object(agent, "_save_lineage"),
        ):
            # Execute
            result = await agent.evolve_strategy("strategy-123")

        # Verify parent was archived
        assert result.success is True
        mock_storage.archive_strategy.assert_called_once()
        # Check the call arguments - access via [0] for positional, [1] for keyword
        call = mock_storage.archive_strategy.call_args_list[0]
        # Strategy ID is first positional arg (strategy_id)
        strategy_id = call[0][0] if call[0] else call[1].get("strategy_id")
        # Reason is second positional arg (reason)
        reason = call[0][1] if len(call[0]) > 1 else call[1].get("reason")

        assert strategy_id == "strategy-123"
        assert "Superseded by evolved version" in reason
