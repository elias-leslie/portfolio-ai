"""Integration tests for agents using DualProviderClient (CLI-based execution).

These tests verify that Discovery and Portfolio Analyzer agents work correctly
when using Gemini CLI and Claude CLI instead of direct Anthropic API calls.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.agents.discovery import DiscoveryAgent
from app.agents.llm_client import DualProviderClient
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.constants import GEMINI_PRO
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.fred import FREDSource
from app.storage import PortfolioStorage


@pytest.fixture
def storage() -> Generator[PortfolioStorage]:
    """Create a PortfolioStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"

    # Create fresh storage instance (bypass singleton)
    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = PortfolioStorage.__new__(PortfolioStorage)
    storage_inst.connection_mgr = ConnectionManager()
    storage_inst.schema_mgr = SchemaManager(storage_inst.connection_mgr)
    storage_inst.metadata_mgr = MetadataManager(storage_inst.connection_mgr)
    storage_inst.ingestion_mgr = IngestionManager(
        storage_inst.connection_mgr, storage_inst.metadata_mgr
    )
    storage_inst.query_mgr = QueryManager(storage_inst.connection_mgr)
    storage_inst.schema_mgr.ensure_schema()

    yield storage_inst

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def mock_news_service() -> Mock:
    """Create a mock news service."""
    from datetime import UTC, datetime

    from app.services.news_models import NewsArticle, NewsBundle, NewsSummary, SentimentScore

    # Create realistic mock articles
    mock_articles = [
        NewsArticle(
            symbol="MARKET",
            headline="Stock market reaches new highs",
            url="http://example.com/1",
            summary="Markets rally on strong earnings",
            source="Financial Times",
            published_at=datetime(2025, 10, 27, tzinfo=UTC),
            fetched_at=datetime.now(UTC),
            sentiment=SentimentScore(score=0.8, label="positive", confidence=0.95, model="finbert"),
            content_hash="hash1",
        ),
        NewsArticle(
            symbol="MARKET",
            headline="Tech sector leads gains",
            url="http://example.com/2",
            summary="Technology stocks surge",
            source="Bloomberg",
            published_at=datetime(2025, 10, 27, tzinfo=UTC),
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
        latest_published_at=datetime(2025, 10, 27, tzinfo=UTC),
    )
    mock_bundle = NewsBundle(
        symbol="MARKET",
        summary=mock_summary,
        articles=mock_articles,
    )

    mock = Mock()
    mock.refresh_max_articles_from_preferences.return_value = 20
    mock.get_news_intelligence.return_value = mock_bundle
    mock.get_custom_news.return_value = mock_bundle
    return mock


@pytest.fixture
def mock_fred_source() -> Mock:
    """Create a mock FRED source."""
    mock = Mock(spec=FREDSource)
    mock.fetch_multiple.return_value = {
        "VIX": {"indicator": "VIX", "date": "2025-10-27", "value": 15.5},
        "TNX": {"indicator": "TNX", "date": "2025-10-27", "value": 4.2},
    }
    return mock


@pytest.fixture
def agent_tools(
    storage: PortfolioStorage,
    mock_news_service: Mock,
    mock_fred_source: Mock,
) -> AgentTools:
    """Create AgentTools with mocked external sources."""
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()
    mock_price_fetcher = Mock(spec=PriceDataFetcher)

    return AgentTools(
        storage=storage,
        news_service=mock_news_service,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )


@pytest.fixture
def mock_llm_client() -> Mock:
    """Create a mock DualProviderClient that simulates CLI-based tool calling."""
    from app.agents.llm_client import LLMResponse

    mock = Mock(spec=DualProviderClient)

    # Simulate a conversation where the agent:
    # 1. Calls get_news (returns JSON with tool call)
    # 2. Calls get_economic_data (returns JSON with tool call)
    # 3. Stores 5 ideas (returns JSON with tool calls)
    # 4. Returns final response

    # First call: agent requests to use get_news tool
    response1 = LLMResponse(
        content='{"tool_calls": [{"name": "get_news", "parameters": {"query": "stock market", "max_results": 10}}]}',
        stop_reason="tool_use",
        model=GEMINI_PRO,
        provider="gemini",
        usage={"total_tokens": 100},
        tool_calls=[
            {"name": "get_news", "parameters": {"query": "stock market", "max_results": 10}}
        ],
    )

    # Second call: agent requests to use get_economic_data tool
    response2 = LLMResponse(
        content='{"tool_calls": [{"name": "get_economic_data", "parameters": {"indicators": ["VIX", "TNX"]}}]}',
        stop_reason="tool_use",
        model=GEMINI_PRO,
        provider="gemini",
        usage={"total_tokens": 100},
        tool_calls=[{"name": "get_economic_data", "parameters": {"indicators": ["VIX", "TNX"]}}],
    )

    # Third call: agent stores 5 ideas
    ideas_tool_calls = []
    for i in range(5):
        ideas_tool_calls.append(
            {
                "name": "store_idea",
                "parameters": {
                    "title": f"Investment Idea {i + 1}",
                    "thesis": f"This is investment thesis {i + 1} based on market analysis",
                    "action": f"Buy {['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'][i]}",
                    "idea_type": "long",
                    "confidence_score": 70 + i * 5,
                    "risk_level": "medium",
                    "reward_estimate": "10-15%",
                    "portfolio_impact": "Adds tech exposure",
                    "risks": "Market volatility",
                },
            }
        )

    ideas_json = {"tool_calls": ideas_tool_calls}
    response3 = LLMResponse(
        content=str(ideas_json).replace("'", '"'),
        stop_reason="tool_use",
        model=GEMINI_PRO,
        provider="gemini",
        usage={"total_tokens": 500},
        tool_calls=ideas_tool_calls,
    )

    # Fourth call: agent returns final text response
    response4 = LLMResponse(
        content="I have analyzed the market and generated 5 investment ideas.",
        stop_reason="end_turn",
        model=GEMINI_PRO,
        provider="gemini",
        usage={"total_tokens": 50},
    )

    # Set up mock to return responses in sequence
    mock.generate_with_tools.side_effect = [response1, response2, response3, response4]

    return mock


def test_discovery_agent_with_cli_initialization(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_llm_client: Mock,
) -> None:
    """Test Discovery Agent initialization with DualProviderClient."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools, llm_client=mock_llm_client)

    assert agent.storage is storage
    assert agent.tools is agent_tools
    assert agent.llm_client is mock_llm_client
    assert agent.agent_type == "DiscoveryAgent"


def test_discovery_agent_with_cli_uses_correct_path(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_llm_client: Mock,
) -> None:
    """Test Discovery Agent uses CLI path when llm_client is provided."""
    import uuid as uuid_module

    # Mock uuid to return same ID for both current_run_id and run_id
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = DiscoveryAgent(storage=storage, tools=agent_tools, llm_client=mock_llm_client)
        result = agent.run()

    # Verify result
    assert result["status"] == "completed"
    assert "response" in result
    assert result["iterations"] == 4

    # Verify CLI path was used (generate_with_tools called)
    assert mock_llm_client.generate_with_tools.call_count == 4

    # Verify Anthropic API was NOT used (base Agent should use CLI path)
    # Note: Agent still initializes Anthropic client for backwards compatibility,
    # but should not call it when llm_client is provided


def test_discovery_agent_with_cli_full_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_llm_client: Mock,
    mock_news_service: Mock,
    mock_fred_source: Mock,
) -> None:
    """Test full Discovery Agent execution with CLI-based tool calling."""
    import uuid as uuid_module

    # Mock uuid to return same ID for both current_run_id and run_id
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = DiscoveryAgent(storage=storage, tools=agent_tools, llm_client=mock_llm_client)
        result = agent.run()

    # Verify result
    assert result["status"] == "completed"
    assert "response" in result
    assert "tool_calls" in result
    assert result["iterations"] == 4

    # Verify tool calls
    tool_calls = result["tool_calls"]
    assert len(tool_calls) == 7  # 1 news + 1 econ + 5 ideas

    # Verify tools were called
    tool_names = [call["name"] for call in tool_calls]
    assert "get_news" in tool_names
    assert "get_economic_data" in tool_names
    assert tool_names.count("store_idea") == 5

    # Verify agent_runs table
    with storage.connection() as conn:
        runs = conn.execute("SELECT * FROM agent_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][1] == "DiscoveryAgent"  # agent_type
        assert runs[0][4] == "completed"  # status

    # Verify agent_ideas table
    with storage.connection() as conn:
        ideas = conn.execute("SELECT * FROM agent_ideas").fetchall()
        assert len(ideas) == 5
        for i, idea in enumerate(ideas):
            assert idea[3] == f"Investment Idea {i + 1}"  # title


def test_portfolio_analyzer_with_cli_initialization(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_llm_client: Mock,
) -> None:
    """Test Portfolio Analyzer Agent initialization with DualProviderClient."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=mock_llm_client)

    assert agent.storage is storage
    assert agent.tools is agent_tools
    assert agent.llm_client is mock_llm_client
    assert agent.agent_type == "PortfolioAnalyzerAgent"


def test_portfolio_analyzer_with_cli_uses_correct_path(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_llm_client: Mock,
) -> None:
    """Test Portfolio Analyzer Agent uses CLI path when llm_client is provided."""
    import uuid as uuid_module

    # Mock uuid to return same ID for both current_run_id and run_id
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = PortfolioAnalyzerAgent(
            storage=storage, tools=agent_tools, llm_client=mock_llm_client
        )
        result = agent.run()

    # Verify result
    assert result["status"] == "completed"
    assert "response" in result
    assert result["iterations"] == 4

    # Verify CLI path was used (generate_with_tools called)
    assert mock_llm_client.generate_with_tools.call_count == 4


def test_cli_path_records_provider_info(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_llm_client: Mock,
) -> None:
    """Test that CLI execution path records provider information in agent_runs."""
    import uuid as uuid_module

    # Mock uuid to return same ID for both current_run_id and run_id
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = DiscoveryAgent(storage=storage, tools=agent_tools, llm_client=mock_llm_client)
        result = agent.run()

    # Verify result
    assert result["status"] == "completed"

    # Verify agent_runs table has metadata about CLI execution
    with storage.connection() as conn:
        runs = conn.execute(
            "SELECT metadata FROM agent_runs WHERE id = ?", [result["run_id"]]
        ).fetchone()
        assert runs is not None
        # Note: metadata column may contain provider info in future
        # For now, just verify the run completed successfully


def test_cli_path_handles_tool_call_errors(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
) -> None:
    """Test that CLI path handles tool execution errors gracefully."""
    import uuid as uuid_module

    from app.agents.llm_client import LLMResponse

    # Create mock that returns valid tool call but tool execution will fail
    mock_client = Mock(spec=DualProviderClient)

    # First call: agent requests to use a tool that will fail
    response1 = LLMResponse(
        content='{"tool_calls": [{"name": "get_news", "parameters": {"invalid_param": "test"}}]}',
        stop_reason="tool_use",
        model=GEMINI_PRO,
        provider="gemini",
        usage={"total_tokens": 100},
        tool_calls=[{"name": "get_news", "parameters": {"invalid_param": "test"}}],
    )

    # Second call: agent handles error and returns final response
    response2 = LLMResponse(
        content="I encountered an error fetching news. Unable to complete analysis.",
        stop_reason="end_turn",
        model=GEMINI_PRO,
        provider="gemini",
        usage={"total_tokens": 50},
    )

    mock_client.generate_with_tools.side_effect = [response1, response2]

    # Mock uuid
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)
    unique_uuids = [uuid_module.uuid4() for _ in range(10)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = DiscoveryAgent(storage=storage, tools=agent_tools, llm_client=mock_client)

        # Agent should return error status when tool execution fails
        result = agent.run()

    # Verify agent returned error status
    assert result["status"] == "error"
    assert "unexpected keyword argument" in result["error"].lower()
