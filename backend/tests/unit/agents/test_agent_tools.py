"""Unit tests for agent tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import pytest

from app.agents.tools import (
    AgentTools,
    get_economic_data_tool_definition,
    get_news_tool_definition,
    get_portfolio_data_tool_definition,
    get_price_data_tool_definition,
    get_store_idea_tool_definition,
)
from app.portfolio.models import (
    ConcentrationMetrics,
    PortfolioAnalytics,
    PortfolioValue,
    Position,
    PriceData,
)


@pytest.fixture
def mock_storage() -> Mock:
    """Create a mock storage instance."""
    return Mock()


@pytest.fixture
def mock_news_service() -> Mock:
    """Create a mock news service."""
    return Mock()


@pytest.fixture
def mock_fred_source() -> Mock:
    """Create a mock FRED source."""
    return Mock()


@pytest.fixture
def mock_price_fetcher() -> Mock:
    """Create a mock price fetcher."""
    return Mock()


@pytest.fixture
def mock_portfolio_mgr() -> Mock:
    """Create a mock portfolio manager."""
    return Mock()


@pytest.fixture
def mock_analytics() -> Mock:
    """Create a mock analytics instance."""
    return Mock()


@pytest.fixture
def agent_tools(
    mock_storage: Mock,
    mock_news_service: Mock,
    mock_fred_source: Mock,
    mock_price_fetcher: Mock,
    mock_portfolio_mgr: Mock,
    mock_analytics: Mock,
) -> AgentTools:
    """Create an AgentTools instance with all mocks."""
    return AgentTools(
        storage=mock_storage,
        news_service=mock_news_service,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=mock_portfolio_mgr,
        analytics=mock_analytics,
    )


def test_get_news_tool_definition() -> None:
    """Test news tool definition structure."""
    tool_def: dict[str, Any] = get_news_tool_definition()

    assert tool_def["name"] == "get_news"
    assert "description" in tool_def
    assert "input_schema" in tool_def
    assert tool_def["input_schema"]["type"] == "object"
    assert "query" in tool_def["input_schema"]["properties"]
    assert "max_results" in tool_def["input_schema"]["properties"]
    assert tool_def["input_schema"]["required"] == ["query"]


def test_get_economic_data_tool_definition() -> None:
    """Test economic data tool definition structure."""
    tool_def: dict[str, Any] = get_economic_data_tool_definition()

    assert tool_def["name"] == "get_economic_data"
    assert "description" in tool_def
    assert "input_schema" in tool_def
    assert "indicators" in tool_def["input_schema"]["properties"]
    assert tool_def["input_schema"]["required"] == ["indicators"]


def test_get_portfolio_data_tool_definition() -> None:
    """Test portfolio data tool definition structure."""
    tool_def: dict[str, Any] = get_portfolio_data_tool_definition()

    assert tool_def["name"] == "get_portfolio_data"
    assert "description" in tool_def
    assert "input_schema" in tool_def
    assert tool_def["input_schema"]["properties"] == {}


def test_get_price_data_tool_definition() -> None:
    """Test price data tool definition structure."""
    tool_def: dict[str, Any] = get_price_data_tool_definition()

    assert tool_def["name"] == "get_price_data"
    assert "description" in tool_def
    assert "input_schema" in tool_def
    assert "symbols" in tool_def["input_schema"]["properties"]
    assert tool_def["input_schema"]["required"] == ["symbols"]


def test_get_store_idea_tool_definition() -> None:
    """Test store idea tool definition structure."""
    tool_def: dict[str, Any] = get_store_idea_tool_definition()

    assert tool_def["name"] == "store_idea"
    assert "description" in tool_def
    assert "input_schema" in tool_def

    properties = tool_def["input_schema"]["properties"]
    assert "title" in properties
    assert "thesis" in properties
    assert "action" in properties
    assert "idea_type" in properties
    assert "confidence_score" in properties
    assert "risk_level" in properties
    assert "reward_estimate" in properties
    assert "portfolio_impact" in properties
    assert "risks" in properties

    required = tool_def["input_schema"]["required"]
    assert "title" in required
    assert "thesis" in required
    assert "action" in required
    assert "idea_type" in required
    assert "confidence_score" in required
    assert "risk_level" in required


def test_execute_get_news(agent_tools: AgentTools, mock_news_service: Mock) -> None:
    """Test executing get_news tool."""
    from datetime import UTC, datetime

    from app.services.news_models import NewsArticle, NewsBundle, NewsSummary, SentimentScore

    # Setup mock with proper NewsBundle structure
    mock_articles = [
        NewsArticle(
            symbol="MARKET",
            headline="Market rallies",
            url="http://example.com/1",
            summary="Markets are up",
            source="TestSource",
            published_at=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
            sentiment=SentimentScore(score=0.8, label="positive", confidence=0.95, model="finbert"),
            content_hash="hash1",
        ),
        NewsArticle(
            symbol="MARKET",
            headline="Tech stocks surge",
            url="http://example.com/2",
            summary="Tech is booming",
            source="TestSource",
            published_at=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
            sentiment=SentimentScore(score=0.9, label="positive", confidence=0.98, model="finbert"),
            content_hash="hash2",
        ),
    ]
    mock_summary = NewsSummary(
        symbol="MARKET",
        score=0.85,
        score_change=0.1,
        positive_count=2,
        neutral_count=0,
        negative_count=0,
        article_count=2,
        latest_published_at=datetime.now(UTC),
    )
    mock_bundle = NewsBundle(
        symbol="MARKET",
        summary=mock_summary,
        articles=mock_articles,
    )

    mock_news_service.refresh_max_articles_from_preferences.return_value = 20
    mock_news_service.get_news_intelligence.return_value = mock_bundle

    # Execute
    result: dict[str, Any] = agent_tools.execute_get_news("stock market", max_results=10)

    # Verify
    assert result["query"] == "stock market"
    assert result["symbol"] == "MARKET"
    assert result["count"] == 2
    assert len(result["articles"]) == 2
    assert result["articles"][0]["headline"] == "Market rallies"
    assert result["articles"][1]["headline"] == "Tech stocks surge"
    mock_news_service.get_news_intelligence.assert_called_once_with(None, max_articles=10)


def test_execute_get_news_default_max_results(
    agent_tools: AgentTools, mock_news_service: Mock
) -> None:
    """Test get_news with default max_results."""
    from app.services.news_models import NewsBundle, NewsSummary

    # Setup mock with empty NewsBundle
    mock_summary = NewsSummary(
        symbol="MARKET",
        score=None,
        score_change=None,
        positive_count=0,
        neutral_count=0,
        negative_count=0,
        article_count=0,
        latest_published_at=None,
    )
    mock_bundle = NewsBundle(
        symbol="MARKET",
        summary=mock_summary,
        articles=[],
    )

    mock_news_service.refresh_max_articles_from_preferences.return_value = 20
    mock_news_service.get_custom_news.return_value = mock_bundle

    agent_tools.execute_get_news("technology")

    # Should use preferences limit (20) since max_results not specified
    mock_news_service.get_custom_news.assert_called_once_with("technology", max_articles=20)


def test_execute_get_economic_data(agent_tools: AgentTools, mock_fred_source: Mock) -> None:
    """Test executing get_economic_data tool."""
    # Setup mock
    mock_data = {
        "VIX": {"value": 18.5, "date": "2025-10-27"},
        "TNX": {"value": 4.2, "date": "2025-10-27"},
    }
    mock_fred_source.fetch_multiple.return_value = mock_data

    # Execute
    result: dict[str, Any] = agent_tools.execute_get_economic_data(["VIX", "TNX"])

    # Verify
    assert result["indicators"] == mock_data
    assert result["count"] == 2
    mock_fred_source.fetch_multiple.assert_called_once_with(["VIX", "TNX"])


def test_execute_get_portfolio_data_empty(
    agent_tools: AgentTools, mock_portfolio_mgr: Mock
) -> None:
    """Test get_portfolio_data with empty portfolio."""
    # Setup mock
    mock_portfolio_mgr.get_positions.return_value = []

    # Execute
    result: dict[str, Any] = agent_tools.execute_get_portfolio_data()

    # Verify
    assert result["positions"] == []
    assert result["analytics"] is None
    mock_portfolio_mgr.get_positions.assert_called_once()


def test_execute_get_portfolio_data_with_positions(
    agent_tools: AgentTools,
    mock_portfolio_mgr: Mock,
    mock_price_fetcher: Mock,
    mock_analytics: Mock,
) -> None:
    """Test get_portfolio_data with positions."""
    # Setup mock positions
    position1 = Position(
        id="pos1",
        account_id="acc1",
        symbol="AAPL",
        shares=100.0,
        cost_basis=150.0,
        position_type="long",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    position2 = Position(
        id="pos2",
        account_id="acc1",
        symbol="GOOGL",
        shares=50.0,
        cost_basis=2000.0,
        position_type="long",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_portfolio_mgr.get_positions.return_value = [position1, position2]

    # Setup mock price data
    price_data = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=170.0,
            beta=1.2,
            volatility=0.25,
            sector="Technology",
        ),
        "GOOGL": PriceData(
            symbol="GOOGL",
            price=2500.0,
            beta=1.1,
            volatility=0.22,
            sector="Technology",
        ),
    }
    mock_price_fetcher.fetch_price_data.return_value = price_data

    # Setup mock analytics
    mock_portfolio_analytics = PortfolioAnalytics(
        portfolio_value=PortfolioValue(
            total_value=142000.0,
            total_cost_basis=115000.0,
            total_gain=27000.0,
            total_gain_pct=23.48,
        ),
        portfolio_beta=1.16,
        portfolio_volatility=0.24,
        sector_exposure={"Technology": 100.0},
        concentration_metrics=ConcentrationMetrics(
            top_holding_pct=88.03,
            top_3_pct=100.0,
            top_10_pct=100.0,
            herfindahl_index=0.775,
        ),
        num_positions=2,
        num_symbols=2,
    )
    mock_analytics.calculate_full_analytics.return_value = mock_portfolio_analytics

    # Execute
    result: dict[str, Any] = agent_tools.execute_get_portfolio_data()

    # Verify
    assert len(result["positions"]) == 2
    assert result["positions"][0]["symbol"] == "AAPL"
    assert result["positions"][1]["symbol"] == "GOOGL"
    assert result["analytics"] is not None
    assert result["analytics"]["portfolio_beta"] == 1.16
    assert result["analytics"]["num_positions"] == 2

    mock_portfolio_mgr.get_positions.assert_called_once()
    # Check that fetch_price_data was called with the right symbols (order may vary)
    mock_price_fetcher.fetch_price_data.assert_called_once()
    called_symbols = mock_price_fetcher.fetch_price_data.call_args[0][0]
    assert set(called_symbols) == {"AAPL", "GOOGL"}
    mock_analytics.calculate_full_analytics.assert_called_once()


def test_execute_get_price_data(agent_tools: AgentTools, mock_price_fetcher: Mock) -> None:
    """Test executing get_price_data tool."""
    # Setup mock
    price_data = {
        "AAPL": PriceData(
            symbol="AAPL",
            price=170.0,
            beta=1.2,
            volatility=0.25,
            sector="Technology",
        ),
        "MSFT": PriceData(
            symbol="MSFT",
            price=380.0,
            beta=0.9,
            volatility=0.20,
            sector="Technology",
        ),
    }
    mock_price_fetcher.fetch_price_data.return_value = price_data

    # Execute
    result: dict[str, Any] = agent_tools.execute_get_price_data(["AAPL", "MSFT"])

    # Verify
    assert result["count"] == 2
    assert "AAPL" in result["prices"]
    assert "MSFT" in result["prices"]
    assert result["prices"]["AAPL"]["price"] == 170.0
    assert result["prices"]["MSFT"]["price"] == 380.0
    mock_price_fetcher.fetch_price_data.assert_called_once_with(["AAPL", "MSFT"])


def test_execute_store_idea(agent_tools: AgentTools, mock_storage: Mock) -> None:
    """Test executing store_idea tool."""
    # Setup
    run_id = "test-run-id"
    idea_data = {
        "title": "Buy AAPL calls",
        "thesis": "Apple is undervalued and earnings look strong",
        "action": "Buy 10 AAPL 200 calls expiring 2025-12-31",
        "idea_type": "option",
        "confidence_score": 75.0,
        "risk_level": "medium",
        "reward_estimate": "15-20% return",
        "portfolio_impact": "Adds tech exposure with limited downside",
        "risks": "Earnings miss, macro weakness",
    }

    # Execute
    result: dict[str, Any] = agent_tools.execute_store_idea(run_id, **idea_data)

    # Verify
    assert "idea_id" in result
    assert result["status"] == "stored"

    # Verify storage was called with correct data
    mock_storage.insert_dict.assert_called_once()
    call_args = mock_storage.insert_dict.call_args
    assert call_args[0][0] == "agent_ideas"

    stored_data = call_args[0][1]
    assert stored_data["agent_run_id"] == run_id
    assert stored_data["title"] == idea_data["title"]
    assert stored_data["thesis"] == idea_data["thesis"]
    assert stored_data["action"] == idea_data["action"]
    assert stored_data["idea_type"] == idea_data["idea_type"]
    # confidence_score is normalized: values > 1.0 are divided by 100 (percentage -> decimal)
    assert stored_data["confidence_score"] == 0.75
    assert stored_data["risk_level"] == idea_data["risk_level"]
    assert stored_data["status"] == "pending"
    assert "id" in stored_data
    assert "created_at" in stored_data
    assert "updated_at" in stored_data


def test_execute_store_idea_minimal_fields(agent_tools: AgentTools, mock_storage: Mock) -> None:
    """Test store_idea with only required fields."""
    run_id = "test-run-id"
    idea_data = {
        "title": "Short SPY",
        "thesis": "Market overheated",
        "action": "Short 100 SPY",
        "idea_type": "short",
        "confidence_score": 60.0,
        "risk_level": "high",
    }

    # Execute
    result: dict[str, Any] = agent_tools.execute_store_idea(run_id, **idea_data)

    # Verify
    assert result["status"] == "stored"
    mock_storage.insert_dict.assert_called_once()


def test_agent_tools_initialization(
    mock_storage: Mock,
    mock_news_service: Mock,
    mock_fred_source: Mock,
    mock_price_fetcher: Mock,
    mock_portfolio_mgr: Mock,
    mock_analytics: Mock,
) -> None:
    """Test AgentTools initialization stores all dependencies."""
    tools = AgentTools(
        storage=mock_storage,
        news_service=mock_news_service,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=mock_portfolio_mgr,
        analytics=mock_analytics,
    )

    # Verify AgentTools correctly initializes with dependencies
    assert tools.storage is mock_storage
    # Dependencies are delegated to specialized executors
    assert tools.data.news_service is mock_news_service
    assert tools.data.fred_source is mock_fred_source
    assert tools.data.price_fetcher is mock_price_fetcher
    assert tools.data.portfolio_mgr is mock_portfolio_mgr
    assert tools.data.analytics is mock_analytics
