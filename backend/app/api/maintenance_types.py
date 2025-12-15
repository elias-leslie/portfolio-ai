"""TypedDict definitions for maintenance API endpoints.

Response models for monitoring, tasks, and health endpoints.
"""

from __future__ import annotations

from typing import TypedDict


class DiskSpaceResponseDict(TypedDict, total=False):
    """Response from get_disk_space endpoint."""

    partitions: list[dict[str, object]]
    alerts: list[object]
    alert_count: int
    success: bool


class DatabaseSizeResponseDict(TypedDict):
    """Response from get_database_size endpoint."""

    database_size_bytes: int
    database_size_mb: float
    top_tables: list[dict[str, object]]
    success: bool


class MaintenanceScheduleResponseDict(TypedDict):
    """Response from get_maintenance_schedule endpoint."""

    scheduled_tasks: dict[str, dict[str, object]]
    total_count: int


class TaskTriggerResponseDict(TypedDict, total=False):
    """Response from trigger_maintenance_task endpoint."""

    task_id: str  # Required
    task_name: str  # Required
    status: str  # Required: triggered, completed, timeout
    message: str  # Required
    result: dict[str, object] | None  # Optional: task result (if wait_for_result)


class TaskStatusResponseDict(TypedDict, total=False):
    """Response from get_task_status endpoint."""

    task_id: str
    state: str
    ready: bool
    successful: bool | None
    result: object
