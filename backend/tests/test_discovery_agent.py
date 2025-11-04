"""Integration tests for Discovery Agent."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.agents.discovery import DiscoveryAgent
from app.agents.tools import AgentTools
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.fred import FREDSource
from app.sources.news import GoogleNewsSource
from app.storage import PortfolioStorage


@pytest.fixture
def storage() -> PortfolioStorage:
    """Create a PortfolioStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.duckdb"

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
def mock_news_source() -> Mock:
    """Create a mock news source."""
    mock = Mock(spec=GoogleNewsSource)
    mock.fetch_headlines.return_value = [
        {
            "title": "Stock market reaches new highs",
            "link": "http://example.com/1",
            "published": "2025-10-27",
            "summary": "Markets rally on strong earnings",
            "source": "Financial Times",
        },
        {
            "title": "Tech sector leads gains",
            "link": "http://example.com/2",
            "published": "2025-10-27",
            "summary": "Technology stocks surge",
            "source": "Bloomberg",
        },
    ]
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
    mock_news_source: Mock,
    mock_fred_source: Mock,
) -> AgentTools:
    """Create AgentTools with mocked external sources."""
    # Create real components
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()

    # Mock price fetcher (not used by Discovery Agent)
    mock_price_fetcher = Mock(spec=PriceDataFetcher)

    return AgentTools(
        storage=storage,
        news_source=mock_news_source,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )


@pytest.fixture
def mock_anthropic_client() -> Mock:
    """Create a mock Anthropic client that simulates agent behavior."""
    mock = Mock()

    # Simulate a conversation where the agent:
    # 1. Calls get_news
    # 2. Calls get_economic_data
    # 3. Stores 5 ideas
    # 4. Returns final response

    # First call: agent requests to use get_news tool
    response1 = Mock()
    response1.stop_reason = "tool_use"
    block1 = Mock()
    block1.type = "tool_use"
    block1.id = "tool_1"
    block1.name = "get_news"
    block1.input = {"query": "stock market", "max_results": 10}
    response1.content = [block1]

    # Second call: agent requests to use get_economic_data tool
    response2 = Mock()
    response2.stop_reason = "tool_use"
    block2 = Mock()
    block2.type = "tool_use"
    block2.id = "tool_2"
    block2.name = "get_economic_data"
    block2.input = {"indicators": ["VIX", "TNX"]}
    response2.content = [block2]

    # Third call: agent stores 5 ideas
    response3 = Mock()
    response3.stop_reason = "tool_use"
    ideas = []
    for i in range(5):
        block = Mock()
        block.type = "tool_use"
        block.id = f"tool_idea_{i}"
        block.name = "store_idea"
        block.input = {
            "title": f"Investment Idea {i + 1}",
            "thesis": f"This is investment thesis {i + 1} based on market analysis",
            "action": f"Buy {['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'][i]}",
            "idea_type": "long",
            "confidence_score": 70 + i * 5,
            "risk_level": "medium",
            "reward_estimate": "10-15%",
            "portfolio_impact": "Adds tech exposure",
            "risks": "Market volatility",
        }
        ideas.append(block)
    response3.content = ideas

    # Fourth call: agent returns final text response
    response4 = Mock()
    response4.stop_reason = "end_turn"
    final_block = Mock()
    final_block.type = "text"
    final_block.text = "I have analyzed the market and generated 5 investment ideas."
    response4.content = [final_block]

    # Set up mock to return responses in sequence
    mock.messages.create.side_effect = [response1, response2, response3, response4]

    return mock


def test_discovery_agent_initialization(storage: PortfolioStorage, agent_tools: AgentTools) -> None:
    """Test Discovery Agent initialization."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)

    assert agent.storage is storage
    assert agent.tools is agent_tools
    assert agent.agent_type == "DiscoveryAgent"
    assert agent.current_run_id is None


def test_discovery_agent_system_prompt(storage: PortfolioStorage, agent_tools: AgentTools) -> None:
    """Test Discovery Agent system prompt."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)
    prompt = agent.get_system_prompt()

    assert "Discovery Agent" in prompt
    assert "investment ideas" in prompt
    assert "get_news" in prompt
    assert "get_economic_data" in prompt
    assert "store_idea" in prompt


