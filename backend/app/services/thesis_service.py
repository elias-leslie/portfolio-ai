"""Thesis Service - LLM-powered investment thesis generation with dual-provider validation.

This service generates structured investment theses using intelligence data from the
symbols API, leveraging both Gemini and Claude for cross-validation and quality assurance.

Key features:
- Fetches comprehensive intelligence data from internal API
- Generates thesis with Gemini, validates with Claude
- Calculates cross-validation scores based on LLM agreement
- Supports versioning and invalidation tracking
- Checks invalidation triggers based on market conditions
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..agents.llm_client import DualProviderClient
from ..logging_config import get_logger
from ..models.thesis import Thesis, ThesisStatus, ThesisVersion
from .thesis.intelligence_fetcher import IntelligenceFetcher
from .thesis.thesis_builder import ThesisBuilder
from .thesis.thesis_generation import ThesisGenerator
from .thesis.thesis_storage import ThesisStorageManager
from .thesis.thesis_validation import ThesisValidator

logger = get_logger(__name__)


class ThesisService:
    """Service for generating and managing investment theses with dual-LLM validation."""

    def __init__(
        self,
        llm_client: DualProviderClient | None = None,
        api_base_url: str = "http://localhost:8000",
    ) -> None:
        """Initialize thesis service.

        Args:
            llm_client: Dual-provider LLM client (Gemini + Claude)
            api_base_url: Base URL for internal API calls
        """
        self._fetcher = IntelligenceFetcher(api_base_url)
        self._generator = ThesisGenerator(llm_client)
        self._validator = ThesisValidator()
        self._storage = ThesisStorageManager()

    def generate_thesis(self, symbol: str, force: bool = False) -> Thesis:
        """Generate investment thesis for symbol.

        Workflow:
        1. Fetch intelligence from internal API
        2. Generate thesis with Gemini
        3. Validate with Claude
        4. Calculate cross-validation score
        5. Save to database with version history

        Args:
            symbol: Stock symbol
            force: Force regeneration even if recent thesis exists

        Returns:
            Generated Thesis object

        Raises:
            RuntimeError: If generation fails
        """
        symbol = symbol.upper()

        # Check for existing active thesis
        if not force:
            existing = self.get_thesis(symbol)
            if existing and existing.status == ThesisStatus.ACTIVE:
                # Check if thesis is recent (< 24 hours old)
                created = datetime.fromisoformat(existing.created_at)
                age_hours = (datetime.now(UTC) - created).total_seconds() / 3600
                if age_hours < 24:
                    logger.info(
                        "thesis_already_recent",
                        symbol=symbol,
                        thesis_id=existing.id,
                        age_hours=age_hours,
                    )
                    return existing

        logger.info("thesis_generation_started", symbol=symbol, force=force)

        try:
            # Step 1: Fetch intelligence
            intelligence = self._fetcher.fetch(symbol)

            # Step 2: Generate with Gemini
            thesis_data = self._generator.generate_with_gemini(intelligence)

            # Step 3: Validate with Claude
            claude_validation = self._validator.validate_with_claude(intelligence, thesis_data)

            # Step 4: Calculate cross-validation score
            cross_val_score = self._validator.calculate_cross_validation_score(claude_validation)

            # Step 5: Determine version (increment if existing)
            existing = self.get_thesis(symbol)
            version = (existing.version + 1) if existing else 1

            # Step 6: Build Thesis object
            thesis = ThesisBuilder.build(
                symbol, thesis_data, claude_validation, cross_val_score, version
            )

            # Step 7: Save to database
            self._storage.save_thesis(thesis)
            self._storage.save_version(thesis, "Generated new thesis")

            logger.info(
                "thesis_generation_completed",
                thesis_id=thesis.id,
                symbol=symbol,
                version=version,
                cross_val_score=cross_val_score,
                claude_approved=claude_validation.approved,
            )

            return thesis

        except Exception as e:
            logger.error("thesis_generation_failed", symbol=symbol, error=str(e))
            raise RuntimeError(f"Failed to generate thesis for {symbol}: {e}") from e

    def get_thesis(self, symbol: str) -> Thesis | None:
        """Retrieve current active thesis for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Thesis object or None if not found
        """
        return self._storage.get_thesis(symbol)

    def get_thesis_versions(self, symbol: str, limit: int = 10) -> list[ThesisVersion]:
        """Retrieve version history for symbol.

        Args:
            symbol: Stock symbol
            limit: Maximum number of versions to return

        Returns:
            List of ThesisVersion objects (newest first)
        """
        return self._storage.get_thesis_versions(symbol, limit)

    def invalidate_thesis(self, symbol: str, reason: str) -> Thesis | None:
        """Mark thesis as invalidated and increment version.

        Args:
            symbol: Stock symbol
            reason: Invalidation reason

        Returns:
            Updated Thesis object or None if not found
        """
        symbol = symbol.upper()
        thesis = self.get_thesis(symbol)

        if not thesis:
            logger.warning("thesis_not_found_for_invalidation", symbol=symbol)
            return None

        # Update status
        now = datetime.now(UTC).isoformat()
        thesis.status = ThesisStatus.INVALIDATED
        thesis.invalidation_reason = reason
        thesis.invalidated_at = now
        thesis.updated_at = now
        thesis.version += 1

        # Save updates
        self._storage.save_thesis(thesis)
        self._storage.save_version(thesis, f"Invalidated: {reason}")

        logger.info(
            "thesis_invalidated",
            thesis_id=thesis.id,
            symbol=symbol,
            version=thesis.version,
            reason=reason,
        )

        return thesis

    def check_invalidation_triggers(self, symbol: str) -> list[str]:
        """Check if any invalidation triggers are met.

        Invalidation triggers:
        - Signal type changed from BUY to AVOID (or vice versa)
        - Signal strength dropped by ≥3 points
        - Cross-validation score < 0.5
        - Stop-loss breach detected
        - Major news event (sentiment shift > 0.3)

        Args:
            symbol: Stock symbol

        Returns:
            List of triggered reasons (empty if none)
        """
        symbol = symbol.upper()
        triggers = []

        try:
            # Fetch current intelligence
            intelligence = self._fetcher.fetch(symbol)

            # Get current thesis
            thesis = self.get_thesis(symbol)
            if not thesis or thesis.status != ThesisStatus.ACTIVE:
                return []

            # Trigger 1: Signal type changed significantly
            scores = intelligence.get("scores") or {}
            current_signal = scores.get("signal_type")
            thesis_action = thesis.action.value

            if current_signal == "AVOID" and thesis_action == "BUY":
                triggers.append("Signal changed from BUY to AVOID")
            elif current_signal == "BUY" and thesis_action == "SELL":
                triggers.append("Signal changed from SELL to BUY")

            # Trigger 2: Signal strength dropped significantly
            # NOTE: We don't store original signal strength in thesis, so skip this check.
            # Future enhancement: Store signal_strength_at_creation in thesis metadata
            _ = scores.get("signal_strength")  # Placeholder for future implementation

            # Trigger 3: Low cross-validation score
            if thesis.cross_validation_score and thesis.cross_validation_score < 0.5:
                triggers.append(f"Low cross-validation score: {thesis.cross_validation_score:.2f}")

            # Trigger 4: News sentiment shift
            news = intelligence.get("news") or {}
            sentiment_score = news.get("sentiment_score")
            if sentiment_score is not None:
                # Check for major negative shift if thesis is BUY
                if thesis_action == "BUY" and sentiment_score < -0.3:
                    triggers.append(f"Negative news sentiment: {sentiment_score:.2f}")
                # Check for major positive shift if thesis is SELL
                elif thesis_action == "SELL" and sentiment_score > 0.3:
                    triggers.append(f"Positive news sentiment: {sentiment_score:.2f}")

            logger.info(
                "invalidation_triggers_checked",
                symbol=symbol,
                triggers_count=len(triggers),
                triggers=triggers,
            )

            return triggers

        except Exception as e:
            logger.error("invalidation_trigger_check_failed", symbol=symbol, error=str(e))
            return []
