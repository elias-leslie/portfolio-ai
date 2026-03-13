"""Shared TypedDicts for maintenance monitoring and dry-run services."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class DryRunFileInfo(TypedDict):
    """Single file or directory entry from a dry-run cleanup preview."""

    file: str
    size_bytes: int
    age_days: float
    reason: str


class DryRunCategoryReport(TypedDict):
    """Dry-run summary for one cleanup category."""

    category: str
    would_delete_count: int
    would_free_bytes: int
    would_free_mb: float
    files: list[DryRunFileInfo]
    retention_policy: str


class DryRunReportResponse(TypedDict):
    """Aggregate dry-run report across cleanup categories."""

    generated_at: str
    categories: dict[str, DryRunCategoryReport]
    total_would_delete: int
    total_would_free_mb: float
    errors: NotRequired[list[str]]
