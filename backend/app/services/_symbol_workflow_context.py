"""Position context and outcome snapshot builder for symbol workflows."""

from __future__ import annotations

from app.logging_config import get_logger
from app.models.symbol_workflow import (
    SymbolWorkflowEvent,
    SymbolWorkflowOutcomeSnapshot,
    SymbolWorkflowPositionContext,
)
from app.portfolio.totals import get_live_portfolio_totals
from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


class _PositionContextBuilder:
    """Builds position and outcome context for a workflow response."""

    def __init__(self, storage: PortfolioStorage) -> None:
        self.storage = storage

    def build(self, symbol: str) -> SymbolWorkflowPositionContext | None:
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
        weight_pct = self._portfolio_weight(market_value)

        return SymbolWorkflowPositionContext(
            shares=shares,
            cost_basis=round(total_cost / shares, 2) if shares > 0 else 0.0,
            market_value=market_value,
            gain_pct=gain_pct,
            weight_pct=weight_pct,
        )

    def _portfolio_weight(self, market_value: float | None) -> float | None:
        if market_value is None:
            return None
        try:
            totals = get_live_portfolio_totals(self.storage, include_paper=False)
            if totals.cash_inclusive_total_value > 0:
                return round((market_value / totals.cash_inclusive_total_value) * 100, 2)
        except Exception:
            logger.debug("portfolio_weight_calc_failed", exc_info=True)
        return None

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
