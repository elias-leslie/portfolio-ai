"""Thesis Storage - Database operations for thesis persistence and retrieval."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

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
    ThesisVersion,
)
from ...storage.connection import get_connection_manager

logger = get_logger(__name__)
VALID_CHANGE_REASONS = {"created", "updated", "invalidated", "superseded"}


class ThesisStorageManager:
    """Handles database operations for thesis persistence and retrieval."""

    def __init__(self) -> None:
        """Initialize storage manager."""
        self._conn_mgr = get_connection_manager()

    def save_thesis(self, thesis: Thesis) -> None:
        """Save thesis to database.

        Args:
            thesis: Thesis object to save
        """
        with self._conn_mgr.connection() as conn:
            # Serialize nested objects to JSON
            core_reasons_json = json.dumps([r.model_dump() for r in thesis.core_reasons])
            key_catalysts_json = json.dumps([c.model_dump() for c in thesis.key_catalysts])
            risks_json = json.dumps([r.model_dump() for r in thesis.risks])
            value_drivers_json = (
                json.dumps(thesis.value_drivers.model_dump()) if thesis.value_drivers else None
            )
            claude_validation_json = (
                json.dumps(thesis.claude_validation.model_dump())
                if thesis.claude_validation
                else None
            )
            gemini_validation_json = (
                json.dumps(thesis.gemini_validation.model_dump())
                if thesis.gemini_validation
                else None
            )

            conn.execute(
                """
                INSERT INTO watchlist_thesis (
                    id, symbol, version, status, action,
                    core_reasons, key_catalysts, risks, value_drivers,
                    expected_return_pct, expected_timeframe_days,
                    claude_validation, gemini_validation, cross_validation_score,
                    invalidation_reason, invalidated_at,
                    created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s
                )
                ON CONFLICT (symbol) DO UPDATE SET
                    version = EXCLUDED.version,
                    status = EXCLUDED.status,
                    action = EXCLUDED.action,
                    core_reasons = EXCLUDED.core_reasons,
                    key_catalysts = EXCLUDED.key_catalysts,
                    risks = EXCLUDED.risks,
                    value_drivers = EXCLUDED.value_drivers,
                    expected_return_pct = EXCLUDED.expected_return_pct,
                    expected_timeframe_days = EXCLUDED.expected_timeframe_days,
                    claude_validation = EXCLUDED.claude_validation,
                    gemini_validation = EXCLUDED.gemini_validation,
                    cross_validation_score = EXCLUDED.cross_validation_score,
                    invalidation_reason = EXCLUDED.invalidation_reason,
                    invalidated_at = EXCLUDED.invalidated_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    thesis.id,
                    thesis.symbol,
                    thesis.version,
                    thesis.status.value,
                    thesis.action.value,
                    core_reasons_json,
                    key_catalysts_json,
                    risks_json,
                    value_drivers_json,
                    thesis.expected_return_pct,
                    thesis.expected_timeframe_days,
                    claude_validation_json,
                    gemini_validation_json,
                    thesis.cross_validation_score,
                    thesis.invalidation_reason,
                    thesis.invalidated_at,
                    thesis.created_at,
                    thesis.updated_at,
                ),
            )
            conn.commit()

        logger.info(
            "thesis_saved",
            thesis_id=thesis.id,
            symbol=thesis.symbol,
            version=thesis.version,
            status=thesis.status.value,
        )

    def save_version(self, thesis: Thesis, change_reason: str) -> None:
        """Save thesis version to history.

        Args:
            thesis: Thesis object
            change_reason: Reason for version change
        """
        version_id = str(uuid.uuid4())
        normalized_change_reason = self._normalize_change_reason(change_reason)

        with self._conn_mgr.connection() as conn:
            conn.execute(
                """
                INSERT INTO thesis_versions (
                    id, thesis_id, version, snapshot, change_reason, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (thesis_id, version) DO UPDATE SET
                    snapshot = EXCLUDED.snapshot,
                    change_reason = EXCLUDED.change_reason,
                    created_at = EXCLUDED.created_at
                """,
                (
                    version_id,
                    thesis.id,
                    thesis.version,
                    json.dumps(thesis.model_dump()),
                    normalized_change_reason,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

        logger.info(
            "thesis_version_saved",
            version_id=version_id,
            thesis_id=thesis.id,
            version=thesis.version,
            change_reason=normalized_change_reason,
        )

    def _normalize_change_reason(self, change_reason: str) -> str:
        normalized = change_reason.strip().lower()
        if normalized in VALID_CHANGE_REASONS:
            return normalized
        if normalized.startswith("invalidated"):
            return "invalidated"
        if normalized.startswith("generated") or normalized.startswith("created"):
            return "created"
        if normalized.startswith("updated"):
            return "updated"
        if normalized.startswith("superseded"):
            return "superseded"
        raise ValueError(f"Unsupported thesis version change reason: {change_reason}")

    def get_thesis(self, symbol: str) -> Thesis | None:
        """Retrieve current active thesis for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Thesis object or None if not found
        """
        symbol = symbol.upper()

        with self._conn_mgr.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    id, symbol, version, status, action,
                    core_reasons, key_catalysts, risks, value_drivers,
                    expected_return_pct, expected_timeframe_days,
                    claude_validation, gemini_validation, cross_validation_score,
                    invalidation_reason, invalidated_at,
                    created_at, updated_at
                FROM watchlist_thesis
                WHERE UPPER(symbol) = UPPER(%s)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (symbol,),
            )
            row = result.fetchone()

            if not row:
                return None

            return self._row_to_thesis(row)

    def get_thesis_versions(self, symbol: str, limit: int = 10) -> list[ThesisVersion]:
        """Retrieve version history for symbol.

        Args:
            symbol: Stock symbol
            limit: Maximum number of versions to return

        Returns:
            List of ThesisVersion objects (newest first)
        """
        symbol = symbol.upper()

        with self._conn_mgr.connection() as conn:
            result = conn.execute(
                """
                SELECT tv.id, tv.thesis_id, tv.version, tv.snapshot, tv.change_reason, tv.created_at
                FROM thesis_versions tv
                JOIN watchlist_thesis t ON tv.thesis_id = t.id
                WHERE UPPER(t.symbol) = UPPER(%s)
                ORDER BY tv.created_at DESC
                LIMIT %s
                """,
                (symbol, limit),
            )
            rows = result.fetchall()

            versions = []
            for row in rows:
                # Parse snapshot JSON
                snapshot_str = row[3]
                if isinstance(snapshot_str, str):
                    snapshot = json.loads(snapshot_str)
                else:
                    snapshot = snapshot_str

                # Handle datetime conversion
                created_at_val = row[5]
                if created_at_val is not None and hasattr(created_at_val, "isoformat"):
                    created_at_str = created_at_val.isoformat()
                else:
                    created_at_str = str(created_at_val) if created_at_val else ""

                versions.append(
                    ThesisVersion(
                        id=str(row[0]),
                        thesis_id=str(row[1]),
                        version=int(row[2]) if row[2] is not None else 0,
                        snapshot=snapshot,
                        change_reason=str(row[4]) if row[4] else "",
                        created_at=created_at_str,
                    )
                )

            return versions

    def _row_to_thesis(self, row: tuple[Any, ...]) -> Thesis:
        """Convert database row to Thesis object.

        Args:
            row: Database row tuple

        Returns:
            Thesis object
        """
        # Parse JSONB fields
        core_reasons_raw = row[5]
        if isinstance(core_reasons_raw, str):
            core_reasons_raw = json.loads(core_reasons_raw)
        core_reasons = [ThesisReason(**r) for r in (core_reasons_raw or [])]

        key_catalysts_raw = row[6]
        if isinstance(key_catalysts_raw, str):
            key_catalysts_raw = json.loads(key_catalysts_raw)
        key_catalysts = [ThesisCatalyst(**c) for c in (key_catalysts_raw or [])]

        risks_raw = row[7]
        if isinstance(risks_raw, str):
            risks_raw = json.loads(risks_raw)
        risks = [ThesisRisk(**r) for r in (risks_raw or [])]

        value_drivers_raw = row[8]
        if value_drivers_raw:
            if isinstance(value_drivers_raw, str):
                value_drivers_raw = json.loads(value_drivers_raw)
            value_drivers = ThesisValueDrivers(**value_drivers_raw)
        else:
            value_drivers = None

        claude_validation_raw = row[11]
        if claude_validation_raw:
            if isinstance(claude_validation_raw, str):
                claude_validation_raw = json.loads(claude_validation_raw)
            claude_validation = ThesisValidation(**claude_validation_raw)
        else:
            claude_validation = None

        gemini_validation_raw = row[12]
        if gemini_validation_raw:
            if isinstance(gemini_validation_raw, str):
                gemini_validation_raw = json.loads(gemini_validation_raw)
            gemini_validation = ThesisValidation(**gemini_validation_raw)
        else:
            gemini_validation = None

        # Handle datetime conversion
        created_at = row[16]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        updated_at = row[17]
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()

        invalidated_at = row[15]
        if invalidated_at and hasattr(invalidated_at, "isoformat"):
            invalidated_at = invalidated_at.isoformat()

        return Thesis(
            id=str(row[0]),
            symbol=row[1],
            version=row[2],
            status=ThesisStatus(row[3]),
            action=ThesisAction(row[4]),
            core_reasons=core_reasons,
            key_catalysts=key_catalysts,
            risks=risks,
            value_drivers=value_drivers,
            expected_return_pct=row[9],
            expected_timeframe_days=row[10],
            claude_validation=claude_validation,
            gemini_validation=gemini_validation,
            cross_validation_score=row[13],
            invalidation_reason=row[14],
            invalidated_at=invalidated_at,
            created_at=created_at,
            updated_at=updated_at,
        )
