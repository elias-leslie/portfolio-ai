"""Pydantic models for backup API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TreeEntry(BaseModel):
    """File count for a directory/file in the backup."""

    count: int


class BackupVerification(BaseModel):
    """Verification results for a backup."""

    verified: bool
    verified_at: str
    errors: list[str]
    tree: dict[str, TreeEntry]
    total_files: int
    checksum: str


class BackupEntry(BaseModel):
    """Individual backup entry."""

    name: str
    timestamp: str
    size_bytes: int
    db_size_bytes: int
    status: Literal["ok", "failed", "in_progress"]
    verification: BackupVerification | None = None


class BackupIndexResponse(BaseModel):
    """Backup index response."""

    version: int
    retention: int
    destination: str
    backups: list[BackupEntry]
    last_updated: str | None


class BackupStatusResponse(BaseModel):
    """Backup status summary response."""

    status: Literal["healthy", "stale", "no_backups", "error"]
    latest_backup: BackupEntry | None
    backup_count: int
    destination: str
    last_updated: str | None
    message: str


class TriggerBackupResponse(BaseModel):
    """Response when triggering a backup."""

    job_id: str
    status: Literal["started", "already_running"]
    message: str


class BackupJobStatus(BaseModel):
    """Status of a running or completed backup job."""

    job_id: str
    status: Literal["running", "completed", "failed", "not_found"]
    started_at: str | None
    completed_at: str | None
    output: str | None = Field(None, description="Command output (truncated)")
    error: str | None


class BackupRequirementCheck(BaseModel):
    """Result of checking if backup requirements are met for maintenance ops."""

    backup_exists: bool = Field(..., description="Whether any backup exists")
    backup_recent: bool = Field(..., description="Whether backup is within max_age_hours")
    backup_verified: bool = Field(..., description="Whether latest backup passed verification")
    backup_name: str | None = Field(None, description="Name of latest backup")
    backup_age_hours: float | None = Field(None, description="Age of latest backup in hours")
    can_proceed: bool = Field(..., description="Whether maintenance can proceed")
    blocking_reason: str | None = Field(None, description="Reason if can_proceed is False")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking warnings")
