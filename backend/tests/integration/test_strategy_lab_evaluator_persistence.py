"""Integration tests for Strategy Lab evaluator persistence."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest

from app.services.strategy_lab_evaluator import StrategyLabEvaluator
from app.storage import get_storage


@pytest.mark.integration
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
async def test_strategy_lab_evaluation_state_persists_and_transitions_notify() -> None:
    storage = get_storage()
    strategy_id = str(uuid.uuid4())
    symbol = "AAPL"

    with storage.connection() as conn:
        conn.execute(
            "INSERT INTO symbols (symbol, name) VALUES (%s, %s) ON CONFLICT (symbol) DO NOTHING",
            [symbol, "Apple Inc."],
        )
        conn.execute(
            """
            INSERT INTO strategy_screening_results (
                id, symbol, strategy_type, run_date, edge_score, mean_sharpe,
                mean_win_rate, max_drawdown_pct, statistically_significant, significance_level
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            """,
            [strategy_id, symbol, "momentum", date(2026, 5, 19), 1.25, 1.4, 0.58, -0.12, "p05"],
        )
        conn.commit()

    evaluator = StrategyLabEvaluator(storage=storage)

    first = await evaluator.evaluate_all_active_strategies()
    second = await evaluator.evaluate_all_active_strategies()

    with storage.connection() as conn:
        state_row = conn.execute(
            """
            SELECT current_state->>'signal', previous_state, last_evaluated_at
            FROM strategy_lab_evaluation_states
            WHERE strategy_id = %s
            """,
            [strategy_id],
        ).fetchone()
        notification_count_before = _count_notifications(conn, symbol)
        conn.execute(
            """
            UPDATE strategy_screening_results
            SET edge_score = %s
            WHERE id = %s
            """,
            [0.5, strategy_id],
        )
        conn.commit()

    third = await evaluator.evaluate_all_active_strategies()

    with storage.connection() as conn:
        notification_count_after = _count_notifications(conn, symbol)
        transition_row = conn.execute(
            """
            SELECT current_state->>'signal', last_transition->'signal'->>'previous',
                   last_transition->'signal'->>'current'
            FROM strategy_lab_evaluation_states
            WHERE strategy_id = %s
            """,
            [strategy_id],
        ).fetchone()

    assert first == {"strategies_evaluated": 1, "notifications_created": 0}
    assert second == {"strategies_evaluated": 1, "notifications_created": 0}
    assert state_row is not None
    assert state_row[0] == "candidate"
    assert state_row[1] is not None
    assert state_row[2] is not None
    assert notification_count_before == 0
    assert third == {"strategies_evaluated": 1, "notifications_created": 1}
    assert notification_count_after == 1
    assert transition_row == ("watch", "candidate", "watch")


def _count_notifications(conn: Any, symbol: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM jenny_notifications
        WHERE symbol = %s AND category = 'strategy_lab_state_change'
        """,
        [symbol],
    ).fetchone()
    return int(row[0])
