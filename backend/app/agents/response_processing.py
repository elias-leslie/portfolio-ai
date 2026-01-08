"""Response processing utilities for agents.

This module handles token extraction, response parsing, and usage accumulation.
Extracted from base.py for single responsibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_client import LLMResponse


def extract_final_response(response: object) -> str:
    """Extract final text response from Anthropic API response.

    Args:
        response: Anthropic API response with content blocks

    Returns:
        Extracted text content
    """
    final_text = ""
    for block in response.content:  # type: ignore[attr-defined]
        if block.type == "text":
            final_text += block.text
    return final_text


def extract_output_tokens(response: LLMResponse) -> int | None:
    """Extract completion tokens from LLM response.

    Args:
        response: LLM response with usage info

    Returns:
        Completion token count, or None if unavailable
    """
    return response.usage.get("completion_tokens") if response.usage else None


def accumulate_token_usage(response: LLMResponse, total_token_usage: dict[str, int]) -> None:
    """Accumulate token usage from an LLM response.

    Args:
        response: LLM response with usage info
        total_token_usage: Dict to accumulate usage into (modified in place)
    """
    if response.usage:
        total_token_usage["input_tokens"] += response.usage.get("prompt_tokens", 0)
        total_token_usage["output_tokens"] += response.usage.get("completion_tokens", 0)
        total_token_usage["total_tokens"] += response.usage.get("total_tokens", 0)


class ResponseProcessingMixin:
    """Mixin providing response processing methods for agents.

    Methods that need to be called as instance methods are wrapped here.
    """

    def _extract_final_response(self, response: object) -> str:
        """Extract final text response from API response."""
        return extract_final_response(response)

    def _extract_output_tokens(self, response: LLMResponse) -> int | None:
        """Extract completion tokens from LLM response."""
        return extract_output_tokens(response)

    def _accumulate_token_usage(
        self, response: LLMResponse, total_token_usage: dict[str, int]
    ) -> None:
        """Accumulate token usage from an LLM response."""
        accumulate_token_usage(response, total_token_usage)
