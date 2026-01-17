"""Multi-LLM Strategy Reviewer - Dual provider execution with consensus detection.

Executes both Gemini and Claude reviews independently and detects disagreements
between providers, fulfilling VISION.md "Disagreement Detection" requirement.

TODO: Migrate to MCP-based agent coordination (see tasks/tasks-0100-multi-agent-mcp-architecture.md)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from ..constants import CLAUDE_SONNET, GEMINI_FLASH
from ..logging_config import get_logger
from .llm_client import AgentHubAPIClient, LLMClient, LLMResponse
from .strategy_reviewer_prompts import (
    GUARDRAILS,
    build_review_prompt,
    get_system_prompt,
    validate_review,
)

logger = get_logger(__name__)


class DisagreementSeverity(str, Enum):
    """Severity of disagreement between providers."""

    NONE = "none"  # Both providers agree
    MINOR = "minor"  # Same direction but different concerns
    MAJOR = "major"  # Conflicting assessments (bullish vs bearish)


@dataclass
class ProviderReview:
    """Individual provider review result."""

    provider: str
    review_text: str
    is_valid: bool
    disagreement: bool  # LLM vs rules disagreement
    usage: dict[str, int]
    error: str | None = None


@dataclass
class DualReviewResult:
    """Combined result from dual-provider review."""

    symbol: str
    review_pair_id: str
    gemini_review: ProviderReview | None
    claude_review: ProviderReview | None
    agreement_score: float  # 0.0 to 1.0
    disagreement_severity: DisagreementSeverity
    provider_disagreement: bool  # True if providers disagree with each other
    consensus_summary: str  # Human-readable summary of consensus


class MultiReviewer:
    """Multi-LLM strategy reviewer with parallel dual execution.

    Executes both Gemini and Claude reviews for each signal, compares results,
    and detects disagreements between providers.
    """

    # Keywords indicating bullish sentiment
    BULLISH_KEYWORDS: ClassVar[list[str]] = [
        "upside",
        "positive",
        "strength",
        "momentum",
        "support",
        "opportunity",
        "favorable",
        "bullish",
    ]

    # Keywords indicating bearish sentiment
    BEARISH_KEYWORDS: ClassVar[list[str]] = [
        "downside",
        "negative",
        "weakness",
        "resistance",
        "risk",
        "concern",
        "unfavorable",
        "bearish",
        "caution",
        "warning",
    ]

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
                    # Use Agent Hub for all providers
                    model = GEMINI_FLASH if name == "gemini" else CLAUDE_SONNET
                    self._clients[name] = AgentHubAPIClient(model=model)
                else:
                    self._clients[name] = None
            except RuntimeError:
                logger.warning("llm_client_unavailable", client=name)
                self._clients[name] = None
        return self._clients[name]

    async def review_signal_dual(self, signal_data: dict[str, Any]) -> DualReviewResult:
        """Review a trading signal using both providers in parallel.

        Args:
            signal_data: Watchlist item with signal classification

        Returns:
            DualReviewResult with both reviews and consensus analysis
        """
        symbol = signal_data.get("symbol", "UNKNOWN")
        review_pair_id = str(uuid.uuid4())

        # Build prompt
        prompt = build_review_prompt(signal_data)
        rationale = signal_data.get("rationale", "").lower()

        logger.info(
            "starting_dual_review",
            symbol=symbol,
            review_pair_id=review_pair_id,
        )

        # Execute both reviews in parallel
        gemini_task = asyncio.create_task(self._generate_review("gemini", prompt, rationale))
        claude_task = asyncio.create_task(self._generate_review("claude", prompt, rationale))

        results = await asyncio.gather(gemini_task, claude_task, return_exceptions=True)

        gemini_result, claude_result = results[0], results[1]

        # Handle exceptions as failed reviews
        if isinstance(gemini_result, BaseException):
            logger.error("gemini_review_exception", error=str(gemini_result))
            gemini_review: ProviderReview = ProviderReview(
                provider="gemini",
                review_text="Review unavailable",
                is_valid=False,
                disagreement=False,
                usage={},
                error=str(gemini_result),
            )
        else:
            gemini_review = gemini_result

        if isinstance(claude_result, BaseException):
            logger.error("claude_review_exception", error=str(claude_result))
            claude_review: ProviderReview = ProviderReview(
                provider="claude",
                review_text="Review unavailable",
                is_valid=False,
                disagreement=False,
                usage={},
                error=str(claude_result),
            )
        else:
            claude_review = claude_result

        # Compute consensus
        agreement_score, severity, provider_disagreement = self._compute_consensus(
            gemini_review, claude_review
        )

        # Generate summary
        consensus_summary = self._generate_consensus_summary(
            gemini_review, claude_review, severity, provider_disagreement
        )

        result = DualReviewResult(
            symbol=symbol,
            review_pair_id=review_pair_id,
            gemini_review=gemini_review,
            claude_review=claude_review,
            agreement_score=agreement_score,
            disagreement_severity=severity,
            provider_disagreement=provider_disagreement,
            consensus_summary=consensus_summary,
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
                max_tokens=GUARDRAILS["max_tokens"],
                temperature=GUARDRAILS["temperature"],
            )

            # Validate against guardrails
            is_valid, reason = validate_review(response.content)
            if not is_valid:
                logger.warning(
                    f"Review failed validation from {provider}: {reason}",
                    extra={"provider": provider},
                )

            # Detect LLM vs rules disagreement
            disagreement = self._detect_rules_disagreement(response.content, rationale)

            return ProviderReview(
                provider=provider,
                review_text=response.content,
                is_valid=is_valid,
                disagreement=disagreement,
                usage=response.usage,
            )

        except Exception as e:
            logger.error(
                f"Provider {provider} failed: {e}",
                extra={"provider": provider},
                exc_info=True,
            )
            return ProviderReview(
                provider=provider,
                review_text="Review unavailable",
                is_valid=False,
                disagreement=False,
                usage={},
                error=str(e),
            )

    def _detect_rules_disagreement(self, review_text: str, rationale: str) -> bool:
        """Check if LLM review flags concerns not in rules rationale.

        Args:
            review_text: LLM review
            rationale: Rules engine rationale

        Returns:
            True if LLM flags NEW concerns
        """
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

        has_concerns = any(kw in review_lower for kw in concern_keywords)
        rules_didnt_flag = not any(kw in rationale_lower for kw in concern_keywords)

        return has_concerns and rules_didnt_flag

    def _compute_consensus(
        self, gemini: ProviderReview, claude: ProviderReview
    ) -> tuple[float, DisagreementSeverity, bool]:
        """Compute consensus between two provider reviews.

        Args:
            gemini: Gemini review result
            claude: Claude review result

        Returns:
            (agreement_score, disagreement_severity, provider_disagreement)
        """
        # If either review failed, can't compute meaningful consensus
        if gemini.error or claude.error:
            # Only one available - treat as full agreement with itself
            if gemini.error and not claude.error:
                return 1.0, DisagreementSeverity.NONE, False
            if claude.error and not gemini.error:
                return 1.0, DisagreementSeverity.NONE, False
            # Both failed
            return 0.0, DisagreementSeverity.NONE, False

        # Analyze sentiment direction from each review
        gemini_sentiment = self._analyze_sentiment(gemini.review_text)
        claude_sentiment = self._analyze_sentiment(claude.review_text)

        # Calculate agreement score (0.0 to 1.0)
        # Based on sentiment alignment and concern overlap
        sentiment_diff = abs(gemini_sentiment - claude_sentiment)

        # Normalize to 0-1 range (max diff is 2.0)
        agreement_score = 1.0 - (sentiment_diff / 2.0)

        # Determine severity based on thresholds
        if sentiment_diff < 0.3:
            severity = DisagreementSeverity.NONE
            provider_disagreement = False
        elif sentiment_diff < 0.7:
            severity = DisagreementSeverity.MINOR
            provider_disagreement = True
        else:
            severity = DisagreementSeverity.MAJOR
            provider_disagreement = True

        return agreement_score, severity, provider_disagreement

    def _analyze_sentiment(self, review_text: str) -> float:
        """Analyze sentiment of review text.

        Args:
            review_text: LLM review text

        Returns:
            Sentiment score from -1.0 (bearish) to +1.0 (bullish)
        """
        text_lower = review_text.lower()

        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)

        total = bullish_count + bearish_count
        if total == 0:
            return 0.0  # Neutral

        # Score from -1 to +1
        return (bullish_count - bearish_count) / total

    def _generate_consensus_summary(
        self,
        gemini: ProviderReview,
        claude: ProviderReview,
        severity: DisagreementSeverity,
        provider_disagreement: bool,
    ) -> str:
        """Generate human-readable consensus summary.

        Args:
            gemini: Gemini review
            claude: Claude review
            severity: Disagreement severity
            provider_disagreement: Whether providers disagree

        Returns:
            Summary string for display
        """
        if gemini.error and claude.error:
            return "Both reviewers unavailable"

        if gemini.error:
            return f"Only Claude review available: {claude.review_text[:100]}..."

        if claude.error:
            return f"Only Gemini review available: {gemini.review_text[:100]}..."

        if not provider_disagreement:
            return "Both reviewers agree on the assessment"

        if severity == DisagreementSeverity.MINOR:
            return "Reviewers have minor differences in emphasis but align on direction"

        # Major disagreement
        return "ALERT: Reviewers significantly disagree - manual review recommended"
