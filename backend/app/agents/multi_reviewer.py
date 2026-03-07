"""Multi-LLM Strategy Reviewer - Dual provider execution with consensus detection.

Executes both Gemini and Claude reviews independently and detects disagreements
between providers, fulfilling VISION.md "Disagreement Detection" requirement.

TODO: Migrate to MCP-based agent coordination (see tasks/tasks-0100-multi-agent-mcp-architecture.md)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from ..constants import CLAUDE_SONNET, GEMINI_FLASH
from ..logging_config import get_logger
from .llm_client import AgentHubAPIClient, LLMClient, LLMResponse
from .multi_reviewer_consensus import (
    analyze_sentiment,
    compute_consensus,
    detect_rules_disagreement,
    generate_consensus_summary,
)
from .multi_reviewer_models import (
    DisagreementSeverity,
    DualReviewResult,
    ProviderReview,
)
from .strategy_reviewer_prompts import (
    GUARDRAILS,
    build_review_prompt,
    get_system_prompt,
    validate_review,
)

logger = get_logger(__name__)

# Re-export for backward compatibility
__all__ = ["DisagreementSeverity", "DualReviewResult", "MultiReviewer", "ProviderReview"]


def _make_failed_review(provider: str, error: str) -> ProviderReview:
    """Create a ProviderReview for a failed/unavailable provider."""
    return ProviderReview(
        provider=provider,
        review_text="Review unavailable",
        is_valid=False,
        disagreement=False,
        usage={},
        error=error,
    )


class MultiReviewer:
    """Multi-LLM strategy reviewer with parallel dual execution.

    Executes both Gemini and Claude reviews for each signal, compares results,
    and detects disagreements between providers.
    """

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize multi-reviewer with both providers.

        Args:
            storage: PortfolioStorage instance for performance metrics
        """
        self.storage = storage
        self._clients: dict[str, LLMClient | None] = {}

    def _get_client(self, name: str) -> LLMClient | None:
        """Lazy-load LLM client via Agent Hub."""
        if name not in self._clients:
            try:
                if name in ("gemini", "claude"):
                    model = GEMINI_FLASH if name == "gemini" else CLAUDE_SONNET
                    self._clients[name] = AgentHubAPIClient(model=model)
                else:
                    self._clients[name] = None
            except RuntimeError:
                logger.warning("llm_client_unavailable", client=name)
                self._clients[name] = None
        return self._clients[name]

    # Thin instance wrappers preserve the historic test/caller surface while
    # keeping the actual logic centralized in multi_reviewer_consensus.
    def _analyze_sentiment(self, review_text: str) -> float:
        return analyze_sentiment(review_text)

    def _detect_rules_disagreement(self, review_text: str, rationale: str) -> bool:
        return detect_rules_disagreement(review_text, rationale)

    def _generate_consensus_summary(
        self,
        gemini: ProviderReview,
        claude: ProviderReview,
        severity: DisagreementSeverity,
        provider_disagreement: bool,
    ) -> str:
        return generate_consensus_summary(gemini, claude, severity, provider_disagreement)

    def _compute_consensus(
        self, gemini: ProviderReview, claude: ProviderReview
    ) -> tuple[float | None, DisagreementSeverity, bool]:
        agreement_score, severity, provider_disagreement = compute_consensus(gemini, claude)

        # Historical callers treated a single-provider success as full agreement
        # because there is no conflicting view to compare against.
        if agreement_score is None and (gemini.error or claude.error):
            return 1.0, DisagreementSeverity.NONE, False

        return agreement_score, severity, provider_disagreement

    async def review_signal_dual(self, signal_data: dict[str, Any]) -> DualReviewResult:
        """Review a trading signal using both providers in parallel.

        Args:
            signal_data: Watchlist item with signal classification

        Returns:
            DualReviewResult with both reviews and consensus analysis
        """
        symbol = signal_data.get("symbol", "UNKNOWN")
        review_pair_id = str(uuid.uuid4())
        prompt = build_review_prompt(signal_data)
        rationale = signal_data.get("rationale", "").lower()

        logger.info("starting_dual_review", symbol=symbol, review_pair_id=review_pair_id)

        results = await asyncio.gather(
            self._generate_review("gemini", prompt, rationale),
            self._generate_review("claude", prompt, rationale),
            return_exceptions=True,
        )

        gemini_review = (
            results[0] if not isinstance(results[0], BaseException)
            else _make_failed_review("gemini", str(results[0]))
        )
        claude_review = (
            results[1] if not isinstance(results[1], BaseException)
            else _make_failed_review("claude", str(results[1]))
        )

        agreement_score, severity, provider_disagreement = compute_consensus(
            gemini_review, claude_review
        )
        result = DualReviewResult(
            symbol=symbol,
            review_pair_id=review_pair_id,
            gemini_review=gemini_review,
            claude_review=claude_review,
            agreement_score=agreement_score,
            disagreement_severity=severity,
            provider_disagreement=provider_disagreement,
            consensus_summary=generate_consensus_summary(
                gemini_review, claude_review, severity, provider_disagreement
            ),
        )

        logger.info(
            "dual_review_complete",
            symbol=symbol,
            review_pair_id=review_pair_id,
            agreement_score=agreement_score,
            disagreement_severity=severity.value,
            provider_disagreement=provider_disagreement,
        )
        return result

    async def _generate_review(self, provider: str, prompt: str, rationale: str) -> ProviderReview:
        """Generate review from a single provider.

        Args:
            provider: "gemini" or "claude"
            prompt: Review prompt
            rationale: Rules engine rationale for disagreement detection

        Returns:
            ProviderReview with result or error
        """
        try:
            client = self._get_client(provider)
            if client is None:
                raise RuntimeError(f"{provider} client not available")
            response: LLMResponse = await asyncio.to_thread(
                client.generate,
                prompt=prompt,
                system=get_system_prompt(self.storage),
                temperature=GUARDRAILS["temperature"],
                purpose=f"multi_review:{provider}",
            )
            is_valid, reason = validate_review(response.content)
            if not is_valid:
                logger.warning(
                    "review_validation_failed",
                    provider=provider,
                    reason=reason,
                )
            return ProviderReview(
                provider=provider,
                review_text=response.content,
                is_valid=is_valid,
                disagreement=detect_rules_disagreement(response.content, rationale),
                usage=response.usage,
            )
        except Exception as e:
            logger.error(
                "provider_review_failed",
                provider=provider,
                error=str(e),
                exc_info=True,
            )
            return _make_failed_review(provider, str(e))
