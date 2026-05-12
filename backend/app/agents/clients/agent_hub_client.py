"""Agent Hub API client.

Implements LLMClient interface for Agent Hub service.
Routes through Agent Hub agents; Agent Hub owns model selection and fallbacks.
"""

from __future__ import annotations

import json
import time
from typing import Any

from agent_hub import AgentHubClient as SDKClient
from agent_hub import AsyncAgentHubClient as AsyncSDKClient
from agent_hub.exceptions import AgentHubError

from ...config import settings
from ...logging_config import get_logger
from ...services._jenny_response_cleanup import extract_json_object_text
from .base_client import LLMClient, LLMResponse

logger = get_logger(__name__)

# Default Agent Hub URL (from centralized settings)
DEFAULT_AGENT_HUB_URL = settings.agent_hub_url
DEFAULT_AGENT_SLUG = "chat"

# Portfolio-AI client credentials from centralized settings
PORTFOLIO_CLIENT_ID = settings.portfolio_client_id or None
PORTFOLIO_REQUEST_SOURCE = settings.portfolio_request_source

# Feature flag to enable/disable Agent Hub calls
AGENT_HUB_ENABLED = settings.agent_hub_enabled


class AgentHubAPIClient(LLMClient):
    """Agent Hub API client.

    Uses Agent Hub service for LLM completions.
    Uses Agent Hub agent slugs via the canonical SDK.
    """

    def __init__(
        self,
        agent_slug: str | None = None,
        model: str | None = None,
        base_url: str = DEFAULT_AGENT_HUB_URL,
        api_key: str | None = None,
        timeout: float | None = None,
        use_memory: bool | None = None,
    ) -> None:
        """Initialize Agent Hub client.

        Args:
            agent_slug: Preferred Agent Hub agent slug for routed completions.
            model: Deprecated. Direct model overrides are rejected; use agent_slug.
            base_url: Agent Hub API base URL
            api_key: Optional API key for authentication
            timeout: Optional HTTP request timeout in seconds. Leave unset for
                long-running agent calls.
            use_memory: Explicit memory override. ``None`` defers to the agent's
                configured memory settings in Agent Hub.

        Raises:
            RuntimeError: If Agent Hub is disabled or service is not reachable
        """
        if not AGENT_HUB_ENABLED:
            raise RuntimeError(
                "Agent Hub is disabled. Set AGENT_HUB_ENABLED=true to enable agentic calls."
            )
        if model is not None:
            raise ValueError("Direct model overrides are not allowed; use agent_slug.")

        self.agent_slug = agent_slug or DEFAULT_AGENT_SLUG
        self._preferred_agent_slug = agent_slug
        self.base_url = base_url
        self.timeout = timeout
        self.use_memory = use_memory
        self._sdk_kwargs: dict[str, Any] = {
            "base_url": base_url,
            "api_key": api_key,
            "timeout": timeout,
            "client_name": "portfolio-ai",
            "client_id": PORTFOLIO_CLIENT_ID,
            "request_source": PORTFOLIO_REQUEST_SOURCE,
        }
        self._client = SDKClient(**self._sdk_kwargs)
        self._async_client: AsyncSDKClient | None = None

        self.provider = "agent_hub"

        logger.info(
            "agent_hub_client_initialized",
            base_url=base_url,
            agent_slug=self.agent_slug,
            provider=self.provider,
        )

    def is_available(self) -> bool:
        """Check if Agent Hub service is available.

        Returns:
            True if service is reachable
        """
        try:
            # Simple health check - try to list models
            response = self._client._get_client().get("/health")
            return bool(response.is_success)
        except Exception as e:
            logger.debug("agent_hub_health_check_failed", error=str(e))
            return False

    def get_model_name(self) -> str:
        """Get the Agent Hub route name.

        Returns:
            Agent slug used for routing.
        """
        return self.agent_slug

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        purpose: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using Agent Hub API.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            tools: Tool definitions for function calling
            temperature: Sampling temperature
            purpose: Purpose of this request for session tracking
            **kwargs: Additional options

        Returns:
            LLMResponse with completion

        Raises:
            RuntimeError: If API call fails
        """
        start_time = time.time()

        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        logger.info(
            "agent_hub_calling",
            agent_slug=self.agent_slug,
            prompt_length=len(prompt),
            has_system=system is not None,
            has_tools=tools is not None,
            purpose=purpose,
        )

        try:
            response = self.complete_messages(
                messages=messages,
                temperature=temperature,
                tools=tools,
                purpose=purpose,
                system_prompt=system,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            # Add cache info if available
            if response.usage.cache:
                usage["cache_creation_tokens"] = response.usage.cache.cache_creation_input_tokens
                usage["cache_read_tokens"] = response.usage.cache.cache_read_input_tokens

            logger.info(
                "agent_hub_success",
                duration_ms=duration_ms,
                tokens=usage["total_tokens"],
                response_length=len(response.content),
                provider=response.provider,
            )

            # Extract tool calls if present
            tool_calls = None
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_calls = [
                    {"name": tc.name, "parameters": tc.input, "id": tc.id}
                    for tc in response.tool_calls
                ]

            return LLMResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=usage,
                stop_reason=response.finish_reason or "end_turn",
                tool_calls=tool_calls,
                raw_response={
                    "session_id": response.session_id,
                    "from_cache": response.from_cache,
                    "finish_reason": response.finish_reason,
                },
            )

        except AgentHubError as e:
            logger.error("agent_hub_error", error=str(e), exc_info=True)
            raise RuntimeError(f"Agent Hub API error: {e}") from e

        except Exception as e:
            logger.error("agent_hub_unexpected_error", error=str(e), exc_info=True)
            raise RuntimeError(f"Unexpected Agent Hub error: {e}") from e

    def complete_messages(
        self,
        *,
        messages: list[Any],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        purpose: str | None = None,
        session_id: str | None = None,
        max_turns: int = 1,
        thinking_level: str | None = None,
        response_format: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        use_memory: bool | None = None,
        execute_tools: bool = False,
        enable_programmatic_tools: bool = False,
        agent_slug: str | None = None,
    ) -> Any:
        request_kwargs: dict[str, Any] = {
            "agent_slug": agent_slug or self.agent_slug,
            "messages": messages,
            "temperature": temperature,
            "project_id": "portfolio-ai",
            "purpose": purpose,
        }
        if tools is not None:
            request_kwargs["tools"] = tools
        resolved_memory = self.use_memory if use_memory is None else use_memory
        if resolved_memory is not None:
            request_kwargs["use_memory"] = resolved_memory
        if session_id is not None:
            request_kwargs["session_id"] = session_id
        if max_turns != 1:
            request_kwargs["max_turns"] = max_turns
        if thinking_level is not None:
            request_kwargs["thinking_level"] = thinking_level
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        if system_prompt is not None:
            request_kwargs["system_prompt"] = system_prompt
        if execute_tools:
            request_kwargs["execute_tools"] = True
        if enable_programmatic_tools:
            request_kwargs["enable_programmatic_tools"] = True
        return self._client.complete(**request_kwargs)

    def run_committee_roundtable(
        self,
        *,
        prompt: str,
        window_days: int,
        source_snapshot_json: str,
        purpose: str = "market_prediction_committee",
        max_turns: int = 4,
    ) -> dict[str, Any]:
        http_client = self._client._get_client()
        try:
            response = http_client.post(
                "/api/orchestration/committee",
                json={
                    "prompt": prompt,
                    "window_days": window_days,
                    "source_snapshot": json.loads(source_snapshot_json),
                    "project_id": "portfolio-ai",
                    "agent_slug": "investment-committee",
                    "trace_id": purpose,
                },
            )
            if getattr(response, "is_success", False):
                payload = response.json()
                if (
                    isinstance(payload, dict)
                    and isinstance(payload.get("calls"), list)
                    and isinstance(payload.get("votes"), list)
                ):
                    return {**payload, "_portfolio_execution_path": "committee_endpoint"}
        except Exception:
            logger.warning("committee_endpoint_request_failed", exc_info=True)

        message = (
            f"Committee forecast window: {window_days} trading days.\n\n"
            f"Source snapshot JSON:\n{source_snapshot_json}\n\n"
            f"Task:\n{prompt}"
        )
        response = self.complete_messages(
            agent_slug="investment-committee",
            messages=[{"role": "user", "content": message}],
            purpose=purpose,
            response_format={"type": "json_object"},
            max_turns=max_turns,
        )
        payload_text = extract_json_object_text(str(getattr(response, "content", "") or ""))
        if payload_text is None:
            raise RuntimeError("Committee roundtable returned no JSON payload")
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Committee roundtable returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Committee roundtable returned non-object payload")
        return {**payload, "_portfolio_execution_path": "fallback_completion"}

    def _get_async_client(self) -> AsyncSDKClient:
        """Return a lazily-constructed async SDK client.

        Used by the Investment Committee runner so analyst/researcher/risk
        stages can call ``asyncio.gather`` and actually parallelize. The sync
        client and async client share the same configuration but maintain
        independent ``httpx`` connection pools.
        """
        if self._async_client is None:
            self._async_client = AsyncSDKClient(**self._sdk_kwargs)
        return self._async_client

    async def complete_messages_async(
        self,
        *,
        messages: list[Any],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        purpose: str | None = None,
        session_id: str | None = None,
        max_turns: int = 1,
        thinking_level: str | None = None,
        response_format: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        use_memory: bool | None = None,
        execute_tools: bool = False,
        enable_programmatic_tools: bool = False,
        agent_slug: str | None = None,
    ) -> Any:
        """Async counterpart to ``complete_messages``.

        Mirrors the sync signature; routes through ``AsyncAgentHubClient``
        so callers using ``asyncio.gather`` see real I/O parallelism.
        """
        request_kwargs: dict[str, Any] = {
            "agent_slug": agent_slug or self.agent_slug,
            "messages": messages,
            "temperature": temperature,
            "project_id": "portfolio-ai",
            "purpose": purpose,
        }
        if tools is not None:
            request_kwargs["tools"] = tools
        resolved_memory = self.use_memory if use_memory is None else use_memory
        if resolved_memory is not None:
            request_kwargs["use_memory"] = resolved_memory
        if session_id is not None:
            request_kwargs["session_id"] = session_id
        if max_turns != 1:
            request_kwargs["max_turns"] = max_turns
        if thinking_level is not None:
            request_kwargs["thinking_level"] = thinking_level
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        if system_prompt is not None:
            request_kwargs["system_prompt"] = system_prompt
        if execute_tools:
            request_kwargs["execute_tools"] = True
        if enable_programmatic_tools:
            request_kwargs["enable_programmatic_tools"] = True
        return await self._get_async_client().complete(**request_kwargs)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    async def aclose(self) -> None:
        """Close async SDK client if one was lazily created."""
        if self._async_client is not None:
            await self._async_client.close()
            self._async_client = None

    def __enter__(self) -> AgentHubAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
