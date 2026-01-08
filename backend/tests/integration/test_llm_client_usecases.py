"""Integration tests for Agent Hub LLM client with Portfolio AI use cases.

Tests AgentHubAPIClient with actual data patterns from:
- Gap analysis
- Paper trading decisions
- Backtesting analysis
- News sentiment analysis

Requires Agent Hub service running at localhost:8003.
"""

from __future__ import annotations

import json

import pytest

from app.agents.llm_client import AgentHubAPIClient, DualProviderClient


@pytest.fixture
def agent_hub_client() -> AgentHubAPIClient:
    """Create Agent Hub client for testing."""
    return AgentHubAPIClient(model="claude-sonnet-4-5-20250514")


@pytest.fixture
def gemini_client() -> AgentHubAPIClient:
    """Create Agent Hub client with Gemini model."""
    return AgentHubAPIClient(model="gemini-3-flash-preview")


class TestGapAnalysisUseCase:
    """Test Agent Hub clients with gap analysis data patterns."""

    def test_agent_hub_gap_analysis_small(self, agent_hub_client: AgentHubAPIClient) -> None:
        """Test Agent Hub with small gap analysis dataset."""
        gap_data = {
            "symbol": "AAPL",
            "current_data": {
                "price": 150.25,
                "volume": 1000000,
                "market_cap": "2.5T",
            },
            "missing_data": [
                "earnings_date",
                "analyst_ratings",
                "insider_trades",
            ],
            "recommendations": [
                "Add earnings calendar integration",
                "Enable analyst consensus tracking",
            ],
        }

        prompt = f"""Analyze this gap analysis and provide a priority score (1-10):

{json.dumps(gap_data, indent=2)}

Reply with just the number."""

        response = agent_hub_client.generate(prompt)

        assert response.content.strip().isdigit()
        assert 1 <= int(response.content.strip()) <= 10

    def test_gemini_gap_analysis_small(self, gemini_client: AgentHubAPIClient) -> None:
        """Test Gemini via Agent Hub with small gap analysis dataset."""
        gap_data = {
            "symbol": "TSLA",
            "data_quality": {"completeness": 75, "freshness": 90},
            "gaps": ["options_data", "short_interest"],
        }

        prompt = f"""Rate the severity of these data gaps (LOW/MEDIUM/HIGH):

{json.dumps(gap_data, indent=2)}

Reply with just the severity level."""

        response = gemini_client.generate(prompt)

        assert response.content.strip().upper() in ["LOW", "MEDIUM", "HIGH"]

    def test_dual_provider_gap_analysis(self) -> None:
        """Test DualProviderClient (Agent Hub wrapper) with gap analysis."""
        client = DualProviderClient(primary="gemini")

        gaps = {
            "symbols": ["AAPL", "GOOGL", "MSFT"],
            "common_gaps": ["real_time_options", "institutional_holdings"],
            "priority": "high",
        }

        prompt = f"""How many symbols have data gaps?

{json.dumps(gaps, indent=2)}

Reply with just the number."""

        response = client.generate(prompt)

        assert response.content.strip() == "3"


class TestPaperTradingUseCase:
    """Test Agent Hub with paper trading decision data."""

    def test_trading_signal_analysis(self, agent_hub_client: AgentHubAPIClient) -> None:
        """Test Agent Hub with trading signal analysis."""
        signal_data = {
            "symbol": "NVDA",
            "signal": "BUY",
            "confidence": 0.85,
            "indicators": {
                "rsi": 45,
                "macd": "bullish_crossover",
                "volume": "above_average",
            },
        }

        prompt = f"""Should this trade be executed? Reply YES or NO.

{json.dumps(signal_data, indent=2)}"""

        response = agent_hub_client.generate(prompt)

        assert response.content.strip().upper() in ["YES", "NO"]


class TestBacktestUseCase:
    """Test Agent Hub with backtesting analysis data."""

    def test_backtest_analysis(self, agent_hub_client: AgentHubAPIClient) -> None:
        """Test Agent Hub with backtest results analysis."""
        backtest_results = {
            "strategy": "momentum",
            "period": "2024-01-01 to 2024-12-31",
            "returns": {"total": 0.15, "annual": 0.15, "max_drawdown": -0.08},
            "trades": {"total": 50, "winners": 32, "losers": 18},
        }

        prompt = f"""Rate this backtest performance (POOR/FAIR/GOOD/EXCELLENT):

{json.dumps(backtest_results, indent=2)}

Reply with just the rating."""

        response = agent_hub_client.generate(prompt)

        assert response.content.strip().upper() in ["POOR", "FAIR", "GOOD", "EXCELLENT"]


class TestSentimentUseCase:
    """Test Agent Hub with news sentiment analysis."""

    def test_sentiment_analysis(self, agent_hub_client: AgentHubAPIClient) -> None:
        """Test Agent Hub with news sentiment extraction."""
        news = {
            "headline": "Tech stocks rally on AI optimism",
            "content": "Major tech companies see gains as investors...",
            "symbols": ["NVDA", "MSFT", "GOOGL"],
        }

        prompt = f"""What is the sentiment of this news? Reply POSITIVE, NEGATIVE, or NEUTRAL.

{json.dumps(news, indent=2)}"""

        response = agent_hub_client.generate(prompt)

        assert response.content.strip().upper() in ["POSITIVE", "NEGATIVE", "NEUTRAL"]
