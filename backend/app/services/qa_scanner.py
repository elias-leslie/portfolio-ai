"""QA Scanner service stub.

This module is referenced by qa_tasks.py but not yet implemented.
The import is wrapped in a try/except to handle the missing implementation gracefully.
"""

from __future__ import annotations

from typing import Any


class QAScanner:
    """Placeholder for QA Scanner implementation."""

    def scan_all(self) -> list[Any]:
        """Scan all items."""
        return []

    def upsert_issues(self, issues: list[Any]) -> None:
        """Upsert issues."""
        pass

    def auto_resolve_missing(self, issues: list[Any]) -> int:
        """Auto-resolve missing issues."""
        return 0

    def take_snapshot(self) -> dict[str, Any]:
        """Take a snapshot."""
        return {}
