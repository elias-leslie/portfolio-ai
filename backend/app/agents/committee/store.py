"""Append-only persistence for committee runs, events, evidence, and inputs.

Writes go through ``app.storage`` connection pooling. The store is
stateless; concurrent runs are serialized by the per-run UUID + the
monotonic ``seq`` per run_id.

Reads provide the data the SSE replay endpoint needs (events ordered
by seq) and the past-context loader needs (last N decisions for a
symbol).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

from .schemas import (
    Evidence,
    PastDecisionEntry,
    PmDecision,
)

logger = get_logger(__name__)


def create_run(
    *,
    symbol: str,
    household_id: str | None,
    parent_run_id: str | None,
    graph_version: str,
) -> str:
    """Insert a fresh committee_runs row in status='pending'. Returns run_id (uuid str)."""
    run_id = str(uuid.uuid4())
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            """
            INSERT INTO committee_runs
                (id, symbol, household_id, status, parent_run_id, graph_version)
            VALUES (%s, %s, %s, 'pending', %s, %s)
            """,
            (run_id, symbol.upper(), household_id, parent_run_id, graph_version),
        )
        conn.commit()
    return run_id


def mark_running(run_id: str) -> None:
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            "UPDATE committee_runs SET status='running' WHERE id=%s",
            (run_id,),
        )
        conn.commit()


def mark_complete(run_id: str, *, decision: PmDecision, tokens_total: int, cost_usd: float) -> None:
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            """
            UPDATE committee_runs
            SET status='complete',
                completed_at=now(),
                decision_action=%s,
                decision_qty=%s,
                decision_pct_portfolio=%s,
                decision_horizon=%s,
                confidence=%s,
                tokens_total=%s,
                cost_usd=%s
            WHERE id=%s
            """,
            (
                decision.action,
                decision.qty,
                decision.qty_pct,
                decision.horizon,
                decision.confidence,
                tokens_total,
                cost_usd,
                run_id,
            ),
        )
        conn.commit()


def mark_aborted(run_id: str, *, reason: str) -> None:
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            """
            UPDATE committee_runs
            SET status='aborted',
                aborted_at=now(),
                error=%s
            WHERE id=%s
            """,
            (reason, run_id),
        )
        conn.commit()


def mark_failed(run_id: str, *, error: str) -> None:
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            """
            UPDATE committee_runs
            SET status='failed',
                error=%s,
                completed_at=now()
            WHERE id=%s
            """,
            (error, run_id),
        )
        conn.commit()


def mark_approved(run_id: str) -> None:
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            """
            UPDATE committee_runs
            SET status='approved',
                approved_at=now()
            WHERE id=%s
            """,
            (run_id,),
        )
        conn.commit()


def next_seq(run_id: str) -> int:
    """Return the next monotonic seq for this run."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM committee_events WHERE run_id=%s",
            (run_id,),
        ).fetchone()
        return int(row[0]) if row else 0


def persist_event(
    run_id: str,
    *,
    seq: int,
    type: str,
    stage: str | None = None,
    agent_slug: str | None = None,
    role: str | None = None,
    content: dict[str, Any] | None = None,
    score: float | None = None,
    tokens: int | None = None,
    latency_ms: int | None = None,
) -> int:
    """Insert one committee_events row. Returns the event id."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            INSERT INTO committee_events
                (run_id, seq, type, stage, agent_slug, role, content, score, tokens, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            RETURNING id
            """,
            (
                run_id,
                seq,
                type,
                stage,
                agent_slug,
                role,
                json.dumps(content or {}, default=_json_default),
                score,
                tokens,
                latency_ms,
            ),
        ).fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError(f"committee_events insert returned no id for run_id={run_id}")
        return int(row[0])


