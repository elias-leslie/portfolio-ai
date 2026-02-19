"""Row-to-model conversion for paper trade database results."""

from __future__ import annotations

from typing import cast

from app.models.paper_trades import PaperTradeResponse


def row_to_paper_trade_response(row: tuple[object, ...]) -> PaperTradeResponse:
    """Convert database row tuple to PaperTradeResponse model.

    Column indices:
        0=idea_id, 1=agent_run_id, 2=symbol, 3=idea_type, 4=shares,
        5=entry_price, 6=entry_amount, 7=entry_date, 8=target_price,
        9=stop_loss_price, 10=current_price, 11=current_return_pct,
        12=status, 13=exit_price, 14=exit_date, 15=exit_reason,
        16=realized_return_pct, 17=holding_days, 18=max_favorable_pct,
        19=max_adverse_pct, 20=thesis, 21=confidence_score, 22=risk_level,
        23=strategy_id

    Args:
        row: Tuple from database query

    Returns:
        PaperTradeResponse model instance
    """
    return PaperTradeResponse(
        idea_id=str(row[0]) if row[0] else "",
        agent_run_id=str(row[1]) if row[1] else "",
        symbol=str(row[2]) if row[2] else "",
        idea_type=str(row[3]) if row[3] in ["buy", "sell"] else "buy",  # type: ignore[arg-type]
        shares=int(cast(int, row[4])) if row[4] is not None else None,
        entry_price=float(cast(float, row[5])) if row[5] is not None else None,
        entry_amount=float(cast(float, row[6])) if row[6] is not None else None,
        entry_date=str(row[7]) if row[7] else None,
        target_price=float(cast(float, row[8])) if row[8] is not None else None,
        stop_loss_price=float(cast(float, row[9])) if row[9] is not None else None,
        current_price=float(cast(float, row[10])) if row[10] is not None else None,
        current_return_pct=float(cast(float, row[11])) if row[11] is not None else None,
        status=str(row[12]) if row[12] else "",
        exit_price=float(cast(float, row[13])) if row[13] is not None else None,
        exit_date=str(row[14]) if row[14] else None,
        exit_reason=str(row[15]) if row[15] else None,
        realized_return_pct=float(cast(float, row[16])) if row[16] is not None else None,
        holding_days=int(cast(int, row[17])) if row[17] is not None else None,
        max_favorable_pct=float(cast(float, row[18])) if row[18] is not None else None,
        max_adverse_pct=float(cast(float, row[19])) if row[19] is not None else None,
        thesis=str(row[20]) if row[20] else None,
        confidence_score=float(cast(float, row[21])) if row[21] is not None else None,
        risk_level=str(row[22]) if row[22] else None,
        strategy_id=str(row[23]) if row[23] else None,
    )