def test_discovery_agent_tools(storage: PortfolioStorage, agent_tools: AgentTools) -> None:
    """Test Discovery Agent tool definitions."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)
    tools = agent.get_tools()

    assert len(tools) == 3
    tool_names = {tool["name"] for tool in tools}
    assert tool_names == {"get_news", "get_economic_data", "store_idea"}


def test_discovery_agent_execute_tool_get_news(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_news_source: Mock,
) -> None:
    """Test executing get_news tool."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)

    result = agent.execute_tool("get_news", {"query": "technology", "max_results": 5})

    assert "headlines" in result
    assert "count" in result
    mock_news_source.fetch_headlines.assert_called_once_with("technology", 5)


def test_discovery_agent_execute_tool_get_economic_data(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_fred_source: Mock,
) -> None:
    """Test executing get_economic_data tool."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)

    result = agent.execute_tool("get_economic_data", {"indicators": ["VIX", "FEDFUNDS"]})

    assert "indicators" in result
    assert "count" in result
    mock_fred_source.fetch_multiple.assert_called_once_with(["VIX", "FEDFUNDS"])


def test_discovery_agent_execute_tool_store_idea(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test executing store_idea tool."""
    from datetime import datetime

    agent = DiscoveryAgent(storage=storage, tools=agent_tools)
    agent.current_run_id = "test-run-id"

    # Create agent_run entry first (required by foreign key)
    storage.insert_dict(
        "agent_runs",
        {
            "id": "test-run-id",
            "agent_type": "DiscoveryAgent",
            "started_at": datetime.now(),
            "completed_at": None,
            "status": "running",
            "num_ideas": 0,
            "cost_usd": 0.0,
            "error_message": None,
            "metadata": None,
            "celery_task_id": None,
        },
    )

    result = agent.execute_tool(
        "store_idea",
        {
            "title": "Buy tech stocks",
            "thesis": "Technology sector is undervalued",
            "action": "Buy AAPL calls",
            "idea_type": "option",
            "confidence_score": 75,
            "risk_level": "medium",
        },
    )

    assert result["status"] == "stored"
    assert "idea_id" in result

    # Verify idea was stored in database
    with storage.connection() as conn:
        ideas = conn.execute(
            "SELECT * FROM agent_ideas WHERE agent_run_id = ?", ["test-run-id"]
        ).fetchall()
        assert len(ideas) == 1
        assert ideas[0][2] == "option"  # idea_type column
        assert ideas[0][3] == "Buy tech stocks"  # title column


