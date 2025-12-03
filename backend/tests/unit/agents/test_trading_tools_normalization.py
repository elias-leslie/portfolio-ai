from unittest.mock import MagicMock

import pytest

from app.agents.tool_executors_trading import TradingTools


@pytest.fixture
def mock_storage():
    return MagicMock()

def test_execute_store_idea_normalization(mock_storage):
    tools = TradingTools(mock_storage)

    # Test case 1: Score > 1.0 (e.g., 70)
    tools.execute_store_idea(
        agent_run_id="run-123",
        title="Test Idea",
        thesis="Test Thesis",
        action="buy",
        confidence_score=70.0,
        risk_level="medium",
        reward_estimate=10.0,
        portfolio_impact=5.0,
        data_needed="None",
        risks="None"
    )

    # Verify stored value is 0.7
    call_args = mock_storage.insert_dict.call_args
    assert call_args is not None
    stored_data = call_args[0][1]
    assert stored_data["confidence_score"] == 0.7

    # Test case 2: Score <= 1.0 (e.g., 0.8)
    tools.execute_store_idea(
        agent_run_id="run-123",
        title="Test Idea 2",
        thesis="Test Thesis 2",
        action="buy",
        confidence_score=0.8,
        risk_level="medium",
        reward_estimate=10.0,
        portfolio_impact=5.0,
        data_needed="None",
        risks="None"
    )

    # Verify stored value is 0.8
    call_args = mock_storage.insert_dict.call_args
    stored_data = call_args[0][1]
    assert stored_data["confidence_score"] == 0.8
