from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import polars as pl

from app.utils.health_workflows import get_workflow_health


def test_get_workflow_health_treats_no_terminal_runs_as_healthy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.utils.health_workflows._query_workflow_health_data",
        lambda _storage: (
            pl.DataFrame(schema={"workflow_type": pl.String, "status": pl.String, "count": pl.Int64}),
            pl.DataFrame([{"total": 2}]),
            pl.DataFrame(
                {
                    "id": ["wf-success"],
                    "workflow_type": ["jenny_weekly_learning"],
                    "completed_at": [datetime(2026, 4, 6, 1, 41, 36, tzinfo=UTC)],
                }
            ),
            pl.DataFrame(schema={"workflow_type": pl.String, "count": pl.Int64}),
        ),
    )

    health = get_workflow_health(Mock())

    assert health.status == "healthy"
    assert health.total_workflows_24h == 2
    assert health.successful_workflows == 0
    assert health.failed_workflows == 0
    assert health.blocked_workflows == 0
    assert health.success_rate == 0


def test_get_workflow_health_counts_overdue_running_workflows_as_blocked(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.utils.health_workflows._query_workflow_health_data",
        lambda _storage: (
            pl.DataFrame(schema={"workflow_type": pl.String, "status": pl.String, "count": pl.Int64}),
            pl.DataFrame([{"total": 2}]),
            pl.DataFrame(
                {
                    "id": ["wf-success"],
                    "workflow_type": ["jenny_weekly_learning"],
                    "completed_at": [datetime(2026, 4, 6, 1, 41, 36, tzinfo=UTC)],
                }
            ),
            pl.DataFrame([{"workflow_type": "jenny_daily_operator", "count": 2}]),
        ),
    )

    health = get_workflow_health(Mock())

    assert health.status == "warning"
    assert health.total_workflows_24h == 2
    assert health.blocked_workflows == 2
    assert health.blocked_by_type == {"jenny_daily_operator": 2}


def test_get_workflow_health_uses_terminal_runs_for_success_rate(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.utils.health_workflows._query_workflow_health_data",
        lambda _storage: (
            pl.DataFrame([{"workflow_type": "jenny_weekly_learning", "status": "complete", "count": 1}]),
            pl.DataFrame([{"total": 3}]),
            pl.DataFrame(
                {
                    "id": ["wf-success"],
                    "workflow_type": ["jenny_weekly_learning"],
                    "completed_at": [datetime(2026, 4, 6, 1, 41, 36, tzinfo=UTC)],
                }
            ),
            pl.DataFrame([{"workflow_type": "jenny_daily_operator", "count": 2}]),
        ),
    )

    health = get_workflow_health(Mock())

    assert health.success_rate == 100
    assert health.status == "warning"
    assert health.successful_workflows == 1
    assert health.failed_workflows == 0
    assert health.blocked_workflows == 2
