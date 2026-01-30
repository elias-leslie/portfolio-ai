"""TypedDict definitions for monitoring endpoints.

Response models and data structures for file cleanup, cache, and dry-run reporting.
"""

from __future__ import annotations

from typing import TypedDict


class FileCleanupInfo(TypedDict):
    """Info about a file cleanup category."""

    path: str
    size_mb: float
    file_count: int
    retention_policy: str
    schedule: str


class FileCleanupStatusResponse(TypedDict):
    """Response for file cleanup status endpoint."""

    logs: FileCleanupInfo
    backups: FileCleanupInfo
    models: FileCleanupInfo
    solution_state: FileCleanupInfo
    total_size_mb: float


class CacheDirectoryInfo(TypedDict):
    """Info about a cache directory."""

    name: str
    path: str
    size_mb: float
    file_count: int
    description: str


class CacheStatusResponse(TypedDict):
    """Response for cache status endpoint."""

    directories: list[CacheDirectoryInfo]
    total_size_mb: float
    total_file_count: int


class DryRunFileInfo(TypedDict):
    """Info about files that would be deleted in a dry run."""

    file: str
    size_bytes: int
    age_days: float
    reason: str


class DryRunCategoryReport(TypedDict):
    """Dry run report for a single category."""

    category: str
    would_delete_count: int
    would_free_bytes: int
    would_free_mb: float
    files: list[DryRunFileInfo]
    retention_policy: str


class DryRunReportResponse(TypedDict):
    """Full dry run report response."""

    generated_at: str
    categories: dict[str, DryRunCategoryReport]
    total_would_delete: int
    total_would_free_mb: float
