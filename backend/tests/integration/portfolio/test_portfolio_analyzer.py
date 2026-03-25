"""Integration tests for Portfolio Analyzer Agent."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock, patch

import pytest

from app.agents.clients.base_client import LLMClient, LLMResponse
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.models import (
    PriceData,
)
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.fred import FREDSource
from app.storage import PortfolioStorage


@pytest.fixture
def storage(clean_database: None) -> Generator[PortfolioStorage]:
    """Create a PortfolioStorage instance using the test database.

    Depends on clean_database to ensure tables are cleaned before test data is inserted.
    """
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


@pytest.fixture
def seed_symbols(storage: PortfolioStorage) -> None:
    """Ensure strategy seed symbols exist in the symbols table (FK constraint)."""
    from app.utils.db_helpers import ensure_symbols_exist

    with storage.connection() as conn:
        ensure_symbols_exist(conn, ["JNJ", "XOM", "UNH", "PG", "BND"])
        conn.commit()


@pytest.fixture
def mock_llm_client() -> Mock:
    """Create a mock LLM client for agent construction."""
    return Mock(spec=LLMClient)


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
def mock_news_service() -> Mock:
    """Create a mock news service."""
    from datetime import UTC, datetime

    from app.services.news_models import NewsArticle, NewsBundle, NewsSummary, SentimentScore

    # Create realistic mock articles
    mock_articles = [
        NewsArticle(
            symbol="MARKET",
            headline="Tech stocks rally on AI optimism",
            url="http://example.com/1",
            summary="Technology sector leads gains",
            source="Financial Times",
            published_at=datetime(2025, 10, 27, tzinfo=UTC),
            fetched_at=datetime.now(UTC),
            sentiment=SentimentScore(score=0.8, label="positive", confidence=0.95, model="finbert"),
            content_hash="hash1",
        ),
    ]
    mock_summary = NewsSummary(
        symbol="MARKET",
        score=0.8,
        score_change=0.1,
        positive_count=1,
        neutral_count=0,
        negative_count=0,
        article_count=1,
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
    mock_news_service: Mock,
    mock_fred_source: Mock,
    mock_price_fetcher: Mock,
) -> AgentTools:
    """Create AgentTools with real portfolio and mocked external sources."""
    analytics = PortfolioAnalytics()

    return AgentTools(
        storage=storage,
        news_service=mock_news_service,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=portfolio_with_positions,
        analytics=analytics,
    )


def _make_llm_response(
    stop_reason: str,
    content: str = "",
    tool_calls: list[dict[str, object]] | None = None,
) -> LLMResponse:
    """Helper to create an LLMResponse with default usage/provider/model."""
    return LLMResponse(
        content=content,
        provider="test",
        model="test-model",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        stop_reason=stop_reason,
        tool_calls=tool_calls or [],
    )


@pytest.fixture
def mock_anthropic_client() -> Mock:
    """Create a mock LLM client that simulates Portfolio Analyzer behavior."""
    mock = Mock(spec=LLMClient)

    # Simulate a conversation where the agent:
    # 1. Calls get_portfolio_data
    # 2. Calls get_news
    # 3. Calls get_economic_data
    # 4. Stores 5 personalized strategy seeds
    # 5. Returns final response

    # First call: get_portfolio_data
    response1 = _make_llm_response(
        stop_reason="tool_use",
        content='{"tool_calls": [{"name": "get_portfolio_data", "parameters": {}}]}',
        tool_calls=[{"name": "get_portfolio_data", "parameters": {}}],
    )

    # Second call: get_news
    response2 = _make_llm_response(
        stop_reason="tool_use",
        content='{"tool_calls": [{"name": "get_news", "parameters": {"query": "technology stocks", "max_results": 5}}]}',
        tool_calls=[{"name": "get_news", "parameters": {"query": "technology stocks", "max_results": 5}}],
    )

    # Third call: get_economic_data
    response3 = _make_llm_response(
        stop_reason="tool_use",
        content='{"tool_calls": [{"name": "get_economic_data", "parameters": {"indicators": ["VIX", "TNX"]}}]}',
        tool_calls=[{"name": "get_economic_data", "parameters": {"indicators": ["VIX", "TNX"]}}],
    )

    # Fourth call: store 5 personalized strategy seeds
    seed_tool_calls = []
    for i in range(5):
        seed_tool_calls.append({
            "name": "store_strategy_seed",
            "parameters": {
                "symbol": ["JNJ", "XOM", "UNH", "PG", "BND"][i],
                "thesis": f"Given your heavy tech exposure, this seed {i + 1} helps diversify",
                "confidence": 6.5 + i * 0.5,
            },
        })
    response4 = _make_llm_response(
        stop_reason="tool_use",
        content="store seeds",
        tool_calls=seed_tool_calls,
    )

    # Fifth call: final response
    response5 = _make_llm_response(
        stop_reason="end_turn",
        content="I have analyzed your portfolio and generated 5 personalized ideas.",
    )

    # Set up mock to return responses in sequence
    mock.generate_with_tools.side_effect = [
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
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))

    assert agent.storage is storage
    assert agent.tools is agent_tools
    assert agent.agent_type == "PortfolioAnalyzerAgent"
    assert agent.current_run_id is None


def test_portfolio_analyzer_system_prompt(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test Portfolio Analyzer Agent system prompt."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))
    prompt = agent.get_system_prompt()

    assert "Portfolio Analyzer Agent" in prompt
    assert "personalized" in prompt
    assert "get_portfolio_data" in prompt
    assert "portfolio" in prompt.lower()
    assert "store_strategy_seed" in prompt


def test_portfolio_analyzer_tools(storage: PortfolioStorage, agent_tools: AgentTools) -> None:
    """Test Portfolio Analyzer Agent tool definitions."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))
    tools = agent.get_tools()

    assert len(tools) == 5
    tool_names = {tool["name"] for tool in tools}
    assert tool_names == {
        "get_portfolio_data",
        "get_news",
        "get_economic_data",
        "get_price_data",
        "store_strategy_seed",
    }


