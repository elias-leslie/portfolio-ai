"""Persisted symbol workflow state and transitions."""

from __future__ import annotations

from datetime import UTC, datetime

from app.logging_config import get_logger
from app.models.symbol_workflow import SymbolWorkflow
from app.services.thesis_service import ThesisService
from app.storage import get_storage

from ._symbol_workflow_constants import (
    OUTCOME_ACTION_STAGE_MAP,
    WORKFLOW_STAGES,
    WORKFLOW_SUMMARIES,
    WORKFLOW_TRANSITIONS,
    available_transitions_for_stage,
    derive_default_stage,
    stage_for_outcome_action,
)
from ._symbol_workflow_context import _PositionContextBuilder
from ._symbol_workflow_store import _next_review_at_value, _WorkflowStore

__all__ = [
    "OUTCOME_ACTION_STAGE_MAP",
    "WORKFLOW_STAGES",
    "WORKFLOW_SUMMARIES",
    "WORKFLOW_TRANSITIONS",
    "SymbolWorkflowService",
    "available_transitions_for_stage",
    "derive_default_stage",
    "stage_for_outcome_action",
]

logger = get_logger(__name__)


class SymbolWorkflowService:
    """Load and mutate persisted symbol workflow state."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.thesis_service = ThesisService()
        self._store = _WorkflowStore(self.storage)
        self._position_builder = _PositionContextBuilder(self.storage)

    def get_workflow(self, symbol: str) -> dict[str, object]:
        symbol = symbol.upper()
        stored = self._store.fetch_stored(symbol)
        if stored is None:
            stage = self._store.derive_stage_from_existing_data(symbol, self.thesis_service)
            last_transition_at = datetime.now(UTC).isoformat()
            updated_by = "system"
            notes = None
            now = datetime.now(UTC)
            next_review = _next_review_at_value(stage, now)
            next_review_at = next_review.isoformat() if next_review is not None else None
        else:
            stage = str(stored["stage"])
            last_transition_at = str(stored["last_transition_at"])
            updated_by = str(stored["updated_by"])
            notes = str(stored["notes"]) if stored["notes"] is not None else None
            raw_review_at = stored["next_review_at"]
            next_review_at = (
                raw_review_at.isoformat()
                if isinstance(raw_review_at, datetime)
                else None
            )

        history = self._store.fetch_history(symbol)
        workflow = SymbolWorkflow(
            symbol=symbol,
            stage=stage,
            summary=WORKFLOW_SUMMARIES[stage],
            last_transition_at=last_transition_at,
            updated_by=updated_by,
            notes=notes,
            next_review_at=next_review_at,
            available_transitions=available_transitions_for_stage(stage),
            position=self._position_builder.build(symbol),
            latest_outcome=self._position_builder.latest_outcome(history),
            history=history,
        )
        return workflow.model_dump(mode="json")

    def transition(self, symbol: str, stage: str, note: str | None, updated_by: str = "user") -> dict[str, object]:
        symbol = symbol.upper()
        if stage not in WORKFLOW_STAGES:
            raise ValueError(f"Unsupported workflow stage: {stage}")
        current = self.get_workflow(symbol)
        from_stage = str(current["stage"])
        now = datetime.now(UTC)
        note_text = self._normalize_transition_note(note)
        self._apply_stage_side_effect(symbol, stage, note_text)
        self._store.persist_transition(
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
    ) -> dict[str, object]:
        symbol = symbol.upper()
        stage = stage_for_outcome_action(action)
        current = self.get_workflow(symbol)
        from_stage = str(current["stage"])
        now = datetime.now(UTC)
        note_text = self._normalize_transition_note(note)
        self._apply_stage_side_effect(symbol, stage, note_text)
        position = self._position_builder.build(symbol)
        self._store.persist_transition(
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

    def list_priority_workflows(self, limit: int = 3) -> list[dict[str, object]]:
        return self._store.list_priority(limit)

    def _normalize_transition_note(self, note: str | None) -> str:
        return _WorkflowStore.normalize_note(note)

    def _apply_stage_side_effect(self, symbol: str, stage: str, note: str) -> None:
        thesis = self.thesis_service.get_thesis(symbol)
        if stage == "thesis_ready" and thesis is None:
            self.thesis_service.generate_thesis(symbol, force=False)
        if stage == "invalidated" and thesis is not None and thesis.status.value != "invalidated":
            self.thesis_service.invalidate_thesis(symbol, note)
