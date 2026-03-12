"""Persisted symbol workflow state and transitions."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.logging_config import get_logger
from app.models.symbol_workflow import (
    SymbolWorkflow,
    SymbolWorkflowEvent,
    SymbolWorkflowOutcomeSnapshot,
    SymbolWorkflowPositionContext,
)
from app.portfolio.totals import get_live_portfolio_totals
from app.services.thesis_service import ThesisService
from app.storage import get_storage

logger = get_logger(__name__)

WORKFLOW_STAGES = (
    "discover",
    "thesis_ready",
    "tracked",
    "live",
    "review_due",
    "invalidated",
    "exited",
)

WORKFLOW_SUMMARIES = {
    "discover": "The symbol is on the radar but still needs a worked thesis.",
    "thesis_ready": "The thesis is ready and the symbol can move into active tracking.",
    "tracked": "The symbol is being tracked deliberately before capital is committed.",
    "live": "The symbol is managed as a live position.",
    "review_due": "A portfolio or thesis review is due before the next decision.",
    "invalidated": "The thesis has broken and the symbol should stay out of the active loop.",
    "exited": "The position is closed and the outcome can be reviewed for learning.",
}

WORKFLOW_TRANSITIONS = {
    "discover": ["thesis_ready", "tracked", "invalidated"],
    "thesis_ready": ["tracked", "live", "review_due", "invalidated"],
    "tracked": ["thesis_ready", "live", "review_due", "invalidated"],
    "live": ["review_due", "exited", "invalidated"],
    "review_due": ["tracked", "live", "exited", "invalidated"],
    "invalidated": ["discover", "tracked"],
    "exited": ["discover", "review_due"],
}

OUTCOME_ACTION_STAGE_MAP = {
    "hold": "live",
    "trim": "review_due",
    "exit": "exited",
    "invalidate": "invalidated",
}


def derive_default_stage(
    *,
    has_watchlist_item: bool,
    has_thesis: bool,
    has_live_position: bool,
    has_trade_review: bool,
) -> str:
    if has_live_position:
        return "live"
    if has_trade_review:
        return "review_due"
    if has_thesis:
        return "thesis_ready"
    if has_watchlist_item:
        return "discover"
    return "discover"


def available_transitions_for_stage(stage: str) -> list[str]:
    return WORKFLOW_TRANSITIONS.get(stage, ["discover"])


def stage_for_outcome_action(action: str) -> str:
    normalized = action.strip().lower()
    if normalized not in OUTCOME_ACTION_STAGE_MAP:
        raise ValueError(f"Unsupported outcome action: {action}")
    return OUTCOME_ACTION_STAGE_MAP[normalized]


class SymbolWorkflowService:
    """Load and mutate persisted symbol workflow state."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.thesis_service = ThesisService()

    def get_workflow(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        stored = self._fetch_stored_workflow(symbol)
        if stored is None:
            stage = self._derive_stage_from_existing_data(symbol)
            last_transition_at = datetime.now(UTC).isoformat()
            updated_by = "system"
            notes = None
            next_review_at = self._default_next_review_at(stage)
        else:
            stage = str(stored["stage"])
            last_transition_at = str(stored["last_transition_at"])
            updated_by = str(stored["updated_by"])
            notes = str(stored["notes"]) if stored["notes"] is not None else None
            next_review_at = (
                stored["next_review_at"].isoformat()
                if stored["next_review_at"] is not None
                else None
            )

        workflow = SymbolWorkflow(
            symbol=symbol,
            stage=stage,
            summary=WORKFLOW_SUMMARIES[stage],
            last_transition_at=last_transition_at,
            updated_by=updated_by,
            notes=notes,
            next_review_at=next_review_at,
            available_transitions=available_transitions_for_stage(stage),
            position=self._position_context(symbol),
            latest_outcome=self._latest_outcome(symbol),
            history=self._fetch_history(symbol),
        )
        return workflow.model_dump(mode="json")

    def transition(self, symbol: str, stage: str, note: str | None, updated_by: str = "user") -> dict[str, Any]:
        symbol = symbol.upper()
        if stage not in WORKFLOW_STAGES:
            raise ValueError(f"Unsupported workflow stage: {stage}")

        current = self.get_workflow(symbol)
        from_stage = current["stage"]
        now = datetime.now(UTC)
        note_text = self._normalize_transition_note(note)
        self._apply_stage_side_effect(symbol, stage, note_text)
        self._persist_transition(
            symbol=symbol,
            from_stage=from_stage,
            stage=stage,
            note_text=note_text,
            updated_by=updated_by,
            now=now,
            metadata={},
        )

        return self.get_workflow(symbol)

    def record_outcome(
        self,
        symbol: str,
        action: str,
        note: str | None,
        *,
        jenny_verdict: str | None = None,
        management_action: str | None = None,
        updated_by: str = "user",
    ) -> dict[str, Any]:
        symbol = symbol.upper()
        stage = stage_for_outcome_action(action)
        current = self.get_workflow(symbol)
        from_stage = current["stage"]
        now = datetime.now(UTC)
        note_text = self._normalize_transition_note(note)
        self._apply_stage_side_effect(symbol, stage, note_text)
        position = self._position_context(symbol)
        self._persist_transition(
            symbol=symbol,
            from_stage=from_stage,
            stage=stage,
            note_text=note_text,
            updated_by=updated_by,
            now=now,
            metadata={
                "kind": "outcome_capture",
                "action": action,
                "position": position.model_dump(mode="json") if position is not None else None,
                "jenny": {
                    "verdict": jenny_verdict,
                    "management_action": management_action,
                },
            },
        )

        return self.get_workflow(symbol)

    def _persist_transition(
        self,
        *,
        symbol: str,
        from_stage: str,
        stage: str,
        note_text: str,
        updated_by: str,
        now: datetime,
        metadata: dict[str, Any],
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
                    self._next_review_at_value(stage, now),
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

    def list_priority_workflows(self, limit: int = 3) -> list[dict[str, Any]]:
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

    def _normalize_transition_note(self, note: str | None) -> str:
        normalized = (note or "").strip()
        return normalized or "Workflow updated from product UI."

    def _fetch_stored_workflow(self, symbol: str) -> dict[str, Any] | None:
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

    def _fetch_history(self, symbol: str) -> list[SymbolWorkflowEvent]:
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

    def _derive_stage_from_existing_data(self, symbol: str) -> str:
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
        thesis = self.thesis_service.get_thesis(symbol)
        return derive_default_stage(
            has_watchlist_item=watchlist_exists,
            has_thesis=thesis is not None,
            has_live_position=position_exists,
            has_trade_review=trade_review_exists,
        )

    def _apply_stage_side_effect(self, symbol: str, stage: str, note: str) -> None:
        thesis = self.thesis_service.get_thesis(symbol)
        if stage == "thesis_ready" and thesis is None:
            self.thesis_service.generate_thesis(symbol, force=False)
        if stage == "invalidated" and thesis is not None and thesis.status.value != "invalidated":
            self.thesis_service.invalidate_thesis(symbol, note)

    def _default_next_review_at(self, stage: str) -> str | None:
        next_review = self._next_review_at_value(stage, datetime.now(UTC))
        return next_review.isoformat() if next_review is not None else None

    def _next_review_at_value(self, stage: str, now: datetime) -> datetime | None:
        if stage in {"live", "tracked"}:
            return now + timedelta(days=7)
        if stage == "review_due":
            return now + timedelta(days=3)
        return None

    def _position_context(self, symbol: str) -> SymbolWorkflowPositionContext | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(shares), 0), COALESCE(SUM(shares * cost_basis), 0)
                FROM portfolio_positions
                WHERE symbol = %s
                  AND position_type != 'paper'
                """,
                [symbol],
            ).fetchone()
        if row is None or float(row[0] or 0.0) <= 0:
            return None

        shares = float(row[0] or 0.0)
        total_cost = float(row[1] or 0.0)
        current_price = self.storage.get_current_price(symbol)
        market_value = round(shares * current_price, 2) if current_price is not None else None
        gain_pct = (
            round(((market_value - total_cost) / total_cost) * 100, 2)
            if market_value is not None and total_cost > 0
            else None
        )
        weight_pct: float | None = None
        try:
            totals = get_live_portfolio_totals(self.storage, include_paper=False)
            if market_value is not None and totals.cash_inclusive_total_value > 0:
                weight_pct = round((market_value / totals.cash_inclusive_total_value) * 100, 2)
        except Exception:
            logger.debug("portfolio_weight_calc_failed", exc_info=True)
            weight_pct = None

        return SymbolWorkflowPositionContext(
            shares=shares,
            cost_basis=round(total_cost / shares, 2) if shares > 0 else 0.0,
            market_value=market_value,
            gain_pct=gain_pct,
            weight_pct=weight_pct,
        )

    def _latest_outcome(self, symbol: str) -> SymbolWorkflowOutcomeSnapshot | None:
        for event in self._fetch_history(symbol):
            if event.metadata.get("kind") != "outcome_capture":
                continue
            position_payload = event.metadata.get("position")
            jenny_payload = event.metadata.get("jenny")
            position = (
                SymbolWorkflowPositionContext.model_validate(position_payload)
                if isinstance(position_payload, dict)
                else None
            )
            return SymbolWorkflowOutcomeSnapshot(
                action=str(event.metadata.get("action") or "review"),
                stage=event.to_stage,
                note=event.note,
                created_at=event.created_at,
                jenny_verdict=(
                    str(jenny_payload.get("verdict"))
                    if isinstance(jenny_payload, dict) and jenny_payload.get("verdict")
                    else None
                ),
                management_action=(
                    str(jenny_payload.get("management_action"))
                    if isinstance(jenny_payload, dict) and jenny_payload.get("management_action")
                    else None
                ),
                position=position,
            )
        return None