def persist_evidence(run_id: str, evidence: list[Evidence], *, event_id: int | None = None) -> None:
    """Insert evidence ledger rows."""
    if not evidence:
        return
    cm = get_connection_manager()
    with cm.connection() as conn:
        for item in evidence:
            conn.execute(
                """
                INSERT INTO committee_evidence
                    (run_id, claim, source, side, weight, event_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, item.claim, item.source, item.side, item.weight, event_id),
            )
        conn.commit()


def persist_user_input(
    run_id: str,
    *,
    round_idx: int,
    user_input: str,
    triggered_event_id: int | None = None,
) -> str:
    """Insert a committee_inputs row. Returns the input row id."""
    input_id = str(uuid.uuid4())
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            """
            INSERT INTO committee_inputs
                (id, run_id, round, user_input, triggered_event_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (input_id, run_id, round_idx, user_input, triggered_event_id),
        )
        conn.commit()
    return input_id


def mark_feedback_resolved(input_id: str, *, decision_shifted: bool) -> None:
    cm = get_connection_manager()
    with cm.connection() as conn:
        conn.execute(
            "UPDATE committee_inputs SET decision_shifted=%s WHERE id=%s",
            (decision_shifted, input_id),
        )
        conn.commit()


def load_events(run_id: str) -> list[dict[str, Any]]:
    """Load all events for one run ordered by seq (for SSE replay)."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        rows = conn.execute(
            """
            SELECT seq, ts, type, stage, agent_slug, role, content, score, tokens, latency_ms
            FROM committee_events
            WHERE run_id=%s
            ORDER BY seq
            """,
            (run_id,),
        ).fetchall()
    return [
        {
            "seq": int(row[0]),
            "ts": row[1].isoformat() if isinstance(row[1], datetime) else str(row[1]),
            "type": row[2],
            "stage": row[3],
            "agent_slug": row[4],
            "role": row[5],
            "content": row[6] if isinstance(row[6], dict) else json.loads(row[6] or "{}"),
            "score": float(row[7]) if row[7] is not None else None,
            "tokens": int(row[8]) if row[8] is not None else None,
            "latency_ms": int(row[9]) if row[9] is not None else None,
            "run_id": run_id,
        }
        for row in rows
    ]


def get_run_summary(run_id: str) -> dict[str, Any] | None:
    """Return committee_runs row + paper_trade if any. None if missing."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            SELECT id, symbol, household_id, status, decision_action, decision_qty,
                   decision_pct_portfolio, decision_price, decision_horizon, confidence,
                   bull_score, bear_score, parent_run_id, graph_version,
                   started_at, completed_at, approved_at, aborted_at, error,
                   tokens_total, cost_usd
            FROM committee_runs
            WHERE id=%s
            """,
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "symbol": row[1],
            "household_id": row[2],
            "status": row[3],
            "decision_action": row[4],
            "decision_qty": float(row[5]) if row[5] is not None else None,
            "decision_pct_portfolio": float(row[6]) if row[6] is not None else None,
            "decision_price": float(row[7]) if row[7] is not None else None,
            "decision_horizon": row[8],
            "confidence": float(row[9]) if row[9] is not None else None,
            "bull_score": float(row[10]) if row[10] is not None else None,
            "bear_score": float(row[11]) if row[11] is not None else None,
            "parent_run_id": str(row[12]) if row[12] is not None else None,
            "graph_version": row[13],
            "started_at": row[14].isoformat() if isinstance(row[14], datetime) else row[14],
            "completed_at": row[15].isoformat() if isinstance(row[15], datetime) else row[15],
            "approved_at": row[16].isoformat() if isinstance(row[16], datetime) else row[16],
            "aborted_at": row[17].isoformat() if isinstance(row[17], datetime) else row[17],
            "error": row[18],
            "tokens_total": int(row[19]) if row[19] is not None else 0,
            "cost_usd": float(row[20]) if row[20] is not None else 0.0,
        }


def list_recent_runs(
    household_id: str | None,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Last N committee runs scoped to the household, newest first.

    Mirrors the auth scoping of ``load_past_decisions``: ``NULL``
    household sees only ``NULL``-household runs (single-household mode
    today). Returns the shape the PriorRunsSidebar expects: a compact
    projection (no per-event detail).
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, symbol, status, decision_action, decision_pct_portfolio,
                   confidence, parent_run_id, started_at, completed_at
            FROM committee_runs
            WHERE household_id IS NOT DISTINCT FROM %s
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (household_id, limit),
        ).fetchall()
    return [
        {
            "id": str(row[0]),
            "symbol": row[1],
            "status": row[2],
            "decision_action": row[3],
            "decision_pct_portfolio": float(row[4]) if row[4] is not None else None,
            "confidence": float(row[5]) if row[5] is not None else None,
            "parent_run_id": str(row[6]) if row[6] is not None else None,
            "started_at": row[7].isoformat() if isinstance(row[7], datetime) else row[7],
            "completed_at": row[8].isoformat() if isinstance(row[8], datetime) else row[8],
        }
        for row in rows
    ]


def load_past_decisions(
    symbol: str,
    household_id: str | None,
    *,
    limit: int = 5,
) -> list[PastDecisionEntry]:
    """Last N approved/complete decisions for this symbol + household + their P/L.

    Used by the PM stage (TradingAgents Reflector pattern). Scopes to
    the same household so cross-household decisions do not leak. NULL
    household scope (public/anonymous) sees only NULL-household runs.
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        rows = conn.execute(
            """
            SELECT cr.id, cr.started_at, cr.decision_action, cr.decision_pct_portfolio,
                   cr.decision_horizon, pt.current_pnl
            FROM committee_runs cr
            LEFT JOIN paper_trades pt ON pt.run_id = cr.id
            WHERE cr.symbol = %s
              AND cr.status IN ('complete', 'approved')
              AND cr.household_id IS NOT DISTINCT FROM %s
            ORDER BY cr.started_at DESC
            LIMIT %s
            """,
            (symbol.upper(), household_id, limit),
        ).fetchall()
    return [
        PastDecisionEntry(
            run_id=str(row[0]),
            started_at=row[1],
            action=row[2] or "hold",
            qty_pct=float(row[3]) if row[3] is not None else None,
            horizon=row[4],
            realized_pnl=float(row[5]) if row[5] is not None else None,
        )
        for row in rows
    ]


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
