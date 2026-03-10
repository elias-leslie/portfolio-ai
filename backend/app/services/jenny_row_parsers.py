"""Row parsers for Jenny persistence models."""

from __future__ import annotations

import json
from typing import Any

from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennyNotification,
    JennyRoutine,
    JennyTradeReview,
)


def decode_json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def row_to_routine(row: tuple[Any, ...]) -> JennyRoutine:
    return JennyRoutine(
        id=str(row[0]),
        routine_type=str(row[1]),
        status=str(row[2]),
        triggered_by=str(row[3]),
        summary=str(row[4]) if row[4] else None,
        agents_used=decode_json_value(row[5], []),
        symbols_scanned=int(row[6] or 0),
        notifications_created=int(row[7] or 0),
        started_at=iso(row[8]),
        completed_at=iso(row[9]) if row[9] else None,
        metadata=decode_json_value(row[10], {}),
    )


def row_to_evaluation(row: tuple[Any, ...]) -> JennyAgentEvaluation:
    return JennyAgentEvaluation(
        id=str(row[0]),
        routine_id=str(row[1]),
        symbol=str(row[2]),
        agent_name=str(row[3]),
        provider=str(row[4]) if row[4] else None,
        model=str(row[5]) if row[5] else None,
        verdict=str(row[6]),
        confidence=float(row[7]) if row[7] is not None else None,
        rationale=str(row[8]),
        recommendation=str(row[9]) if row[9] else None,
        strengths=decode_json_value(row[10], []),
        weaknesses=decode_json_value(row[11], []),
        metadata=decode_json_value(row[12], {}),
        thesis_id=str(row[13]) if row[13] else None,
        agent_run_id=str(row[14]) if row[14] else None,
        created_at=iso(row[15]),
    )


def row_to_notification(row: tuple[Any, ...]) -> JennyNotification:
    return JennyNotification(
        id=str(row[0]),
        routine_id=str(row[1]) if row[1] else None,
        symbol=str(row[2]) if row[2] else None,
        category=str(row[3]),
        severity=str(row[4]),
        status=str(row[5]),
        title=str(row[6]),
        detail=str(row[7]),
        recommendation=str(row[8]) if row[8] else None,
        created_at=iso(row[9]),
        acknowledged_at=iso(row[10]) if row[10] else None,
        metadata=decode_json_value(row[11], {}),
    )


def row_to_trade_review(row: tuple[Any, ...]) -> JennyTradeReview:
    return JennyTradeReview(
        id=str(row[0]),
        symbol=str(row[1]),
        thesis_id=str(row[2]) if row[2] else None,
        idea_id=str(row[3]) if row[3] else None,
        review_source=str(row[4]),
        outcome_label=str(row[5]),
        return_pct=float(row[6]) if row[6] is not None else None,
        lesson=str(row[7]),
        what_worked=str(row[8]) if row[8] else None,
        what_failed=str(row[9]) if row[9] else None,
        next_time=str(row[10]) if row[10] else None,
        created_at=iso(row[11]),
        updated_at=iso(row[12]),
        agent_consensus=decode_json_value(row[13], {}),
        metadata=decode_json_value(row[14], {}),
    )


def row_to_scorecard(row: tuple[Any, ...]) -> JennyAgentScorecard:
    return JennyAgentScorecard(
        agent_name=str(row[0]),
        total_evaluations=int(row[1] or 0),
        completed_reviews=int(row[2] or 0),
        positive_verdicts=int(row[3] or 0),
        win_rate=float(row[4]) if row[4] is not None else None,
        avg_return_pct=float(row[5]) if row[5] is not None else None,
        agreement_rate=float(row[6]) if row[6] is not None else None,
        calibration_score=float(row[7]) if row[7] is not None else None,
        entry_quality_score=float(row[8]) if row[8] is not None else None,
        risk_judgment_score=float(row[9]) if row[9] is not None else None,
        exit_timing_score=float(row[10]) if row[10] is not None else None,
        alert_discipline_score=float(row[11]) if row[11] is not None else None,
        strengths=decode_json_value(row[12], []),
        weaknesses=decode_json_value(row[13], []),
        last_evaluation_at=iso(row[14]) if row[14] else None,
        updated_at=iso(row[15]),
    )