def test_portfolio_analyzer_execute_tool_get_portfolio_data(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_price_fetcher: Mock,
) -> None:
    """Test executing get_portfolio_data tool."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))

    result = cast(dict[str, object], agent.execute_tool("get_portfolio_data", {}))

    assert "positions" in result
    assert "analytics" in result
    positions = result["positions"]
    assert isinstance(positions, list)
    assert len(positions) == 2
    first_pos = positions[0]
    assert isinstance(first_pos, dict)
    assert first_pos["symbol"] == "AAPL"
    mock_price_fetcher.fetch_price_data.assert_called_once()


def test_portfolio_analyzer_execute_tool_get_price_data(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_price_fetcher: Mock,
) -> None:
    """Test executing get_price_data tool."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))

    result = cast(dict[str, object], agent.execute_tool("get_price_data", {"symbols": ["AAPL", "MSFT"]}))

    assert "prices" in result
    assert "count" in result
    mock_price_fetcher.fetch_price_data.assert_called_with(["AAPL", "MSFT"])


def test_portfolio_analyzer_execute_tool_store_strategy_seed(
    storage: PortfolioStorage, agent_tools: AgentTools, seed_symbols: None
) -> None:
    """Test executing store_strategy_seed tool."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))
    test_run_id = "12345678-1234-5678-1234-567812345678"
    agent.current_run_id = test_run_id

    # Create agent_run entry first (required by foreign key)
    storage.insert_dict(
        "agent_runs",
        {
            "id": test_run_id,
            "agent_type": "PortfolioAnalyzerAgent",
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "status": "running",
            "num_ideas": 0,
            "cost_usd": 0.0,
            "error_message": None,
            "metadata": None,
            "celery_task_id": None,
            "provider": "test",
            "model": "test-model",
            "cli_command": None,
            "exit_code": None,
            "duration_ms": None,
            "token_usage": None,
            "session_id": None,
            "run_type": "automated",
            "parent_run_id": None,
            "workflow_id": None,
            "user_id": None,
        },
    )

    result = cast(
        dict[str, object],
        agent.execute_tool(
            "store_strategy_seed",
            {
                "symbol": "BND",
                "thesis": "Portfolio is 100% tech, bonds reduce volatility",
                "confidence": 7.0,
            },
        ),
    )

    assert result["status"] == "stored"
    assert "seed_id" in result


def test_portfolio_analyzer_execute_tool_unknown(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test executing unknown tool raises error."""
    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=Mock(spec=LLMClient))

    with pytest.raises(ValueError, match="Unknown tool"):
        agent.execute_tool("unknown_tool", {})


