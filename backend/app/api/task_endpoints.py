"""Task monitoring endpoints (Hatchet-backed).

Provides REST API endpoints for inspecting Hatchet workflow runs.
Maintains backward-compatible URL prefix /api/status/celery for
existing frontend consumers, plus new /api/status/tasks prefix.
"""

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.hatchet_inspector import (
    get_queue_depth,
    get_unified_task_list,
)

router = APIRouter(prefix="/api/status/tasks", tags=["tasks"])

# Backward compat: keep /api/status/celery prefix for existing frontend consumers
compat_router = APIRouter(prefix="/api/status/celery", tags=["tasks"])


class TaskInfo(BaseModel):
    """Information about a single workflow run."""

    id: str = Field(..., description="Workflow run ID")
    name: str = Field(..., description="Workflow name")
    status: str = Field(..., description="Run status: RUNNING, PENDING, SUCCEEDED, FAILED")
    started_at: str | None = Field(None, description="ISO timestamp when run started")
    duration: float | None = Field(None, description="Run duration in seconds")
    worker: str | None = Field(None, description="Worker name")
    args: str | None = Field(None, description="JSON string of input data")
    kwargs: str | None = Field(None, description="JSON string of keyword arguments")
    result: str | None = Field(None, description="Run output (completed runs only)")
    traceback: str | None = Field(None, description="Error message (failed runs only)")
    date_done: str | None = Field(None, description="ISO timestamp when run completed")


class TaskListResponse(BaseModel):
    """Response containing list of workflow runs with statistics."""

    tasks: list[TaskInfo] = Field(..., description="List of workflow runs")
    total: int = Field(..., description="Total number of runs returned")
    active_count: int = Field(..., description="Count of running workflows")
    pending_count: int = Field(..., description="Count of pending workflows")
    completed_count: int = Field(..., description="Count of completed workflows")
    failed_count: int = Field(..., description="Count of failed workflows")


class QueueInfo(BaseModel):
    """Queue depth information."""

    depth: int = Field(..., description="Number of pending workflow runs")
    consumers: int = Field(..., description="Number of active workers (always 1 for Hatchet)")


class ScheduleInfo(BaseModel):
    """Workflow schedule information."""

    name: str = Field(..., description="Workflow name")
    task: str = Field(..., description="Hatchet task name")
    schedule: str = Field(..., description="Cron expression")
    last_run: str | None = Field(None, description="Last run timestamp")
    next_run: str | None = Field(None, description="Next run timestamp")


def _get_tasks_response(
    status: Literal["all", "active", "pending", "completed", "failed"],
    limit: int,
    sort: str,
) -> TaskListResponse:
    """Shared implementation for both routers."""
    tasks = get_unified_task_list(status=status, limit=limit)

    if sort == "duration":
        tasks = sorted(tasks, key=lambda t: t.get("duration") or 0, reverse=True)
    elif sort == "name":
        tasks = sorted(tasks, key=lambda t: t.get("name", ""))

    # Map Hatchet statuses to counts
    active_count = sum(1 for t in tasks if t.get("status") == "RUNNING")
    pending_count = sum(1 for t in tasks if t.get("status") in ("PENDING", "QUEUED"))
    completed_count = sum(1 for t in tasks if t.get("status") == "SUCCEEDED")
    failed_count = sum(1 for t in tasks if t.get("status") == "FAILED")

    task_infos = [TaskInfo(**task) for task in tasks]

    return TaskListResponse(
        tasks=task_infos,
        total=len(task_infos),
        active_count=active_count,
        pending_count=pending_count,
        completed_count=completed_count,
        failed_count=failed_count,
    )


def _get_queue_response() -> QueueInfo:
    """Shared implementation for queue endpoint."""
    depth = get_queue_depth()
    return QueueInfo(depth=depth, consumers=1)


