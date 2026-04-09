"""Integration tests for workflow persistence (database writes).

Tests verify that agent_workflows and agent_messages tables are populated correctly.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest

from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.storage.facade import PortfolioStorage


@pytest.fixture
def storage() -> PortfolioStorage:
    """Provide database storage connection."""
    return PortfolioStorage()


@pytest.fixture(autouse=True)
def clean_workflow_tables(storage: PortfolioStorage) -> Generator[None]:
    """Clean workflow tables before each test."""
    with storage.connection() as conn:
        conn.execute("TRUNCATE agent_messages, agent_workflows CASCADE")
    yield
    # Cleanup after test
    with storage.connection() as conn:
        conn.execute("TRUNCATE agent_messages, agent_workflows CASCADE")


def test_workflow_creation_with_multiple_agents(storage: PortfolioStorage) -> None:
    """Test that workflow creation correctly stores agents_involved as PostgreSQL array.

    This test verifies the fix for the database bug where agents_involved was
    being stored as a CSV string instead of a proper PostgreSQL array.
    """
    # Create workflow with multiple agents
    orchestrator = WorkflowOrchestrator(storage)
    agents = ["gemini", "claude"]

    result = orchestrator.start_workflow(
        workflow_type="test_workflow",
        agents_involved=agents,
        triggered_by="test",
    )

    workflow_id: str = str(result["workflow_id"])

    # Verify workflow was created
    with storage.connection() as conn:
        db_result = conn.execute(
            "SELECT id, workflow_type, status, agents_involved FROM agent_workflows WHERE id = $1",
            [workflow_id],
        ).fetchone()

    assert db_result is not None, "Workflow should be created in database"
    # fetchone() returns tuple: (id, workflow_type, status, agents_involved)
    db_id, db_workflow_type, db_status, db_agents_involved = db_result

    assert db_id == workflow_id
    assert db_workflow_type == "test_workflow"
    assert db_status == "pending"

    # CRITICAL: Verify agents_involved is a proper PostgreSQL array with 2 elements
    assert isinstance(db_agents_involved, list), (
        f"agents_involved should be list, got {type(db_agents_involved)}"
    )
    assert len(db_agents_involved) == 2, (
        f"Should have 2 agents, got {len(db_agents_involved)}: {db_agents_involved}"
    )
    assert "gemini" in db_agents_involved, f"Should contain 'gemini', got {db_agents_involved}"
    assert "claude" in db_agents_involved, f"Should contain 'claude', got {db_agents_involved}"


def test_workflow_creation_with_single_agent(storage: PortfolioStorage) -> None:
    """Test that workflow creation works with a single agent."""
    orchestrator = WorkflowOrchestrator(storage)

    result = orchestrator.start_workflow(
        workflow_type="test_single_agent",
        agents_involved=["gemini"],
        triggered_by="test",
    )

    workflow_id: str = str(result["workflow_id"])

    with storage.connection() as conn:
        db_result = conn.execute(
            "SELECT agents_involved FROM agent_workflows WHERE id = $1", [workflow_id]
        ).fetchone()

    assert db_result is not None
    (agents_involved,) = db_result  # Unpack single-column result
    assert isinstance(agents_involved, list)
    assert len(agents_involved) == 1
    assert agents_involved[0] == "gemini"


def test_workflow_creation_with_no_agents(storage: PortfolioStorage) -> None:
    """Test that workflow creation handles empty agent list."""
    orchestrator = WorkflowOrchestrator(storage)

    result = orchestrator.start_workflow(
        workflow_type="test_no_agents",
        agents_involved=[],
        triggered_by="test",
    )

    workflow_id: str = str(result["workflow_id"])

    with storage.connection() as conn:
        db_result = conn.execute(
            "SELECT agents_involved FROM agent_workflows WHERE id = $1", [workflow_id]
        ).fetchone()

    assert db_result is not None
    (agents_involved,) = db_result
    assert isinstance(agents_involved, list)
    assert len(agents_involved) == 0


def test_workflow_shared_context_storage(storage: PortfolioStorage) -> None:
    """Test that shared_context is stored as valid JSONB."""
    orchestrator = WorkflowOrchestrator(storage)

    config: dict[str, object] = {"test_param": "value", "metadata": {"test": True}}

    result = orchestrator.start_workflow(
        workflow_type="test_context",
        config=config,
        agents_involved=["gemini", "claude"],
        triggered_by="test",
    )

    workflow_id: str = str(result["workflow_id"])

    with storage.connection() as conn:
        db_result = conn.execute(
            "SELECT shared_context FROM agent_workflows WHERE id = $1", [workflow_id]
        ).fetchone()

    assert db_result is not None
    (stored_context,) = db_result
    assert isinstance(stored_context, dict)
    # Check that config was embedded in shared_context
    assert "config" in stored_context
    assert stored_context["config"] == config


def test_workflow_update_status(storage: PortfolioStorage) -> None:
    """Test that workflow status updates work correctly."""
    orchestrator = WorkflowOrchestrator(storage)

    result = orchestrator.start_workflow(
        workflow_type="test_update",
        agents_involved=["gemini"],
        triggered_by="test",
    )

    workflow_id = result["workflow_id"]
    assert isinstance(workflow_id, str)

    # Update status
    orchestrator.update_workflow_status(
        workflow_id=workflow_id, status="running", current_step="executing"
    )

    with storage.connection() as conn:
        db_result = conn.execute(
            "SELECT status, current_step FROM agent_workflows WHERE id = $1", [workflow_id]
        ).fetchone()

    assert db_result is not None
    db_status, db_current_step = db_result
    assert db_status == "running"
    assert db_current_step == "executing"


def test_workflow_fail_persists_status_and_error(storage: PortfolioStorage) -> None:
    """Failing a workflow should persist the failed state and error text."""
    orchestrator = WorkflowOrchestrator(storage)

    result = orchestrator.start_workflow(
        workflow_type="test_fail",
        agents_involved=["gemini"],
        triggered_by="test",
    )

    workflow_id = result["workflow_id"]
    assert isinstance(workflow_id, str)

    fail_result = orchestrator.fail_workflow(
        workflow_id=workflow_id,
        error="simulated failure",
        retry=False,
    )

    assert fail_result["status"] == "failed"

    with storage.connection() as conn:
        db_result = conn.execute(
            "SELECT status, error, completed_at FROM agent_workflows WHERE id = $1",
            [workflow_id],
        ).fetchone()

    assert db_result is not None
    db_status, db_error, completed_at = db_result
    assert db_status == "failed"
    assert db_error == "simulated failure"
    assert completed_at is not None


def test_agent_message_storage(storage: PortfolioStorage) -> None:
    """Test that agent messages are stored correctly in agent_messages table."""
    from app.agents.tool_executors_collaboration import CollaborationTools

    tools = CollaborationTools(storage)
    agent_run_id = str(uuid.uuid4())

    # Send message from gemini to claude
    result = tools.execute_send_message_to_agent(
        agent_run_id=agent_run_id,
        agent_type="claude",
        message_type="question",
        message="What do you think about AAPL?",
        data={"question": "What do you think about AAPL?", "context": "earnings analysis"},
        priority=5,
    )

    assert result["status"] == "sent"
    message_id: str = str(result["message_id"])

    # Verify message was stored
    with storage.connection() as conn:
        msg_result = conn.execute(
            "SELECT from_agent_run_id, to_agent_type, message_type, status, priority, content FROM agent_messages WHERE id = $1",
            [message_id],
        ).fetchone()

    assert msg_result is not None
    (from_agent_run_id, to_agent_type, message_type, status, priority, content) = msg_result

    assert from_agent_run_id == agent_run_id
    assert to_agent_type == "claude"
    assert message_type == "question"
    assert status == "pending"
    assert priority == 5

    # Verify content is valid JSON
    assert isinstance(content, dict)
    assert content["message"] == "What do you think about AAPL?"
    assert content["data"]["question"] == "What do you think about AAPL?"
    assert content["data"]["context"] == "earnings analysis"
