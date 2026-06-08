"""Helpers for resolving repo-relative paths across host and container layouts."""

from __future__ import annotations

from pathlib import Path


def resolve_project_root(anchor: Path) -> Path:
    """Resolve the repo root when code runs from host or slim container layouts."""
    search_roots = (anchor.parent, *anchor.parents)
    # Generated marker pins the repo root when present.
    for candidate in search_roots:
        if (candidate / ".index.yaml").exists():
            return candidate
    # Host monorepo root holds backend/ and frontend/ side by side, alongside the
    # repo-local env files. Match this before the backend-only heuristic: the
    # backend directory also has alembic.ini + app, so without this check it gets
    # mistaken for the root whenever the generated marker is absent (e.g. under
    # st-managed builds, which no longer run the legacy rebuild.sh that wrote it).
    for candidate in search_roots:
        if (candidate / "backend").is_dir() and (candidate / "frontend").is_dir():
            return candidate
    # Slim container layout: backend is the root (alembic.ini + app live together).
    for candidate in search_roots:
        if (candidate / "alembic.ini").exists() and (candidate / "app").exists():
            return candidate
    return anchor.parents[3]
