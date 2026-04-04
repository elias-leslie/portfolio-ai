"""Helpers for resolving repo-relative paths across host and container layouts."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root(anchor: Path) -> Path:
    """Resolve the repo root when code runs from host or slim container layouts."""
    search_roots = (anchor.parent, *anchor.parents)
    for candidate in search_roots:
        if (candidate / ".index.yaml").exists():
            return candidate
    for candidate in search_roots:
        if (candidate / "alembic.ini").exists() and (candidate / "app").exists():
            return candidate
    return anchor.parents[3]
