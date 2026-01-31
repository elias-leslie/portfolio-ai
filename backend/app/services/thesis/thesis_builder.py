"""Thesis Builder - Constructs Thesis objects from thesis data."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from ...logging_config import get_logger
from ...models.thesis import (
    Thesis,
    ThesisAction,
    ThesisCatalyst,
    ThesisReason,
    ThesisRisk,
    ThesisStatus,
    ThesisValidation,
    ThesisValueDrivers,
)

logger = get_logger(__name__)


class ThesisBuilder:
    """Builds Thesis objects from thesis data with validation."""

    @staticmethod
    def build(
        symbol: str,
        thesis_data: dict[str, Any],
        claude_validation: ThesisValidation,
        cross_val_score: float,
        version: int,
    ) -> Thesis:
        """Build Thesis object from thesis data.

        Args:
            symbol: Stock symbol
            thesis_data: Thesis data from LLM
            claude_validation: Claude validation result
            cross_val_score: Cross-validation score
            version: Thesis version number

        Returns:
            Thesis object
        """
        now = datetime.now(UTC).isoformat()

        # Parse thesis components with error handling
        try:
            core_reasons = [ThesisReason(**r) for r in thesis_data.get("core_reasons", [])]
        except ValidationError as e:
            logger.warning("core_reasons_parse_failed", error=str(e))
            core_reasons = []

        try:
            key_catalysts = [ThesisCatalyst(**c) for c in thesis_data.get("key_catalysts", [])]
        except ValidationError as e:
            logger.warning("key_catalysts_parse_failed", error=str(e))
            key_catalysts = []

        try:
            risks = [ThesisRisk(**r) for r in thesis_data.get("risks", [])]
        except ValidationError as e:
            logger.warning("risks_parse_failed", error=str(e))
            risks = []

        value_drivers = None
        if thesis_data.get("value_drivers"):
            try:
                value_drivers = ThesisValueDrivers(**thesis_data["value_drivers"])
            except ValidationError as e:
                logger.warning("value_drivers_parse_failed", error=str(e))

        return Thesis(
            id=str(uuid.uuid4()),
            symbol=symbol,
            version=version,
            status=ThesisStatus.ACTIVE,
            action=ThesisAction(thesis_data.get("action", "HOLD")),
            core_reasons=core_reasons,
            key_catalysts=key_catalysts,
            risks=risks,
            value_drivers=value_drivers,
            expected_return_pct=thesis_data.get("expected_return_pct"),
            expected_timeframe_days=thesis_data.get("expected_timeframe_days"),
            claude_validation=claude_validation,
            gemini_validation=None,  # Not implementing Gemini validation of Claude for now
            cross_validation_score=cross_val_score,
            invalidation_reason=None,
            invalidated_at=None,
            created_at=now,
            updated_at=now,
        )
