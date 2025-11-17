"""Integration tests for LLM client with real Portfolio AI use cases.

Tests both Gemini and Claude CLIs with actual data patterns from:
- Gap analysis
- Paper trading decisions
- Backtesting analysis
- News sentiment analysis
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.agents.llm_client import ClaudeCLIClient, DualProviderClient, GeminiCLIClient


class TestGapAnalysisUseCase:
    """Test LLM clients with gap analysis data patterns."""

    def test_gemini_gap_analysis_small(self) -> None:
        """Test Gemini with small gap analysis dataset."""
        client = GeminiCLIClient()

        gap_data = {
            "ticker": "AAPL",
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

        response = client.generate(prompt)

        assert response.content.strip().isdigit()
        assert response.provider == "gemini"
        assert 1 <= int(response.content.strip()) <= 10

    def test_claude_gap_analysis_small(self) -> None:
        """Test Claude with small gap analysis dataset."""
        client = ClaudeCLIClient()

        gap_data = {
            "ticker": "TSLA",
            "data_quality": {"completeness": 75, "freshness": 90},
            "gaps": ["options_data", "short_interest"],
        }

        prompt = f"""Rate the severity of these data gaps (LOW/MEDIUM/HIGH):

{json.dumps(gap_data, indent=2)}

Reply with just the severity level."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["LOW", "MEDIUM", "HIGH"]
        assert response.provider == "claude"

    def test_dual_provider_gap_analysis_with_fallback(self) -> None:
        """Test dual provider with gap analysis (Gemini primary, Claude fallback)."""
        client = DualProviderClient(primary="gemini")

        # Gap analysis with multiple tickers
        gaps = {
            "tickers": ["AAPL", "GOOGL", "MSFT"],
            "common_gaps": ["real_time_options", "institutional_holdings"],
            "priority": "high",
        }

        prompt = f"""How many tickers have data gaps?

{json.dumps(gaps, indent=2)}

Reply with just the number."""

        response = client.generate(prompt)

        assert response.content.strip() == "3"
        assert response.provider in ["gemini", "claude"]


class TestPaperTradingUseCase:
    """Test LLM clients with paper trading decision patterns."""

    def test_gemini_paper_trading_decision(self) -> None:
        """Test Gemini with paper trading scenario."""
        client = GeminiCLIClient()

        trade_data = {
            "ticker": "NVDA",
            "current_price": 450.75,
            "indicators": {
                "rsi": 68,
                "macd": "bullish",
                "volume_trend": "increasing",
            },
            "news_sentiment": "positive",
            "analyst_consensus": "buy",
        }

        prompt = f"""Should we execute this paper trade? (YES/NO)

{json.dumps(trade_data, indent=2)}

Reply with just YES or NO."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["YES", "NO"]
        assert response.provider == "gemini"

    def test_claude_paper_trading_risk_assessment(self) -> None:
        """Test Claude with paper trading risk assessment."""
        client = ClaudeCLIClient()

        risk_data = {
            "position_size": 1000,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "portfolio_allocation": 10.0,
            "max_loss": -200,
        }

        prompt = f"""Is this risk profile acceptable? (ACCEPTABLE/TOO_RISKY)

{json.dumps(risk_data, indent=2)}

Reply with just the assessment."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["ACCEPTABLE", "TOO_RISKY"]
        assert response.provider == "claude"


class TestBacktestingUseCase:
    """Test LLM clients with backtesting analysis patterns."""

    def test_gemini_backtest_summary(self) -> None:
        """Test Gemini with backtest results."""
        client = GeminiCLIClient()

        backtest_results = {
            "strategy": "momentum_with_rsi",
            "period": "2024-01-01 to 2024-12-31",
            "total_trades": 45,
            "win_rate": 62.2,
            "total_return": 18.5,
            "max_drawdown": -8.3,
            "sharpe_ratio": 1.85,
        }

        prompt = f"""Rate this backtest performance (POOR/GOOD/EXCELLENT):

{json.dumps(backtest_results, indent=2)}

Reply with just the rating."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["POOR", "GOOD", "EXCELLENT"]
        assert response.provider == "gemini"

    def test_claude_backtest_comparison(self) -> None:
        """Test Claude comparing multiple backtest strategies."""
        client = ClaudeCLIClient()

        comparison = {
            "strategy_a": {"sharpe": 1.85, "return": 18.5, "drawdown": -8.3},
            "strategy_b": {"sharpe": 2.10, "return": 22.3, "drawdown": -6.1},
            "strategy_c": {"sharpe": 1.62, "return": 15.8, "drawdown": -10.2},
        }

        prompt = f"""Which strategy is best overall? (A/B/C)

