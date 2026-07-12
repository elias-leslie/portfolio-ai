"""Static safety evidence for the source lifecycle cleanup migration."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any


class _RecordingOp:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: Any) -> None:
        self.statements.append(" ".join(str(statement).split()))


def test_cleanup_migration_only_removes_current_snapshots_without_active_aliases() -> None:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "d9e0f1a2b3c4_cleanup_inactive_source_snapshots.py"
    )
    namespace = runpy.run_path(str(migration_path))
    upgrade = namespace["upgrade"]
    recording_op = _RecordingOp()
    upgrade.__globals__["op"] = recording_op

    upgrade()

    assert len(recording_op.statements) == 3
    position_cleanup, cash_cleanup, plaid_cleanup = recording_op.statements
    assert "DELETE FROM portfolio_positions" in position_cleanup
    assert "NOT EXISTS" in position_cleanup
    assert "active_account.is_active = TRUE" in position_cleanup
    assert "active_connection.is_active = TRUE" in position_cleanup
    assert "UPDATE portfolio_accounts" in cash_cleanup
    assert "SET cash_balance = 0" in cash_cleanup
    assert "DELETE FROM household_evidence_accounts" in plaid_cleanup
    assert "item.status <> 'active'" in plaid_cleanup
    combined = " ".join(recording_op.statements)
    assert "DELETE FROM snaptrade_activities" not in combined
    assert "DELETE FROM snaptrade_orders" not in combined
    assert "DELETE FROM household_transactions" not in combined
