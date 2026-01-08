"""LLM Strategy Reviewer service - second opinion on trading signals.

Zero-cost post-analysis using Claude/Gemini CLI tools.

TODO: Migrate to MCP-based agent coordination (see tasks/tasks-0100-multi-agent-mcp-architecture.md)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from ..logging_config import get_logger
from .llm_client import AgentHubAPIClient, LLMClient, LLMResponse
from .strategy_reviewer_prompts import (
    GUARDRAILS,
    build_review_prompt,
    get_system_prompt,
    validate_review,
)

logger = get_logger(__name__)


class StrategyReviewer:
    """LLM-powered strategy reviewer with automatic failover."""

    def __init__(self, storage: PortfolioStorage, primary_provider: str = "gemini") -> None:
        """Initialize reviewer with provider preference.

        Args:
            storage: PortfolioStorage instance for performance metrics
            primary_provider: "gemini" or "claude" (fallback to other if unavailable)
        """
        self.storage = storage
        self.primary_provider = primary_provider
        self._clients: dict[str, LLMClient | None] = {}

    def _get_client(self, name: str) -> LLMClient | None:
        """Lazy-load LLM client via Agent Hub."""
        if name not in self._clients:
            try:
                if name in ("gemini", "claude"):
                    # Use Agent Hub for all providers
                    model = (
                        "gemini-3-flash-preview"
                        if name == "gemini"
                        else "claude-sonnet-4-5-20250514"
                    )
                    self._clients[name] = AgentHubAPIClient(model=model)
                else:
                    self._clients[name] = None
            except RuntimeError:
                logger.warning("llm_client_unavailable", client=name)
                self._clients[name] = None
        return self._clients[name]

    async def review_signal(self, signal_data: dict[str, Any]) -> dict[str, Any]:
        """Review a trading signal and return analysis.

        Args:
            signal_data: Watchlist item with signal classification

        Returns:
            {
                "symbol": str,
                "review": str (2-3 sentences),
                "is_valid": bool (passed guardrails),
                "provider": str ("gemini" or "claude"),
                "disagreement": bool (LLM flags concerns not in rules rationale),
                "usage": dict (token stats),
            }
        """
        symbol = signal_data.get("symbol", "UNKNOWN")

        try:
            # Build prompt
            prompt = build_review_prompt(signal_data)

            # Try primary provider
            review_text, provider, usage = await self._generate_with_failover(prompt)

            # Validate against guardrails
            is_valid, reason = validate_review(review_text)
            if not is_valid:
                logger.warning(
                    f"Review failed validation for {symbol}: {reason}",
                    extra={"symbol": symbol, "provider": provider},
                )

            # Detect disagreement (LLM flags risks not in rules rationale)
            rationale = signal_data.get("rationale", "").lower()
            disagreement = self._detect_disagreement(review_text, rationale)

            return {
                "symbol": symbol,
                "review": review_text,
                "is_valid": is_valid,
                "provider": provider,
                "disagreement": disagreement,
                "usage": usage,
            }

        except Exception as e:
            logger.error(
                f"Strategy review failed for {symbol}: {e}",
                extra={"symbol": symbol},
                exc_info=True,
            )
            return {
                "symbol": symbol,
                "review": "Review unavailable",
                "is_valid": False,
                "provider": "none",
                "disagreement": False,
                "usage": {},
            }

    async def _generate_with_failover(self, prompt: str) -> tuple[str, str, dict[str, int]]:
        """Generate with automatic failover to backup provider.

        Args:
            prompt: Review prompt

        Returns:
            (review_text, provider_used, token_usage)
        """
        providers = [self.primary_provider]
        if self.primary_provider == "gemini":
            providers.append("claude")
        else:
            providers.append("gemini")

        last_error = None
        for provider in providers:
            try:
                client = self._get_client(provider)
                if client is None:
                    raise RuntimeError(f"{provider} client not available")
                response: LLMResponse = await asyncio.to_thread(
                    client.generate,
                    prompt=prompt,
                    system=get_system_prompt(self.storage),
                    max_tokens=GUARDRAILS["max_tokens"],
                    temperature=GUARDRAILS["temperature"],
                )
                return response.content, provider, response.usage
            except Exception as e:
                logger.warning(
                    f"Provider {provider} failed, trying failover: {e}",
                    extra={"provider": provider},
                )
                last_error = e
                continue

        # All providers failed
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def _detect_disagreement(self, review_text: str, rationale: str) -> bool:
        """Check if LLM review flags concerns not in rules rationale.

        Args:
            review_text: LLM review
            rationale: Rules engine rationale

        Returns:
            True if LLM flags NEW concerns
        """
        # Keywords indicating LLM found issues
        concern_keywords = [
            "risk",
            "concern",
            "caution",
            "unusual",
            "unexpected",
            "note that",
            "however",
            "but",
            "warning",
        ]

        review_lower = review_text.lower()
        rationale_lower = rationale.lower()

        # LLM raised concerns
        has_concerns = any(kw in review_lower for kw in concern_keywords)

        # Rules didn't mention those concerns
        rules_didnt_flag = not any(kw in rationale_lower for kw in concern_keywords)

        return has_concerns and rules_didnt_flag