def test_discovery_agent_execute_tool_store_idea_without_run_id(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test store_idea fails without active run_id."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)
    agent.current_run_id = None

    with pytest.raises(ValueError, match="No active run_id"):
        agent.execute_tool(
            "store_idea",
            {
                "title": "Test",
                "thesis": "Test",
                "action": "Test",
                "idea_type": "long",
                "confidence_score": 50,
                "risk_level": "low",
            },
        )


def test_discovery_agent_execute_tool_unknown(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test executing unknown tool raises error."""
    agent = DiscoveryAgent(storage=storage, tools=agent_tools)

    with pytest.raises(ValueError, match="Unknown tool"):
        agent.execute_tool("unknown_tool", {})


def test_discovery_agent_run_full_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
    mock_news_source: Mock,
    mock_fred_source: Mock,
) -> None:
    """Test full Discovery Agent execution with mocked Claude API."""
    import uuid as uuid_module

    # Mock uuid to return same ID for both current_run_id and run_id
    # but different IDs for tool call IDs
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        # Return the same UUID object for the first two calls (Discovery and base Agent)
        # Then return unique UUIDs for idea IDs and tool call IDs
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = DiscoveryAgent(
            storage=storage, tools=agent_tools, anthropic_client=mock_anthropic_client
        )

        # Run the agent
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
        assert runs[0][4] == "completed"  # status (column 4, not 3)
        # Note: base Agent records total tool calls in num_ideas field, not just store_idea calls
        assert runs[0][5] == 7  # num_ideas actually stores total tool call count

    # Verify agent_ideas table
    with storage.connection() as conn:
        ideas = conn.execute("SELECT * FROM agent_ideas").fetchall()
        assert len(ideas) == 5
        for i, idea in enumerate(ideas):
            assert idea[3] == f"Investment Idea {i + 1}"  # title (column 3, not 4)


def test_discovery_agent_run_records_tool_calls(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
) -> None:
    """Test that agent run records tool calls in database."""
    import uuid as uuid_module

    # Mock uuid to return same ID for both current_run_id and run_id
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        # Return the same UUID object for the first two calls
        # Then return unique UUIDs for idea IDs and tool call IDs
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = DiscoveryAgent(
            storage=storage, tools=agent_tools, anthropic_client=mock_anthropic_client
        )

        agent.run()

    # Verify agent_tool_calls table
    with storage.connection() as conn:
        tool_calls = conn.execute("SELECT * FROM agent_tool_calls").fetchall()
        assert len(tool_calls) == 7  # 1 news + 1 econ + 5 ideas

        # Check tool names
        tool_names = [call[2] for call in tool_calls]  # tool_name column (col 2)
        assert "get_news" in tool_names
        assert "get_economic_data" in tool_names
        assert tool_names.count("store_idea") == 5

        # Verify each tool call has required fields
        for call in tool_calls:
            assert call[0] is not None  # id
            assert call[1] is not None  # agent_run_id
            assert call[2] is not None  # tool_name
            assert call[3] is not None  # parameters (JSON)
            # response_summary (col 4) may be None for some tools
            # duration_ms (col 5) should exist
            assert call[6] is not None  # called_at


def test_discovery_agent_run_clears_run_id_after_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
) -> None:
    """Test that run_id is cleared after execution."""
    import uuid as uuid_module

    agent = DiscoveryAgent(
        storage=storage, tools=agent_tools, anthropic_client=mock_anthropic_client
    )

    # Before run
    assert agent.current_run_id is None

    # Mock uuid to return same ID for both current_run_id and run_id
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)

    # Generate unique UUIDs before patching
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]
        # Run
        agent.run()

    # After run
    assert agent.current_run_id is None


def test_discovery_agent_handles_max_iterations(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test agent respects max_iterations limit."""
    # Create mock that never stops
    mock_client = Mock()
    response = Mock()
    response.stop_reason = "tool_use"
    block = Mock()
    block.type = "tool_use"
    block.id = "tool_1"
    block.name = "get_news"
    block.input = {"query": "test"}
    response.content = [block]
    mock_client.messages.create.return_value = response

    agent = DiscoveryAgent(storage=storage, tools=agent_tools, anthropic_client=mock_client)

    # Run with max_iterations=3
    result = agent.run(max_iterations=3)

    assert result["status"] == "max_iterations"
    assert result["iterations"] == 3


def test_discovery_agent_handles_api_error(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test agent handles API errors gracefully."""
    # Create mock that raises exception
    mock_client = Mock()
    mock_client.messages.create.side_effect = Exception("API Error")

    agent = DiscoveryAgent(storage=storage, tools=agent_tools, anthropic_client=mock_client)

    result = agent.run()

    assert result["status"] == "error"
    assert "API Error" in result["error"]

    # Verify error was recorded in database
    with storage.connection() as conn:
        runs = conn.execute("SELECT * FROM agent_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][4] == "error"  # status (column 4)
        assert runs[0][7] is not None  # error_message (column 7)