{json.dumps(comparison, indent=2)}

Reply with just the letter."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["A", "B", "C"]
        assert response.provider == "claude"


class TestNewsSentimentUseCase:
    """Test LLM clients with news sentiment analysis patterns."""

    def test_gemini_news_sentiment(self) -> None:
        """Test Gemini analyzing news sentiment."""
        client = GeminiCLIClient()

        news_items = [
            {
                "ticker": "AAPL",
                "headline": "Apple announces record quarterly earnings",
                "source": "Reuters",
            },
            {
                "ticker": "AAPL",
                "headline": "Apple faces regulatory scrutiny in EU",
                "source": "Bloomberg",
            },
        ]

        prompt = f"""What's the overall sentiment? (POSITIVE/NEGATIVE/NEUTRAL)

{json.dumps(news_items, indent=2)}

Reply with just the sentiment."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["POSITIVE", "NEGATIVE", "NEUTRAL"]
        assert response.provider == "gemini"

    def test_claude_news_impact_assessment(self) -> None:
        """Test Claude assessing news impact on trading."""
        client = ClaudeCLIClient()

        news = {
            "ticker": "TSLA",
            "headline": "Tesla recalls 500k vehicles for safety issue",
            "sentiment": "negative",
            "expected_impact": "moderate",
        }

        prompt = f"""Should we adjust our position? (HOLD/REDUCE/EXIT)

{json.dumps(news, indent=2)}

Reply with just the action."""

        response = client.generate(prompt)

        assert response.content.strip().upper() in ["HOLD", "REDUCE", "EXIT"]
        assert response.provider == "claude"


class TestLargeDatasetHandling:
    """Test LLM clients with large datasets (realistic Portfolio AI scale)."""

    def test_gemini_large_ticker_list(self) -> None:
        """Test Gemini with large ticker watchlist."""
        client = GeminiCLIClient()

        # 50 tickers with data
        tickers = [
            {"ticker": f"STOCK{i}", "price": 100 + i, "change_pct": i % 10 - 5}
            for i in range(50)
        ]

        prompt = f"""How many stocks are showing positive gains?

{json.dumps(tickers, indent=2)}

Reply with just the number."""

        response = client.generate(prompt)

        assert response.content.strip().isdigit()
        count = int(response.content.strip())
        assert 0 <= count <= 50

    @pytest.mark.slow
    def test_dual_provider_very_large_dataset(self) -> None:
        """Test dual provider with very large dataset (stress test)."""
        client = DualProviderClient(primary="gemini")

        # 200 records (realistic for gap analysis results)
        records = [
            {
                "id": i,
                "ticker": f"TICK{i}",
                "gap_type": "missing_data",
                "severity": "medium" if i % 3 == 0 else "low",
            }
            for i in range(200)
        ]

        prompt = f"""Count records with severity='medium':

{json.dumps(records, indent=2)[:30000]}  # Limit to 30KB

Reply with just the number."""

        response = client.generate(prompt)

        # Should handle large input and return reasonable answer
        assert response.content.strip().isdigit()
        assert response.provider in ["gemini", "claude"]


class TestCSVDataHandling:
    """Test LLM clients with CSV-formatted data (common in backtesting)."""

    def test_gemini_parse_trade_history_csv(self) -> None:
        """Test Gemini parsing trade history CSV."""
        client = GeminiCLIClient()

        csv_data = """date,ticker,action,price,shares,total
2024-01-15,AAPL,BUY,150.25,10,1502.50
2024-01-20,AAPL,SELL,155.75,10,1557.50
2024-02-01,GOOGL,BUY,2800.00,2,5600.00
2024-02-15,GOOGL,SELL,2850.50,2,5701.00"""

        prompt = f"""Calculate total profit from these trades:

{csv_data}

Reply with just the dollar amount (no $)."""

        response = client.generate(prompt)

        # Should calculate: (1557.50 - 1502.50) + (5701.00 - 5600.00) = 156.00
        result = response.content.strip().replace("$", "").replace(",", "")
        assert result.replace(".", "").isdigit()

    def test_claude_parse_indicator_csv(self) -> None:
        """Test Claude parsing technical indicator CSV."""
        client = ClaudeCLIClient()

        csv_data = """ticker,date,rsi,macd,signal
AAPL,2024-11-15,68.5,2.3,bullish
TSLA,2024-11-15,42.1,-1.5,bearish
NVDA,2024-11-15,72.8,3.1,bullish"""

        prompt = f"""How many tickers show bullish signals?

{csv_data}

Reply with just the number."""

        response = client.generate(prompt)

        assert response.content.strip() == "2"
        assert response.provider == "claude"