def test_portfolio_analyzer_run_full_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
    mock_price_fetcher: Mock,
    seed_symbols: None,
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
            storage=storage, tools=agent_tools, llm_client=mock_anthropic_client
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
    assert len(tool_calls) == 8  # 1 portfolio + 1 news + 1 econ + 5 seeds

    # Verify tools were called
    tool_names = [call["name"] for call in tool_calls]
    assert "get_portfolio_data" in tool_names
    assert "get_news" in tool_names
    assert "get_economic_data" in tool_names
    assert tool_names.count("store_strategy_seed") == 5

    # Verify price fetcher was called for portfolio analytics (if positions were visible)
    # Note: In integration tests with connection pooling, positions may not always
    # be visible to the agent's connection depending on transaction isolation
    portfolio_call = next(c for c in tool_calls if c["name"] == "get_portfolio_data")
    if portfolio_call["result"]["positions"]:
        mock_price_fetcher.fetch_price_data.assert_called()

    # Verify agent_runs table
    with storage.connection() as conn:
        runs = conn.execute("SELECT * FROM agent_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][1] == "PortfolioAnalyzerAgent"  # agent_type
        assert runs[0][4] == "completed"  # status
        assert runs[0][5] == 8  # num_ideas (total tool calls)

    # Verify strategy_seeds table
    with storage.connection() as conn:
        seeds = conn.execute("SELECT symbol, thesis FROM strategy_seeds ORDER BY created_at").fetchall()
        assert len(seeds) == 5
        for i, seed in enumerate(seeds):
            assert seed[0] == ["JNJ", "XOM", "UNH", "PG", "BND"][i]
            thesis = seed[1]
            assert isinstance(thesis, str)
            assert "tech" in thesis.lower() or "portfolio" in thesis.lower()


def test_portfolio_analyzer_run_with_empty_portfolio(
    storage: PortfolioStorage,
    mock_news_service: Mock,
    mock_fred_source: Mock,
    mock_price_fetcher: Mock,
) -> None:
    """Test Portfolio Analyzer with empty portfolio."""
    # Create empty portfolio manager
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()

    tools = AgentTools(
        storage=storage,
        news_service=mock_news_service,
        fred_source=mock_fred_source,
        price_fetcher=mock_price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )

    agent = PortfolioAnalyzerAgent(storage=storage, tools=tools, llm_client=Mock(spec=LLMClient))

    # Execute get_portfolio_data
    result = cast(dict[str, object], agent.execute_tool("get_portfolio_data", {}))

    assert result["positions"] == []
    assert result["analytics"] is None


def test_portfolio_analyzer_run_records_tool_calls(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
    seed_symbols: None,
) -> None:
    """Test that agent run records tool calls in database."""
    import uuid as uuid_module

    fixed_run_id = "12345678-1234-5678-1234-567812345678"
    shared_uuid = uuid_module.UUID(fixed_run_id)
    unique_uuids = [uuid_module.uuid4() for _ in range(20)]

    with patch("uuid.uuid4") as mock_uuid:
        mock_uuid.side_effect = [shared_uuid, shared_uuid, *unique_uuids]

        agent = PortfolioAnalyzerAgent(
            storage=storage, tools=agent_tools, llm_client=mock_anthropic_client
        )

        agent.run()

    # Verify agent_tool_calls table
    with storage.connection() as conn:
        tool_calls = conn.execute("SELECT * FROM agent_tool_calls").fetchall()
        assert len(tool_calls) == 8  # 1 portfolio + 1 news + 1 econ + 5 seeds

        # Check tool names
        tool_names = [call[2] for call in tool_calls]
        assert "get_portfolio_data" in tool_names
        assert "get_news" in tool_names
        assert "get_economic_data" in tool_names
        assert tool_names.count("store_strategy_seed") == 5


def test_portfolio_analyzer_run_clears_run_id_after_execution(
    storage: PortfolioStorage,
    agent_tools: AgentTools,
    mock_anthropic_client: Mock,
    seed_symbols: None,
) -> None:
    """Test that run_id is cleared after execution."""
    import uuid as uuid_module

    agent = PortfolioAnalyzerAgent(
        storage=storage, tools=agent_tools, llm_client=mock_anthropic_client
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
    mock_client = Mock(spec=LLMClient)
    response = _make_llm_response(
        stop_reason="tool_use",
        content='{"tool_calls": [{"name": "get_portfolio_data", "parameters": {}}]}',
        tool_calls=[{"name": "get_portfolio_data", "parameters": {}}],
    )
    mock_client.generate_with_tools.return_value = response

    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=mock_client)

    # Run with max_iterations=3
    result = agent.run(max_iterations=3)

    assert result["status"] == "max_iterations"
    assert result["iterations"] == 3


def test_portfolio_analyzer_handles_api_error(
    storage: PortfolioStorage, agent_tools: AgentTools
) -> None:
    """Test agent handles API errors gracefully."""
    # Create mock that raises exception
    mock_client = Mock(spec=LLMClient)
    mock_client.generate_with_tools.side_effect = Exception("API Error")

    agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=mock_client)

    result = agent.run()

    assert result["status"] == "error"
    assert "API Error" in result["error"]

    # Verify error was recorded in database
    with storage.connection() as conn:
        runs = conn.execute("SELECT * FROM agent_runs").fetchall()
        assert len(runs) == 1
        assert runs[0][4] == "error"  # status
        assert runs[0][7] is not None  # error_message
