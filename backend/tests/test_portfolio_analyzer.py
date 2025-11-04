"""Integration tests for Portfolio Analyzer Agent."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.models import (
    PriceData,
)
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
def portfolio_with_positions(storage: PortfolioStorage) -> PortfolioManager:
    """Create a portfolio manager with test positions."""
    portfolio_mgr = PortfolioManager(storage)

    # Add account
    account = portfolio_mgr.add_account("Test Account", "Taxable")

    # Add positions
    portfolio_mgr.add_position(
        account_id=account.id,
        symbol="AAPL",
        shares=100.0,
        cost_basis=150.0,
        position_type="long",
    )
    portfolio_mgr.add_position(
        account_id=account.id,
        symbol="GOOGL",
        shares=50.0,
        cost_basis=2000.0,
        position_type="long",
    )

    return portfolio_mgr


@pytest.fixture
def mock_news_source() -> Mock:
    """Create a mock news source."""
    mock = Mock(spec=GoogleNewsSource)
    mock.fetch_headlines.return_value = [
        {
            "title": "Tech stocks rally on AI optimism",
            "link": "http://example.com/1",
            "published": "2025-10-27",
            "summary": "Technology sector leads gains",
            "source": "Financial Times",
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
def mock_price_fetcher() -> Mock:
    """Create a mock price fetcher."""
    mock = Mock(spec=PriceDataFetcher)
    mock.fetch_price_data.return_value = {
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
    return mock


@pytest.fixture
def agent_tools(
    storage: PortfolioStorage,
    portfolio_with_positions: PortfolioManager,
    mock_news_source: Mock,
    mock_fred_source: Mock,
    mock_price_fetcher: Mock,
) -> AgentTools:
    """Create AgentTools with real portfolio and mocked external sources."""
    analytics = PortfolioAnalytics()

    return AgentTools(
        storage=storage,
        news_source=mock_news_source,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=portfolio_with_positions,
        analytics=analytics,
    )


@pytest.fixture
def mock_anthropic_client() -> Mock:
    """Create a mock Anthropic client that simulates Portfolio Analyzer behavior."""
    mock = Mock()

    # Simulate a conversation where the agent:
    # 1. Calls get_portfolio_data
    # 2. Calls get_news
    # 3. Calls get_economic_data
    # 4. Stores 5 personalized ideas
    # 5. Returns final response

    # First call: get_portfolio_data
    response1 = Mock()
    response1.stop_reason = "tool_use"
    block1 = Mock()
    block1.type = "tool_use"
    block1.id = "tool_1"
    block1.name = "get_portfolio_data"
    block1.input = {}
    response1.content = [block1]

    # Second call: get_news
    response2 = Mock()
    response2.stop_reason = "tool_use"
    block2 = Mock()
    block2.type = "tool_use"
    block2.id = "tool_2"
    block2.name = "get_news"
    block2.input = {"query": "technology stocks", "max_results": 5}
    response2.content = [block2]

    # Third call: get_economic_data
    response3 = Mock()
    response3.stop_reason = "tool_use"
    block3 = Mock()
    block3.type = "tool_use"
    block3.id = "tool_3"
    block3.name = "get_economic_data"
    block3.input = {"indicators": ["VIX", "TNX"]}
    response3.content = [block3]

    # Fourth call: store 5 personalized ideas
    response4 = Mock()
    response4.stop_reason = "tool_use"
    ideas = []
    for i in range(5):
        block = Mock()
        block.type = "tool_use"
        block.id = f"tool_idea_{i}"
        block.name = "store_idea"
        block.input = {
            "title": f"Portfolio Idea {i + 1}",
            "thesis": f"Given your heavy tech exposure, this idea {i + 1} helps diversify",
            "action": f"Action for idea {i + 1}",
            "idea_type": "long",
            "confidence_score": 65 + i * 5,
            "risk_level": "medium",
            "reward_estimate": "8-12%",
            "portfolio_impact": "Reduces tech concentration, adds diversification",
            "risks": "Market volatility, sector rotation",
        }
        ideas.append(block)
    response4.content = ideas

    # Fifth call: final response
    response5 = Mock()
    response5.stop_reason = "end_turn"
    final_block = Mock()
    final_block.type = "text"
    final_block.text = "I have analyzed your portfolio and generated 5 personalized ideas."
    response5.content = [final_block]

    # Set up mock to return responses in sequence
    mock.messages.create.side_effect = [
        response1,
        response2,
        response3,
        response4,
        response5,
    ]

    return mock


def test_portfolio_analyzer_initialization(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test Portfolio Analyzer Agent initialization."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)

    assert agent.storage is storage
    assert agent.tools is agent_tools
    assert agent.agent_type == "PortfolioAnalyzerAgent"
    assert agent.current_run_id is None


def test_portfolio_analyzer_system_prompt(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test Portfolio Analyzer Agent system prompt."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
    prompt = agent.get_system_prompt()

    assert "Portfolio Analyzer Agent" in prompt
    assert "personalized" in prompt
    assert "get_portfolio_data" in prompt
    assert "portfolio" in prompt.lower()
    assert "store_idea" in prompt


def test_portfolio_analyzer_tools(storage: PortfolioStorage, agent_tools: AgentTools) -> None:
    """Test Portfolio Analyzer Agent tool definitions."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
    tools = agent.get_tools()

    assert len(tools) == 5
    tool_names = {tool["name"] for tool in tools}
    assert tool_names == {
        "get_portfolio_data",
        "get_news",
        "get_economic_data",
        "get_price_data",
        "store_idea",
    }


