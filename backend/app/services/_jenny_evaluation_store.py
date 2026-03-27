"""Persistence helpers for Jenny agent evaluations."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.thesis import Thesis


def save_agent_evaluation(
    service: Any,
    routine_id: str,
    symbol: str,
    thesis: Thesis | None,
    evaluation: dict[str, Any],
) -> None:
    """Persist a single agent evaluation row to the database."""
    evaluation_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    with service.storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO jenny_agent_evaluations (
                id, routine_id, symbol, agent_name, provider, model, verdict, confidence,
                rationale, recommendation, strengths, weaknesses, metadata, thesis_id, agent_run_id, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s
            )
            """,
            [
                evaluation_id,
                routine_id,
                symbol,
                evaluation["agent_name"],
                evaluation.get("provider"),
                evaluation.get("model"),
                evaluation["verdict"],
                evaluation.get("confidence"),
                evaluation["rationale"],
                evaluation.get("recommendation"),
                json.dumps(evaluation.get("strengths", [])),
                json.dumps(evaluation.get("weaknesses", [])),
                json.dumps(evaluation.get("metadata", {})),
                thesis.id if thesis else None,
                evaluation.get("agent_run_id"),
                now,
            ],
        )
        conn.commit()
