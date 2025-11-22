"""Shared Pydantic models for maintenance API.

This module consolidates all request and response models used across
maintenance routers to eliminate duplication.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Response Models (Shared across routers)


class MaintenanceResult(BaseModel):
    """Response model for maintenance task execution."""

    task_id: int = Field(description="Maintenance log entry ID")
    task_name: str = Field(description="Task name")
    status: str = Field(description="Execution status (running/success/error)")
    started_at: datetime = Field(description="Task start timestamp")
    completed_at: datetime | None = Field(description="Task completion timestamp")
    dry_run: bool = Field(description="Whether task ran in dry-run mode")
    summary: dict[str, Any] | None = Field(description="Task execution summary")
    error_message: str | None = Field(default=None, description="Error message if failed")


class MaintenanceHistory(BaseModel):
    """Response model for maintenance history."""

    runs: list[MaintenanceResult] = Field(description="List of maintenance runs")
    total: int = Field(description="Total number of runs")


class LastRunSummary(BaseModel):
    """Response model for last-run summary."""

    cleanup_news: MaintenanceResult | None = Field(description="Last cleanup run")
    vacuum_database: MaintenanceResult | None = Field(description="Last vacuum run")
    validate_integrity: MaintenanceResult | None = Field(description="Last validation run")


# Request Models (Script endpoints)


class CleanupNewsRequest(BaseModel):
    """Request model for cleanup-news endpoint."""

    dry_run: bool = Field(default=True, description="Preview mode without actual deletion")
    days: int = Field(default=90, ge=1, le=365, description="Delete news older than N days")


class VacuumDatabaseRequest(BaseModel):
    """Request model for vacuum-database endpoint."""

    dry_run: bool = Field(default=False, description="Preview mode without actual vacuum")
    tables: list[str] | None = Field(
        default=None, description="Specific tables to vacuum (None = all)"
    )


class ValidateIntegrityRequest(BaseModel):
    """Request model for validate-integrity endpoint."""

    dry_run: bool = Field(default=True, description="Report-only mode without fixes")
