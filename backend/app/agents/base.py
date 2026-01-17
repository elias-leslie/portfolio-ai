"""Base agent class for portfolio-ai agents.

This module provides the base Agent class that all agents inherit from.
The implementation is split across several mixin modules for maintainability:
- persistence.py: Database recording (runs, tool calls, messages)
- response_processing.py: Token extraction and usage tracking
- completion_handler.py: Run completion handling (success, error, max iterations)
- tool_executor.py: Tool execution and recording
- tool_formatting.py: Tool result formatting
- llm_flow.py: LLM client conversation flow (via Agent Hub)
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

from ..constants import CLAUDE_SONNET
from ..logging_config import get_logger
from ..repositories import AgentRunRepository
from .completion_handler import CompletionHandlerMixin
from .llm_client import LLMClient
from .llm_flow import LLMFlowMixin
from .persistence import AgentPersistenceMixin
from .response_processing import ResponseProcessingMixin
from .tool_executor import ToolExecutorMixin
from .tool_formatting import ToolFormattingMixin
from .types import AgentRunStatus, ToolInputDict

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)

# Re-export constants for backwards compatibility
MAX_LLM_TOKENS = 4096
TOOL_RESULT_TRUNCATE = 10000
RESULT_SUMMARY_LENGTH = 500


class ToolCallRecord(TypedDict):
    """Record of a tool call made by the agent."""

    name: str
    input: ToolInputDict
    result: object


class AgentRunResult(TypedDict, total=False):
    """Result of an agent run."""

    status: str
    response: str
    tool_calls: list[ToolCallRecord]
    iterations: int
    error: str
    run_id: str


class ToolExecutionResult(TypedDict):
    """Result of executing and recording a tool call."""

    result: object
    duration_ms: int


class Agent(
    ABC,
    AgentPersistenceMixin,
    ResponseProcessingMixin,
    CompletionHandlerMixin,
    ToolExecutorMixin,
    ToolFormattingMixin,
    LLMFlowMixin,
):
    """Base class for AI agents.

    Provides common functionality for tool calling, execution tracking,
    and LLM client integration via Agent Hub. Implementation is split across
    mixins for maintainability.

    All LLM requests go through Agent Hub service.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        llm_client: LLMClient,
        model: str = CLAUDE_SONNET,
        repository: AgentRunRepository | None = None,
    ) -> None:
        """Initialize agent.

        Args:
            storage: PortfolioStorage instance
            llm_client: LLM client (routes to Agent Hub)
            model: Claude model to use
            repository: AgentRunRepository instance (auto-created if not provided)
        """
        self.storage = storage
        self.llm_client = llm_client
        self.model = model
        self.agent_type = self.__class__.__name__
        self.repository = repository or AgentRunRepository(storage)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def get_tools(self) -> list[dict[str, object]]:
        """Get tool definitions for this agent.

        Returns:
            List of tool definition dicts for Claude API
        """
        pass

    @abstractmethod
    def execute_tool(self, tool_name: str, tool_input: ToolInputDict) -> object:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Tool parameters

        Returns:
            Tool execution result
        """
        pass

    def run(self, user_prompt: str, max_iterations: int = 10) -> AgentRunResult:
        """Run the agent with a user prompt.

        Args:
            user_prompt: User's prompt/request
            max_iterations: Maximum tool call iterations

        Returns:
            Dict with final response and metadata
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        provider = "agent_hub"
        model = self.model

        logger.info(
            "agent_run_started",
            run_id=run_id,
            agent_type=self.agent_type,
            provider=provider,
            model=model,
            max_iterations=max_iterations,
        )

        self._record_run_start(run_id, started_at, provider=provider, model=model)

        try:
            return self._run_with_llm_client(run_id, started_at, user_prompt, max_iterations)

        except Exception as e:
            logger.error(f"Agent run {run_id} failed: {e}")
            self._record_run_complete(
                run_id, datetime.now(UTC), AgentRunStatus.ERROR.value, 0, str(e)
            )
            return {"status": AgentRunStatus.ERROR.value, "error": str(e), "run_id": run_id}
