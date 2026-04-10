"""Position context and outcome snapshot builder for symbol workflows."""

from __future__ import annotations

from app.api.symbols.builders import build_portfolio_section
from app.api.symbols.portfolio_context import fetch_symbol_portfolio_context
from app.models.symbol_workflow import (
    SymbolWorkflowEvent,
    SymbolWorkflowOutcomeSnapshot,
    SymbolWorkflowPositionContext,
)
from app.storage.facade import PortfolioStorage


class _PositionContextBuilder:
    """Builds position and outcome context for a workflow response."""

    def __init__(self, storage: PortfolioStorage) -> None:
        self.storage = storage

    def build(self, symbol: str) -> SymbolWorkflowPositionContext | None:
        positions_by_symbol, summary = fetch_symbol_portfolio_context(
            self.storage,
            [symbol],
        )
        position_section = build_portfolio_section(
            positions_by_symbol.get(symbol.upper()),
            summary,
        )
        position = position_section.position
        if position is None:
            return None

        return SymbolWorkflowPositionContext(
            shares=position.shares,
            cost_basis=position.cost_basis,
            market_value=round(position.current_value, 2),
            gain_pct=round(position.gain_pct, 2),
            weight_pct=round(position.weight_pct, 2),
        )

    def latest_outcome(self, history: list[SymbolWorkflowEvent]) -> SymbolWorkflowOutcomeSnapshot | None:
        for event in history:
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
