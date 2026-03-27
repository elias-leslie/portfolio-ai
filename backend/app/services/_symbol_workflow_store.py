"""Low-level SQL helpers for symbol workflow persistence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from app.logging_config import get_logger
from app.models.symbol_workflow import SymbolWorkflowEvent
from app.services.thesis_service import ThesisService
from app.storage.facade import PortfolioStorage

from ._symbol_workflow_constants import (
    derive_default_stage,
)

logger = get_logger(__name__)


def _next_review_at_value(stage: str, now: datetime) -> datetime | None:
    if stage in {"live", "tracked"}:
        return now + timedelta(days=7)
    if stage == "review_due":
        return now + timedelta(days=3)
    return None


class _WorkflowStore:
    """Low-level SQL helpers for workflow persistence."""

    def __init__(self, storage: PortfolioStorage) -> None:
        self.storage = storage

    def fetch_stored(self, symbol: str) -> dict[str, object] | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT symbol, current_stage, notes, updated_by, last_transition_at, next_review_at
                FROM symbol_workflows
                WHERE symbol = %s
                """,
                [symbol],
            ).fetchone()
        if row is None:
            return None
        return {
            "symbol": row[0],
            "stage": row[1],
            "notes": row[2],
            "updated_by": row[3],
            "last_transition_at": row[4],
            "next_review_at": row[5],
        }

    def fetch_history(self, symbol: str) -> list[SymbolWorkflowEvent]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, symbol, from_stage, to_stage, note, created_by, created_at, metadata
                FROM symbol_workflow_events
                WHERE symbol = %s
                ORDER BY created_at DESC
                LIMIT 8
                """,
                [symbol],
            ).fetchall()
        return [
            SymbolWorkflowEvent(
                id=str(row[0]),
                symbol=str(row[1]),
                from_stage=str(row[2]) if row[2] is not None else None,
                to_stage=str(row[3]),
                note=str(row[4]),
                created_by=str(row[5]),
                created_at=row[6].isoformat(),
                metadata=row[7] if isinstance(row[7], dict) else {},
            )
            for row in rows
        ]

    def derive_stage_from_existing_data(self, symbol: str, thesis_service: ThesisService) -> str:
        with self.storage.connection() as conn:
            watchlist_exists = bool(
                conn.execute("SELECT 1 FROM watchlist_items WHERE symbol = %s LIMIT 1", [symbol]).fetchone()
            )
            position_exists = bool(
                conn.execute(
                    """
                    SELECT 1
                    FROM portfolio_positions p
                    JOIN portfolio_accounts a ON a.id = p.account_id
                    WHERE p.symbol = %s AND a.account_type != 'paper'
                    LIMIT 1
                    """,
                    [symbol],
                ).fetchone()
            )
            trade_review_exists = bool(
                conn.execute(
                    "SELECT 1 FROM jenny_trade_reviews WHERE symbol = %s LIMIT 1",
                    [symbol],
                ).fetchone()
            )
        thesis = thesis_service.get_thesis(symbol)
        return derive_default_stage(
            has_watchlist_item=watchlist_exists,
            has_thesis=thesis is not None,
            has_live_position=position_exists,
            has_trade_review=trade_review_exists,
        )

    def persist_transition(
        self,
        *,
        symbol: str,
        from_stage: str,
        stage: str,
        note_text: str,
        updated_by: str,
        now: datetime,
        metadata: dict[str, object],
    ) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO symbol_workflows (
                    symbol, current_stage, notes, updated_by, last_transition_at,
                    next_review_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE SET
                    current_stage = EXCLUDED.current_stage,
                    notes = EXCLUDED.notes,
                    updated_by = EXCLUDED.updated_by,
                    last_transition_at = EXCLUDED.last_transition_at,
                    next_review_at = EXCLUDED.next_review_at,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    symbol,
                    stage,
                    note_text,
                    updated_by,
                    now,
                    _next_review_at_value(stage, now),
                    now,
                    now,
                ],
            )
            conn.execute(
                """
                INSERT INTO symbol_workflow_events (
                    id, symbol, from_stage, to_stage, note, created_by, created_at, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                [
                    str(uuid.uuid4()),
                    symbol,
                    from_stage,
                    stage,
                    note_text,
                    updated_by,
                    now,
                    json.dumps(metadata),
                ],
            )
            conn.commit()

    def list_priority(self, limit: int) -> list[dict[str, object]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT symbol, current_stage, last_transition_at
                FROM symbol_workflows
                WHERE current_stage IN ('review_due', 'invalidated', 'exited')
                ORDER BY last_transition_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [
            {
                "symbol": str(row[0]),
                "stage": str(row[1]),
                "last_transition_at": row[2].isoformat() if row[2] is not None else None,
            }
            for row in rows
        ]

    @staticmethod
    def normalize_note(note: str | None) -> str:
        normalized = (note or "").strip()
        return normalized or "Workflow updated from product UI."
