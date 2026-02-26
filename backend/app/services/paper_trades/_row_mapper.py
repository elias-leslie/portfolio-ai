"""Row-to-model conversion for paper trade database results."""

from __future__ import annotations

from typing import Literal

from app.models.paper_trades import PaperTradeResponse

_VALID_IDEA_TYPES: frozenset[str] = frozenset({"buy", "sell"})


def _opt_float(val: object) -> float | None:
    return float(val) if val is not None else None  # type: ignore[arg-type]


def _opt_int(val: object) -> int | None:
    return int(val) if val is not None else None  # type: ignore[arg-type]


def _opt_str(val: object) -> str | None:
    return str(val) if val else None


def _idea_type(val: object) -> Literal["buy", "sell"]:
    s = str(val) if val else ""
    return s if s in _VALID_IDEA_TYPES else "buy"  # type: ignore[return-value]


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
    """
    return PaperTradeResponse(
        idea_id=str(row[0]) if row[0] else "",
        agent_run_id=str(row[1]) if row[1] else "",
        symbol=str(row[2]) if row[2] else "",
        idea_type=_idea_type(row[3]),
        shares=_opt_int(row[4]),
        entry_price=_opt_float(row[5]),
        entry_amount=_opt_float(row[6]),
        entry_date=_opt_str(row[7]),
        target_price=_opt_float(row[8]),
        stop_loss_price=_opt_float(row[9]),
        current_price=_opt_float(row[10]),
        current_return_pct=_opt_float(row[11]),
        status=str(row[12]) if row[12] else "",
        exit_price=_opt_float(row[13]),
        exit_date=_opt_str(row[14]),
        exit_reason=_opt_str(row[15]),
        realized_return_pct=_opt_float(row[16]),
        holding_days=_opt_int(row[17]),
        max_favorable_pct=_opt_float(row[18]),
        max_adverse_pct=_opt_float(row[19]),
        thesis=_opt_str(row[20]),
        confidence_score=_opt_float(row[21]),
        risk_level=_opt_str(row[22]),
        strategy_id=_opt_str(row[23]),
    )
