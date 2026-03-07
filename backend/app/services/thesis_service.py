"""Thesis Service - LLM-powered investment thesis generation with dual-provider validation."""

from __future__ import annotations

from ..agents.llm_client import DualProviderClient
from ..logging_config import get_logger
from ..models.thesis import Thesis, ThesisStatus, ThesisVersion
from ..portfolio.watchlist_sync import ensure_symbols_in_watchlist
from ..storage import get_storage
from .thesis.intelligence_fetcher import IntelligenceFetcher
from .thesis.thesis_builder import ThesisBuilder
from .thesis.thesis_generation import ThesisGenerator
from .thesis.thesis_storage import ThesisStorageManager
from .thesis.thesis_triggers import (
    apply_invalidation,
    check_cross_val_trigger,
    check_sentiment_triggers,
    check_signal_triggers,
    is_thesis_recent,
)
from .thesis.thesis_validation import ThesisValidator

logger = get_logger(__name__)


class ThesisService:
    """Service for generating and managing investment theses with dual-LLM validation."""

    def __init__(
        self,
        llm_client: DualProviderClient | None = None,
        api_base_url: str = "http://localhost:8000",
    ) -> None:
        self._app_storage = get_storage()
        self._fetcher = IntelligenceFetcher(api_base_url)
        self._generator = ThesisGenerator(llm_client)
        self._validator = ThesisValidator()
        self._storage = ThesisStorageManager()

    def generate_thesis(self, symbol: str, force: bool = False) -> Thesis:
        """Generate or return cached investment thesis for symbol.

        Raises:
            RuntimeError: If generation fails
        """
        symbol = symbol.upper()

        if not force:
            existing = self.get_thesis(symbol)
            if existing and existing.status == ThesisStatus.ACTIVE and is_thesis_recent(existing):
                logger.info("thesis_already_recent", symbol=symbol, thesis_id=existing.id)
                return existing

        logger.info("thesis_generation_started", symbol=symbol, force=force)

        try:
            intelligence = self._fetcher.fetch(symbol)
            thesis_data = self._generator.generate_thesis(intelligence)
            claude_validation = self._validator.validate_thesis(intelligence, thesis_data)
            cross_val_score = self._validator.calculate_cross_validation_score(claude_validation)

            existing = self.get_thesis(symbol)
            version = (existing.version + 1) if existing else 1

            thesis = ThesisBuilder.build(
                symbol, thesis_data, claude_validation, cross_val_score, version
            )
            if existing is not None:
                thesis = thesis.model_copy(update={"id": existing.id})
            ensure_symbols_in_watchlist(self._app_storage, [symbol], source="portfolio")
            self._storage.save_thesis(thesis)
            self._storage.save_version(thesis, "updated" if existing else "created")

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
        """Retrieve current active thesis for symbol."""
        return self._storage.get_thesis(symbol)

    def get_thesis_versions(self, symbol: str, limit: int = 10) -> list[ThesisVersion]:
        """Retrieve version history for symbol (newest first)."""
        return self._storage.get_thesis_versions(symbol, limit)

    def invalidate_thesis(self, symbol: str, reason: str) -> Thesis | None:
        """Mark thesis as invalidated and increment version."""
        symbol = symbol.upper()
        thesis = self.get_thesis(symbol)

        if not thesis:
            logger.warning("thesis_not_found_for_invalidation", symbol=symbol)
            return None

        apply_invalidation(thesis, reason)
        self._storage.save_thesis(thesis)
        self._storage.save_version(thesis, "invalidated")
        logger.info(
            "thesis_invalidated",
            thesis_id=thesis.id,
            symbol=symbol,
            version=thesis.version,
            reason=reason,
        )
        return thesis

    def check_invalidation_triggers(self, symbol: str) -> list[str]:
        """Check if any invalidation triggers are met for the active thesis."""
        symbol = symbol.upper()

        try:
            intelligence = self._fetcher.fetch(symbol)
            thesis = self.get_thesis(symbol)

            if not thesis or thesis.status != ThesisStatus.ACTIVE:
                return []

            thesis_action = thesis.action.value
            scores = intelligence.get("scores") or {}
            news = intelligence.get("news") or {}

            triggers = (
                check_signal_triggers(thesis_action, scores.get("signal_type"))
                + check_cross_val_trigger(thesis)
                + check_sentiment_triggers(thesis_action, news.get("sentiment_score"))
            )

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
