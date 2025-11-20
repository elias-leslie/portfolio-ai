"""Integration tests for complete strategy generation pipeline.

Tests the full workflow from research aggregation through to strategy storage.
Uses real database and components (not fully mocked).
"""

import uuid
from datetime import date

import pytest

from app.strategies.models import ResearchInsights, StrategyGenerationResult
from app.strategies.optimizer import StrategyOptimizer
from app.strategies.research_aggregator import ResearchAggregationService
from app.strategies.storage import StrategyStorage
from app.strategies.strategy_generator import StrategyGeneratorAgent


class TestStrategyGenerationPipeline:
    """Integration tests for complete strategy generation pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_pipeline_success(self):
        """Test complete pipeline: research → generation → optimization → storage.

        This is an end-to-end test of the full workflow.
        Requires: Database with test data, LLM API access.
        """
        # Skip if no LLM access (CI environment)
        pytest.skip("Requires LLM API access - run manually for full integration testing")

        symbol = "AAPL"

        # Step 1: Aggregate research
        aggregator = ResearchAggregationService()
        research = await aggregator.aggregate_research(symbol, lookback_days=30)

        # Verify research quality
        assert isinstance(research, ResearchInsights)
        assert research.symbol == symbol
        assert research.overall_confidence > 0.0
        assert research.research_quality in ["high", "medium", "low"]

        # Step 2: Generate strategy from research
        generator = StrategyGeneratorAgent()
        strategy_result = await generator.generate_strategy(research)

        # Verify strategy generated
        assert isinstance(strategy_result, StrategyGenerationResult)
        assert strategy_result.strategy_type in [
            "momentum",
            "value",
            "event",
            "reversal",
            "defensive",
            "no_strategy",
        ]
        assert 0.0 <= strategy_result.confidence <= 1.0
        assert len(strategy_result.reasoning) >= 50  # Min length validation

        # Verify parameter weights sum to 1.0
        weights = [
            strategy_result.parameters.weight_price_trend,
            strategy_result.parameters.weight_rsi_health,
            strategy_result.parameters.weight_momentum,
            strategy_result.parameters.weight_volume,
            strategy_result.parameters.weight_fundamentals,
            strategy_result.parameters.weight_news_sentiment,
            strategy_result.parameters.weight_sector_alignment,
        ]
        assert abs(sum(weights) - 1.0) < 0.01

        # Step 3: Optimize parameters (if not no_strategy)
        if strategy_result.strategy_type != "no_strategy":
            optimizer = StrategyOptimizer()
            optimized_config = await optimizer.optimize_strategy_parameters(
                symbol=symbol, strategy_template=strategy_result, lookback_days=180, max_combinations=5
            )

            # Verify optimization results
            assert optimized_config.strategy_type == strategy_result.strategy_type
            assert 0.0 <= optimized_config.confidence <= 1.0
            assert len(optimized_config.optimization_metrics) > 0

        # Step 4: Store strategy
        storage = StrategyStorage()

        # Convert research to dict for storage
        research_dict = {
            "symbol": research.symbol,
            "as_of_date": research.as_of_date.isoformat(),
            "overall_confidence": research.overall_confidence,
            "research_quality": research.research_quality,
            # Add other key fields as needed
        }

        # Convert parameters to dict
        params_dict = strategy_result.parameters.dict()

        if strategy_result.strategy_type != "no_strategy":
            strategy_id = storage.store_strategy(
                symbol=symbol,
                strategy_type=strategy_result.strategy_type,
                parameters=params_dict,
                research_summary=research_dict,
                generation_reasoning=strategy_result.reasoning,
                backtest_metrics=optimized_config.optimization_metrics,
                expected_sharpe=optimized_config.avg_sharpe,
                expected_win_rate=optimized_config.avg_win_rate,
                expected_max_drawdown=optimized_config.max_drawdown,
                created_by=f"test:{uuid.uuid4()}",
                status="testing",
            )

            # Verify strategy stored
            assert uuid.UUID(strategy_id)  # Valid UUID

            # Retrieve and verify
            retrieved = storage.get_strategy_by_id(strategy_id)
            assert retrieved is not None
            assert retrieved["symbol"] == symbol
            assert retrieved["strategy_type"] == strategy_result.strategy_type

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_research_aggregation_with_real_data(self):
        """Test research aggregation with real database data.

        Requires: Database with market data for test ticker.
        """
        symbol = "AAPL"
        aggregator = ResearchAggregationService()

        research = await aggregator.aggregate_research(symbol, lookback_days=30)

        # Verify structure
        assert isinstance(research, ResearchInsights)
        assert research.symbol == symbol
        assert isinstance(research.as_of_date, date)

        # Verify news intelligence populated
        assert research.news_sentiment_trend in ["improving", "stable", "deteriorating"]
        assert -1.0 <= research.news_sentiment_score <= 1.0
        assert research.news_volume >= 0
        assert 0.0 <= research.news_confidence <= 1.0

        # Verify fundamental analysis populated
        assert research.company_health in ["EXCELLENT", "GOOD", "WEAK"]
        assert 0 <= research.fundamental_score <= 100
        assert research.valuation_tier in ["undervalued", "fair", "overvalued"]
        assert 0.0 <= research.fundamental_confidence <= 1.0

        # Verify technical analysis populated
        assert research.trend_strength in [
            "strong_up",
            "weak_up",
            "neutral",
            "weak_down",
            "strong_down",
        ]
        assert research.momentum_rating in ["accelerating", "steady", "decelerating"]
        assert 0.0 <= research.technical_confidence <= 1.0

        # Verify macro context populated
        assert research.market_regime in ["bull", "bear", "range", "volatile"]
        assert 0 <= research.fear_greed_score <= 100
        assert research.fear_greed_classification in [
            "extreme_fear",
            "fear",
            "neutral",
            "greed",
            "extreme_greed",
        ]

        # Verify sector analysis populated
        assert isinstance(research.sector, str)
        assert research.sector_momentum in ["leading", "in_line", "lagging"]
        assert isinstance(research.sector_vs_spy_30d, (int, float))

        # Verify overall assessment
        assert 0.0 <= research.overall_confidence <= 1.0
        assert research.research_quality in ["high", "medium", "low"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_missing_symbol(self):
        """Test error handling when symbol doesn't exist in database."""
        symbol = "INVALID_SYMBOL_XYZ"
        aggregator = ResearchAggregationService()

        # Should raise ValueError for missing symbol
        with pytest.raises(ValueError, match="not found|insufficient|invalid"):
            await aggregator.aggregate_research(symbol)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_strategy_storage_retrieval(self):
        """Test strategy storage and retrieval operations."""
        storage = StrategyStorage()
        symbol = "TEST"

        # Create test strategy
        strategy_id = storage.store_strategy(
            symbol=symbol,
            strategy_type="momentum",
            parameters={
                "weight_price_trend": 0.20,
                "weight_rsi_health": 0.10,
                "weight_momentum": 0.25,
                "weight_volume": 0.10,
                "weight_fundamentals": 0.15,
                "weight_news_sentiment": 0.15,
                "weight_sector_alignment": 0.05,
                "min_confirmations": 6,
                "min_weighted_score": 0.65,
            },
            research_summary={"symbol": symbol, "confidence": 0.8},
            generation_reasoning="Test strategy for integration testing purposes only.",
            backtest_metrics=[{"sharpe": 1.5, "win_rate": 0.6}],
            expected_sharpe=1.5,
            expected_win_rate=0.6,
            expected_max_drawdown=0.15,
            created_by="integration_test",
            status="testing",
        )

        # Test retrieval by ID
        strategy = storage.get_strategy_by_id(strategy_id)
        assert strategy is not None
        assert strategy["id"] == strategy_id
        assert strategy["symbol"] == symbol
        assert strategy["strategy_type"] == "momentum"
        assert strategy["status"] == "testing"

        # Test retrieval by symbol
        strategies = storage.list_strategies_for_symbol(symbol)
        assert len(strategies) >= 1
        assert any(s["id"] == strategy_id for s in strategies)

        # Test status update
        storage.update_strategy_status(strategy_id, "active")
        updated = storage.get_strategy_by_id(strategy_id)
        assert updated["status"] == "active"

        # Test archive
        storage.archive_strategy(strategy_id, "Integration test cleanup")
        archived = storage.get_strategy_by_id(strategy_id)
        assert archived["status"] == "archived"
        assert archived["archive_reason"] == "Integration test cleanup"
