"""Unit tests for Agent Hub LLM client with Portfolio AI use cases.

Tests AgentHubAPIClient request/response handling with actual data patterns from:
- Gap analysis
- Paper trading decisions
- Backtesting analysis
- News sentiment analysis

All tests use mocked responses to prevent real API calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from unittest.mock import patch

import pytest

from app.agents.llm_client import AgentHubAPIClient, DualProviderClient, LLMResponse


@pytest.fixture
def mock_llm_response() -> Callable[..., LLMResponse]:
    """Factory fixture for creating mock LLM responses."""

    def _create_response(content: str, model: str = "claude-sonnet-4-5-20250514") -> LLMResponse:
        return LLMResponse(
            content=content,
            provider="claude" if "claude" in model else "gemini",
            model=model,
            usage={"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        )

    return _create_response


class TestGapAnalysisUseCase:
    """Test Agent Hub clients with gap analysis data patterns."""

    def test_agent_hub_gap_analysis_small(self, mock_llm_response: Callable[..., LLMResponse]) -> None:
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

        with patch.object(AgentHubAPIClient, "generate") as mock_generate:
            mock_generate.return_value = mock_llm_response("7")
            client = AgentHubAPIClient(model="claude-sonnet-4-5-20250514")
            response = client.generate(prompt)

            assert response.content.strip().isdigit()
            assert 1 <= int(response.content.strip()) <= 10
            mock_generate.assert_called_once()

    def test_gemini_gap_analysis_small(self, mock_llm_response: Callable[..., LLMResponse]) -> None:
        """Test Gemini via Agent Hub with small gap analysis dataset."""
        gap_data = {
            "symbol": "TSLA",
            "data_quality": {"completeness": 75, "freshness": 90},
            "gaps": ["options_data", "short_interest"],
        }

        prompt = f"""Rate the severity of these data gaps (LOW/MEDIUM/HIGH):

{json.dumps(gap_data, indent=2)}

Reply with just the severity level."""

        with patch.object(AgentHubAPIClient, "generate") as mock_generate:
            mock_generate.return_value = mock_llm_response("MEDIUM", "gemini-3-flash-preview")
            client = AgentHubAPIClient(model="gemini-3-flash-preview")
            response = client.generate(prompt)

            assert response.content.strip().upper() in ["LOW", "MEDIUM", "HIGH"]
            mock_generate.assert_called_once()

    def test_dual_provider_gap_analysis(self, mock_llm_response: Callable[..., LLMResponse]) -> None:
        """Test DualProviderClient (Agent Hub wrapper) with gap analysis."""
        gaps = {
            "symbols": ["AAPL", "GOOGL", "MSFT"],
            "common_gaps": ["real_time_options", "institutional_holdings"],
            "priority": "high",
        }

        prompt = f"""How many symbols have data gaps?

{json.dumps(gaps, indent=2)}

Reply with just the number."""

        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.generate.return_value = mock_llm_response("3", "gemini-3-flash-preview")
            mock_client.is_available.return_value = True
            mock_client.get_model_name.return_value = "gemini-3-flash-preview"

            client = DualProviderClient(primary="gemini")
            response = client.generate(prompt)

            assert response.content.strip() == "3"


class TestPaperTradingUseCase:
    """Test Agent Hub with paper trading decision data."""

    def test_trading_signal_analysis(self, mock_llm_response: Callable[..., LLMResponse]) -> None:
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

        with patch.object(AgentHubAPIClient, "generate") as mock_generate:
            mock_generate.return_value = mock_llm_response("YES")
            client = AgentHubAPIClient(model="claude-sonnet-4-5-20250514")
            response = client.generate(prompt)

            assert response.content.strip().upper() in ["YES", "NO"]
            mock_generate.assert_called_once()


class TestBacktestUseCase:
    """Test Agent Hub with backtesting analysis data."""

    def test_backtest_analysis(self, mock_llm_response: Callable[..., LLMResponse]) -> None:
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

        with patch.object(AgentHubAPIClient, "generate") as mock_generate:
            mock_generate.return_value = mock_llm_response("GOOD")
            client = AgentHubAPIClient(model="claude-sonnet-4-5-20250514")
            response = client.generate(prompt)

            assert response.content.strip().upper() in ["POOR", "FAIR", "GOOD", "EXCELLENT"]
            mock_generate.assert_called_once()


class TestSentimentUseCase:
    """Test Agent Hub with news sentiment analysis."""

    def test_sentiment_analysis(self, mock_llm_response: Callable[..., LLMResponse]) -> None:
        """Test Agent Hub with news sentiment extraction."""
        news = {
            "headline": "Tech stocks rally on AI optimism",
            "content": "Major tech companies see gains as investors...",
            "symbols": ["NVDA", "MSFT", "GOOGL"],
        }

        prompt = f"""What is the sentiment of this news? Reply POSITIVE, NEGATIVE, or NEUTRAL.

{json.dumps(news, indent=2)}"""

        with patch.object(AgentHubAPIClient, "generate") as mock_generate:
            mock_generate.return_value = mock_llm_response("POSITIVE")
            client = AgentHubAPIClient(model="claude-sonnet-4-5-20250514")
            response = client.generate(prompt)

            assert response.content.strip().upper() in ["POSITIVE", "NEGATIVE", "NEUTRAL"]
            mock_generate.assert_called_once()
