"""Sitemap entry dataclass and row conversion utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# Standard SELECT columns for sitemap entries
ENTRY_COLUMNS = """
    id, port, path, method, entry_type, source, title, parent_path,
    health_status, console_errors, console_warnings, http_status,
    response_time_ms, last_error_message, artifact_id,
    last_checked_at, discovered_at
"""


@dataclass
class SitemapEntry:
    """Type-safe representation of a sitemap entry row."""

    id: int
    port: int
    path: str
    method: str | None
    entry_type: str | None
    source: str | None
    title: str | None
    parent_path: str | None
    health_status: str | None
    console_errors: int | None
    console_warnings: int | None
    http_status: int | None
    response_time_ms: float | None
    last_error_message: str | None
    artifact_id: str | None
    last_checked_at: datetime | None
    discovered_at: datetime | None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary with ISO-formatted dates."""
        return {
            "id": self.id,
            "port": self.port,
            "path": self.path,
            "method": self.method,
            "entry_type": self.entry_type,
            "source": self.source,
            "title": self.title,
            "parent_path": self.parent_path,
            "health_status": self.health_status,
            "console_errors": self.console_errors,
            "console_warnings": self.console_warnings,
            "http_status": self.http_status,
            "response_time_ms": self.response_time_ms,
            "last_error_message": self.last_error_message,
            "artifact_id": self.artifact_id,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }


def row_to_entry(row: tuple[object, ...]) -> SitemapEntry:
    """Convert database row tuple to SitemapEntry."""
    last_checked = row[15]
    discovered = row[16]
    return SitemapEntry(
        id=int(row[0]),  # type: ignore[arg-type]
        port=int(row[1]),  # type: ignore[arg-type]
        path=str(row[2]),
        method=str(row[3]) if row[3] is not None else None,
        entry_type=str(row[4]) if row[4] is not None else None,
        source=str(row[5]) if row[5] is not None else None,
        title=str(row[6]) if row[6] is not None else None,
        parent_path=str(row[7]) if row[7] is not None else None,
        health_status=str(row[8]) if row[8] is not None else None,
        console_errors=int(row[9]) if row[9] is not None else None,  # type: ignore[arg-type]
        console_warnings=int(row[10]) if row[10] is not None else None,  # type: ignore[arg-type]
        http_status=int(row[11]) if row[11] is not None else None,  # type: ignore[arg-type]
        response_time_ms=float(row[12]) if row[12] is not None else None,  # type: ignore[arg-type]
        last_error_message=str(row[13]) if row[13] is not None else None,
        artifact_id=str(row[14]) if row[14] is not None else None,
        last_checked_at=last_checked if isinstance(last_checked, datetime) else None,
        discovered_at=discovered if isinstance(discovered, datetime) else None,
    )
