"""Base agent class for portfolio-ai agents.

This module provides the base Agent class that all agents inherit from.
The implementation is split across several mixin modules for maintainability:
- persistence.py: Database recording (runs, tool calls, messages)
- response_processing.py: Token extraction and usage tracking
- completion_handler.py: Run completion handling (success, error, max iterations)
- tool_executor.py: Tool execution and recording
- tool_formatting.py: Tool result formatting
- llm_flow.py: LLM client conversation flow
- anthropic_flow.py: Anthropic API conversation flow (legacy)
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict

from anthropic import Anthropic

from ..logging_config import get_logger
from ..repositories import AgentRunRepository
from .anthropic_flow import AnthropicFlowMixin
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
    AnthropicFlowMixin,
):
    """Base class for AI agents.

    Provides common functionality for tool calling, execution tracking,
    and interaction with Claude API. Implementation is split across mixins
    for maintainability.

    Mixin order matters - later mixins can override earlier ones.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        llm_client: LLMClient | None = None,
        anthropic_client: Anthropic | None = None,
        model: str = "claude-sonnet-4-5",
        repository: AgentRunRepository | None = None,
    ) -> None:
        """Initialize agent.

        Args:
            storage: PortfolioStorage instance
            llm_client: LLM client (DualProviderClient for CLI providers)
            anthropic_client: Anthropic client (deprecated, for backwards compatibility)
            model: Claude model to use
            repository: AgentRunRepository instance (auto-created if not provided)

        Note:
            If llm_client is provided, it takes precedence over anthropic_client.
            Tool calling currently requires anthropic_client (CLI tool support coming soon).
        """
        self.storage = storage
        self.llm_client = llm_client
        self.client = anthropic_client or Anthropic()
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

        # Determine provider and model
        provider = None
        model = self.model
        if self.llm_client:
            provider = "cli"  # Placeholder, will be updated after first response
        else:
            provider = "anthropic_api"

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
            # Use LLM client if provided, otherwise fall back to Anthropic API
            if self.llm_client:
                return self._run_with_llm_client(run_id, started_at, user_prompt, max_iterations)
            return self._run_with_anthropic_api(run_id, started_at, user_prompt, max_iterations)

        except Exception as e:
            logger.error(f"Agent run {run_id} failed: {e}")
            self._record_run_complete(
                run_id, datetime.now(UTC), AgentRunStatus.ERROR.value, 0, str(e)
            )
            return {"status": AgentRunStatus.ERROR.value, "error": str(e), "run_id": run_id}