def test_portfolio_analyzer_execute_tool_get_portfolio_data(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_price_fetcher: Mock,
) -> None:
    """Test executing get_portfolio_data tool."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)

    result = agent.execute_tool("get_portfolio_data", {})

    assert "positions" in result
    assert "analytics" in result
    assert len(result["positions"]) == 2
    assert result["positions"][0]["symbol"] == "AAPL"
    mock_price_fetcher.fetch_price_data.assert_called_once()


def test_portfolio_analyzer_execute_tool_get_price_data(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_price_fetcher: Mock,
) -> None:
    """Test executing get_price_data tool."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)

    result = agent.execute_tool("get_price_data", {"symbols": ["AAPL", "MSFT"]})

    assert "prices" in result
    assert "count" in result
    mock_price_fetcher.fetch_price_data.assert_called_with(["AAPL", "MSFT"])


def test_portfolio_analyzer_execute_tool_store_idea(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test executing store_idea tool."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
    agent.current_run_id = "test-run-id"

    # Create agent_run entry first (required by foreign key)
    storage.insert_dict(
        "agent_runs",
        {
            "id": "test-run-id",
            "agent_type": "PortfolioAnalyzerAgent",
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
            "title": "Diversify into bonds",
            "thesis": "Portfolio is 100% tech, bonds reduce volatility",
            "action": "Buy BND ETF",
            "idea_type": "long",
            "confidence_score": 70,
            "risk_level": "low",
        },
    )

    assert result["status"] == "stored"
    assert "idea_id" in result


def test_portfolio_analyzer_execute_tool_unknown(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test executing unknown tool raises error."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)

    with pytest.raises(ValueError, match="Unknown tool"):
        agent.execute_tool("unknown_tool", {})


def test_portfolio_analyzer_run_full_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
    mock_price_fetcher: Mock,
) -> None:
    """Test full Portfolio Analyzer execution with mocked Claude API."""
    import uuid as uuid_module

    # Generate unique UUIDs before patching
    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = PortfolioAnalyzerAgent(
            storage=storage, tools=agent_tools, anthropic_client=mock_anthropic_client
        )

        # Run the agent
        result = agent.run()

    # Verify result
    assert result["status"] == "completed"
    assert "response" in result
    assert "tool_calls" in result
    assert result["iterations"] == 5

    # Verify tool calls
    tool_calls = result["tool_calls"]
    assert len(tool_calls) == 8  # 1 portfolio + 1 news + 1 econ + 5 ideas

    # Verify tools were called
    tool_names = [call["name"] for call in tool_calls]
    assert "get_portfolio_data" in tool_names
    assert "get_news" in tool_names
    assert "get_economic_data" in tool_names
    assert tool_names.count("store_idea") == 5

    # Verify price fetcher was called for portfolio analytics
    mock_price_fetcher.fetch_price_data.assert_called()

    # Verify agent_runs table
    with storage.connection() as conn:
        runs = conn.execute("SELECT * FROM agent_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][1] == "PortfolioAnalyzerAgent"  # agent_type
        assert runs[0][4] == "completed"  # status
        assert runs[0][5] == 8  # num_ideas (total tool calls)

    # Verify agent_ideas table
    with storage.connection() as conn:
        ideas = conn.execute("SELECT * FROM agent_ideas").fetchall()
        assert len(ideas) == 5
        for i, idea in enumerate(ideas):
            assert idea[3] == f"Portfolio Idea {i + 1}"  # title
            # Verify ideas reference portfolio
            assert "tech" in idea[4].lower() or "portfolio" in idea[4].lower()  # thesis


def test_portfolio_analyzer_run_with_empty_portfolio(
    storage: PortfolioStorage,
    mock_news_source: Mock,
    mock_fred_source: Mock,
    mock_price_fetcher: Mock,
) -> None:
    """Test Portfolio Analyzer with empty portfolio."""
    # Create empty portfolio manager
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()

    tools = AgentTools(
        storage=storage,
        news_source=mock_news_source,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )

    agent = PortfolioAnalyzerAgent(storage=storage, tools=tools)

    # Execute get_portfolio_data
    result = agent.execute_tool("get_portfolio_data", {})

    assert result["positions"] == []
    assert result["analytics"] is None


def test_portfolio_analyzer_run_records_tool_calls(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
) -> None:
    """Test that agent run records tool calls in database."""
    import uuid as uuid_module

    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = PortfolioAnalyzerAgent(
            storage=storage, tools=agent_tools, anthropic_client=mock_anthropic_client
        )

        agent.run()

    # Verify agent_tool_calls table
    with storage.connection() as conn:
        tool_calls = conn.execute("SELECT * FROM agent_tool_calls").fetchall()
        assert len(tool_calls) == 8  # 1 portfolio + 1 news + 1 econ + 5 ideas

        # Check tool names
        tool_names = [call[2] for call in tool_calls]
        assert "get_portfolio_data" in tool_names
        assert "get_news" in tool_names
        assert "get_economic_data" in tool_names
        assert tool_names.count("store_idea") == 5


def test_portfolio_analyzer_run_clears_run_id_after_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
) -> None:
    """Test that run_id is cleared after execution."""
    import uuid as uuid_module

    agent = PortfolioAnalyzerAgent(
        storage=storage, tools=agent_tools, anthropic_client=mock_anthropic_client
    )

    # Before run
    assert agent.current_run_id is None

    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]
        agent.run()

    # After run
    assert agent.current_run_id is None


def test_portfolio_analyzer_handles_max_iterations(
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
    block.name = "get_portfolio_data"
    block.input = {}
    response.content = [block]
    mock_client.messages.create.return_value = response

    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, anthropic_client=mock_client)

    # Run with max_iterations=3
    result = agent.run(max_iterations=3)

    assert result["status"] == "max_iterations"
    assert result["iterations"] == 3


def test_portfolio_analyzer_handles_api_error(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test agent handles API errors gracefully."""
    # Create mock that raises exception
    mock_client = Mock()
    mock_client.messages.create.side_effect = Exception("API Error")

    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, anthropic_client=mock_client)

    result = agent.run()

    assert result["status"] == "error"
    assert "API Error" in result["error"]

    # Verify error was recorded in database
    with storage.connection() as conn:
        runs = conn.execute("SELECT * FROM agent_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][4] == "error"  # status
        assert runs[0][7] is not None  # error_message