def _get_schedule_response() -> list[ScheduleInfo]:
    """Get all registered cron schedules from workflow definitions."""

    # All workflows with on_crons defined
    _SCHEDULED_WORKFLOWS: list[tuple[str, str, str]] = [
        # Maintenance
        ("portfolio-vacuum-db", "vacuum_db_wf", "30 3 * * 0"),
        ("portfolio-cleanup-news", "cleanup_news_wf", "0 4 * * 0"),
        ("portfolio-cleanup-agent-runs", "cleanup_old_agent_runs_wf", "15 4 * * 0"),
        ("portfolio-cleanup-orphaned", "cleanup_orphaned_wf", "30 4 * * 0"),
        ("portfolio-cleanup-backups", "cleanup_old_backups_wf", "45 4 * * 0"),
        ("portfolio-cleanup-models", "cleanup_old_models_wf", "5 5 * * 0"),
        ("portfolio-cleanup-solution-state", "cleanup_solution_state_wf", "25 5 * * 0"),
        ("portfolio-db-size", "db_size_wf", "36 5 * * *"),
        ("portfolio-cleanup-logs", "cleanup_old_logs_wf", "0 2 * * *"),
        ("portfolio-cleanup-temp", "cleanup_temp_wf", "15 2 * * *"),
        ("portfolio-check-disk", "check_disk_space_wf", "0 */6 * * *"),
        ("portfolio-data-freshness", "maintain_data_freshness_wf", "0 */2 * * *"),
        ("portfolio-check-freshness", "check_all_data_freshness_wf", "0 */2 * * *"),
        ("portfolio-source-health", "check_data_source_health_wf", "30 */6 * * *"),
        ("portfolio-cleanup-debug", "cleanup_debug_captures_wf", "15 6 * * *"),
        ("portfolio-cleanup-versions", "cleanup_old_versions_wf", "0 6 * * *"),
        ("portfolio-profile-news", "profile_news_wf", "0 */12 * * *"),
        # Data Refresh
        ("portfolio-refresh-ohlcv", "refresh_daily_ohlcv_wf", "0 2 * * *"),
        ("portfolio-refresh-watchlist-ohlcv", "refresh_watchlist_ohlcv_wf", "15 2 * * *"),
        ("portfolio-backfill-indicators", "backfill_indicators_wf", "30 2 * * *"),
        ("portfolio-fg-inputs", "populate_fear_greed_inputs_wf", "45 2 * * *"),
        ("portfolio-fg-calc", "calculate_fear_greed_wf", "2 3 * * *"),
        ("portfolio-maintain-historical", "maintain_historical_wf", "15 4 * * *"),
        ("portfolio-options-activity", "fetch_options_activity_wf", "15 21 * * *"),
        ("portfolio-putcall-ratio", "fetch_putcall_ratio_wf", "30 14 * * *"),
        ("portfolio-ingest-fundamentals", "ingest_fundamental_data_wf", "10 6 * * 0"),
        ("portfolio-ingest-macro", "ingest_macro_indicators_wf", "30 6 * * *"),
        # Reference
        ("portfolio-yfinance-ref", "yfinance_ref_wf", "2 4 * * *"),
        ("portfolio-valuation-metrics", "valuation_metrics_wf", "30 4 * * *"),
        ("portfolio-analyst-revisions", "refresh_analyst_revisions_wf", "0 7 * * *"),
        ("portfolio-earnings-surprises", "earnings_surprises_wf", "10 5 * * 0"),
        ("portfolio-financial-health", "financial_health_wf", "15 5 * * 0"),
        ("portfolio-risk-metrics", "refresh_risk_metrics_wf", "39 5 * * *"),
        ("portfolio-corporate-actions", "corporate_actions_wf", "30 6 * * 0"),
        ("portfolio-sec-cik", "refresh_sec_cik_wf", "5 6 * * 0"),
        ("portfolio-retrain-ml", "retrain_ml_wf", "0 5 * * *"),
        # Strategy
        ("portfolio-eval-strategy", "eval_strategy_wf", "0 4 * * *"),
        ("portfolio-auto-promote", "auto_promote_wf", "15 4 * * *"),
        ("portfolio-daily-strategy", "daily_strategy_refresh_wf", "15 5 * * *"),
        ("portfolio-weekly-strategy-gen", "weekly_strategy_gen_wf", "0 5 * * 0"),
        ("portfolio-weekly-evolution", "weekly_evolution_wf", "0 6 * * 0"),
        ("portfolio-daily-signals", "daily_signals_wf", "30 21 * * *"),
        ("portfolio-auto-paper-trade", "auto_paper_trade_wf", "45 21 * * *"),
        ("portfolio-snapshots", "portfolio_snapshots_wf", "33 21 * * *"),
        ("portfolio-covariance", "covariance_wf", "30 5 * * *"),
        ("portfolio-rules-validation", "rules_validation_wf", "8 3 * * *"),
        ("portfolio-weekly-optimization", "weekly_optimization_wf", "10 3 * * 1"),
        ("portfolio-strategy-metrics", "strategy_metrics_wf", "0 22 * * *"),
        # Watchlist
        ("portfolio-refresh-watchlist-scores", "refresh_watchlist_scores_wf", "* * * * *"),
        ("portfolio-refresh-news-sentiment", "refresh_news_sentiment_wf", "25 * * * *"),
        ("portfolio-discover-candidates", "discover_candidates_wf", "0 8 * * *"),
        ("portfolio-trim-underperforming", "trim_underperforming_wf", "30 8 * * *"),
        # Agents
        ("portfolio-run-discovery-agent", "run_discovery_agent_wf", "36 3 * * *"),
        ("portfolio-run-portfolio-analyzer", "run_portfolio_analyzer_wf", "39 3 * * *"),
        ("portfolio-update-paper-trades", "update_paper_trades_wf", "36 21 * * *"),
        # Monitoring
        ("portfolio-qa-scan", "qa_scan_wf", "0 4 * * *"),
        ("portfolio-generate-sitemap", "generate_sitemap_wf", "0 5 * * *"),
        ("portfolio-monitor-theses", "monitor_theses_wf", "0 3 * * *"),
    ]

    return [
        ScheduleInfo(
            name=name,
            task=name,
            schedule=cron,
            last_run=None,
            next_run=None,
        )
        for name, _wf_name, cron in _SCHEDULED_WORKFLOWS
    ]


