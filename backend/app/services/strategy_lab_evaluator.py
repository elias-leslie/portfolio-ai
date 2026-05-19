"""Async Strategy Lab evaluation worker."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

EVALUATION_INTERVAL_MINUTES = 5
STATE_CHANGE_CATEGORY = "strategy_lab_state_change"
_SIGNIFICANT_STATE_KEYS = (
    "status",
    "signal",
    "severity",
    "edge_score",
    "mean_sharpe",
    "mean_win_rate",
    "max_drawdown_pct",
)


@dataclass(frozen=True)
class StrategyStateDiff:
    """Significant state diff for one strategy."""

    changed: bool
    changes: dict[str, dict[str, Any]]


class StrategyLabEvaluator:
    """Evaluate active strategies, persist state, and emit transition notifications."""

    def __init__(self, storage: Any | None = None) -> None:
        self.storage = storage or get_storage()

    async def evaluate_all_active_strategies(self) -> dict[str, int]:
        """Evaluate all active strategies once."""
        strategies = self._fetch_active_strategies()
        notifications_created = 0

        for strategy in strategies:
            strategy_id = str(strategy["id"])
            previous_state = self._load_current_state(strategy_id)
            current_state = build_current_state(strategy)
            diff = diff_strategy_states(previous_state, current_state)
            self._persist_state(strategy, previous_state, current_state, diff)

            if previous_state is not None and diff.changed:
                self._enqueue_notification(strategy, previous_state, current_state, diff)
                notifications_created += 1

        logger.info(
            "strategy_lab_evaluation_complete",
            strategies_evaluated=len(strategies),
            notifications_created=notifications_created,
        )
        return {
            "strategies_evaluated": len(strategies),
            "notifications_created": notifications_created,
        }

    def _fetch_active_strategies(self) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, symbol, strategy_type, run_date, edge_score, mean_sharpe,
                       mean_win_rate, max_drawdown_pct, statistically_significant,
                       significance_level
                FROM strategy_screening_results
                WHERE statistically_significant = TRUE
                ORDER BY run_date DESC, edge_score DESC NULLS LAST
                """
            ).fetchall()
        return [_strategy_row_to_dict(row) for row in rows]

    def _load_current_state(self, strategy_id: str) -> dict[str, Any] | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT current_state
                FROM strategy_lab_evaluation_states
                WHERE strategy_id = %s
                """,
                [strategy_id],
            ).fetchone()
        if row is None:
            return None
        state = _row_value(row, 0, "current_state")
        return _normalize_state(state) if isinstance(state, dict) else None

    def _persist_state(
        self,
        strategy: dict[str, Any],
        previous_state: dict[str, Any] | None,
        current_state: dict[str, Any],
        diff: StrategyStateDiff,
    ) -> None:
        now = datetime.now(UTC)
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO strategy_lab_evaluation_states (
                    strategy_id, symbol, strategy_type, previous_state, current_state,
                    last_transition, last_evaluated_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (strategy_id) DO UPDATE SET
                    symbol = EXCLUDED.symbol,
                    strategy_type = EXCLUDED.strategy_type,
                    previous_state = EXCLUDED.previous_state,
                    current_state = EXCLUDED.current_state,
                    last_transition = EXCLUDED.last_transition,
                    last_evaluated_at = EXCLUDED.last_evaluated_at,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    str(strategy["id"]),
                    strategy["symbol"],
                    strategy["strategy_type"],
                    previous_state or {},
                    current_state,
                    diff.changes if diff.changed else {},
                    now,
                    now,
                ],
            )
            conn.commit()

    def _enqueue_notification(
        self,
        strategy: dict[str, Any],
        previous_state: dict[str, Any],
        current_state: dict[str, Any],
        diff: StrategyStateDiff,
    ) -> None:
        now = datetime.now(UTC)
        title = f"Strategy state changed: {strategy['symbol']} {strategy['strategy_type']}"
        detail = _format_diff_detail(diff)
        metadata = {
            "strategy_id": str(strategy["id"]),
            "strategy_type": strategy["strategy_type"],
            "previous_state": previous_state,
            "current_state": current_state,
            "changes": diff.changes,
        }
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_notifications (
                    id, routine_id, symbol, category, severity, status, title, detail,
                    recommendation, metadata, created_at
                ) VALUES (%s, NULL, %s, %s, %s, 'open', %s, %s, %s, %s, %s)
                """,
                [
                    str(uuid.uuid4()),
                    strategy["symbol"],
                    STATE_CHANGE_CATEGORY,
                    current_state.get("severity", "info"),
                    title,
                    detail,
                    "Review the Strategy Lab state transition before acting.",
                    metadata,
                    now,
                ],
            )
            conn.commit()


def build_current_state(strategy: dict[str, Any]) -> dict[str, Any]:
    """Build stable comparable state for one active strategy."""
    edge_score = _numeric(strategy.get("edge_score"))
    max_drawdown_pct = _numeric(strategy.get("max_drawdown_pct"))
    signal = "watch"
    severity = "info"
    if edge_score is not None and edge_score >= 1:
        signal = "candidate"
    if max_drawdown_pct is not None and max_drawdown_pct <= -0.2:
        severity = "warning"

    return _normalize_state(
        {
            "status": "active",
            "signal": signal,
            "severity": severity,
            "edge_score": edge_score,
            "mean_sharpe": _numeric(strategy.get("mean_sharpe")),
            "mean_win_rate": _numeric(strategy.get("mean_win_rate")),
            "max_drawdown_pct": max_drawdown_pct,
            "significance_level": strategy.get("significance_level"),
            "run_date": str(strategy.get("run_date")) if strategy.get("run_date") is not None else None,
        }
    )


def diff_strategy_states(
    previous_state: dict[str, Any] | None,
    current_state: dict[str, Any],
) -> StrategyStateDiff:
    """Return significant field changes only."""
    if previous_state is None:
        return StrategyStateDiff(changed=False, changes={})

    previous = _normalize_state(previous_state)
    current = _normalize_state(current_state)
    changes = {
        key: {"previous": previous.get(key), "current": current.get(key)}
        for key in _SIGNIFICANT_STATE_KEYS
        if previous.get(key) != current.get(key)
    }
    return StrategyStateDiff(changed=bool(changes), changes=changes)


def _strategy_row_to_dict(row: Any) -> dict[str, Any]:
    keys = (
        "id",
        "symbol",
        "strategy_type",
        "run_date",
        "edge_score",
        "mean_sharpe",
        "mean_win_rate",
        "max_drawdown_pct",
        "statistically_significant",
        "significance_level",
    )
    return {key: _row_value(row, index, key) for index, key in enumerate(keys)}


def _row_value(row: Any, index: int, key: str) -> Any:
    if isinstance(row, dict):
        return row[key]
    try:
        return row[key]
    except (TypeError, KeyError):
        return row[index]


def _numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(state, sort_keys=True, default=str))


def _format_diff_detail(diff: StrategyStateDiff) -> str:
    parts = [
        f"{key}: {change['previous']} → {change['current']}"
        for key, change in sorted(diff.changes.items())
    ]
    return "; ".join(parts)
