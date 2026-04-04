"""Tests for repo-root resolution across host and container layouts."""

from __future__ import annotations

from pathlib import Path

from app.utils.project_paths import resolve_project_root


def test_resolve_project_root_from_host_layout(tmp_path: Path) -> None:
    repo_root = tmp_path / "portfolio-ai"
    anchor = repo_root / "backend" / "app" / "config" / "__init__.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (repo_root / ".index.yaml").write_text("project: portfolio-ai\n", encoding="utf-8")

    assert resolve_project_root(anchor) == repo_root


def test_resolve_project_root_from_container_layout(tmp_path: Path) -> None:
    repo_root = tmp_path / "app"
    anchor = repo_root / "app" / "services" / "_jenny_conversation_constants.py"
    anchor.parent.mkdir(parents=True)
    anchor.touch()
    (repo_root / ".index.yaml").write_text("project: portfolio-ai\n", encoding="utf-8")

    assert resolve_project_root(anchor) == repo_root