# === New /api/status/tasks endpoints ===

@router.get("/tasks", response_model=TaskListResponse)
def get_tasks(
    status: Literal["all", "active", "pending", "completed", "failed"] = Query(
        "all", description="Filter by status"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of runs to return"),
    sort: Literal["time", "duration", "name"] = Query("time", description="Sort order"),
) -> TaskListResponse:
    """Get unified list of Hatchet workflow runs."""
    return _get_tasks_response(status, limit, sort)


@router.get("/queue", response_model=QueueInfo)
def get_queue() -> QueueInfo:
    """Get pending workflow run count."""
    return _get_queue_response()


@router.get("/schedule", response_model=list[ScheduleInfo])
def get_schedule() -> list[ScheduleInfo]:
    """Get all registered cron schedules."""
    return _get_schedule_response()


# === Backward-compatible /api/status/celery endpoints ===

@compat_router.get("/tasks", response_model=TaskListResponse)
def get_celery_tasks_compat(
    status: Literal["all", "active", "pending", "completed", "failed"] = Query(
        "all", description="Filter by status"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of runs to return"),
    sort: Literal["time", "duration", "name"] = Query("time", description="Sort order"),
) -> TaskListResponse:
    """Get unified list of workflow runs (backward-compatible)."""
    return _get_tasks_response(status, limit, sort)


@compat_router.get("/queue", response_model=QueueInfo)
def get_celery_queue_compat() -> QueueInfo:
    """Get pending run count (backward-compatible)."""
    return _get_queue_response()


@compat_router.get("/schedule", response_model=list[ScheduleInfo])
def get_celery_schedule_compat() -> list[ScheduleInfo]:
    """Get cron schedules (backward-compatible)."""
    return _get_schedule_response()
