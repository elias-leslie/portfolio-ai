"""Git automation for autonomous workflow results.

Capabilities:
- Creates snapshot files in reports/autonomous/ directory
- Commits workflow results with formatted messages to main branch
- Auto-pushes commits to remote (origin/main)
- Graceful error handling (git failures don't crash workflows)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from typing import Any

from app.utils import safe_subprocess

from ..logging_config import get_logger

logger = get_logger(__name__)


class GitAutomationError(Exception):
    """Base exception for git automation errors."""

    pass


def commit_workflow_results(
    workflow_type: str,
    date: datetime | str,
    result_summary: str,
    snapshot_data: dict[str, Any],
) -> bool:
    """Commit workflow results to git with snapshot file.

    Creates a JSON snapshot file in reports/autonomous/ directory,
    stages it with git add, commits with a formatted message,
    and auto-pushes to origin/main.

    Args:
        workflow_type: Type of workflow (e.g., "daily_gap_analysis")
        date: Date of workflow execution (datetime or string YYYY-MM-DD)
        result_summary: Human-readable summary of results
        snapshot_data: Dictionary containing workflow results to save as JSON

    Returns:
        True if commit and push succeeded, False if any step failed
        (failures are logged but do not raise exceptions)
    """
    try:
        date_str = _parse_date(date)
        if date_str is None:
            return False

        repo_root = _get_repo_root()
        if not repo_root:
            logger.warning("git_not_in_repository")
            return False

        return _execute_git_workflow(
            repo_root, workflow_type, date_str, result_summary, snapshot_data
        )

    except Exception as e:
        logger.error(
            "git_automation_unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return False


def _parse_date(date: datetime | str) -> str | None:
    """Parse date argument to YYYY-MM-DD string, or return None on error."""
    if isinstance(date, str):
        try:
            datetime.strptime(date, "%Y-%m-%d")
            return date
        except ValueError as e:
            logger.error(
                "invalid_date_format",
                date_str=date,
                expected="YYYY-MM-DD",
                error=str(e),
            )
            return None
    return date.strftime("%Y-%m-%d")


def _get_repo_root() -> Path | None:
    """Return the git repository root, or None if not in a repo."""
    result = _run_git(["rev-parse", "--show-toplevel"], timeout=5)
    if result is not None and result.returncode == 0:
        return Path(result.stdout.strip())
    return None


def _execute_git_workflow(
    repo_root: Path,
    workflow_type: str,
    date_str: str,
    result_summary: str,
    snapshot_data: dict[str, Any],
) -> bool:
    """Create snapshot file, commit, pull, and push."""
    reports_dir = repo_root / "reports" / "autonomous"
    reports_dir.mkdir(parents=True, exist_ok=True)

    snapshot_filename = f"{date_str}-{workflow_type}.json"
    snapshot_path = reports_dir / snapshot_filename
    with snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2, default=str)
        f.write("\n")
    logger.debug("snapshot_file_created", path=str(snapshot_path))

    if not _git_add(repo_root, str(snapshot_path)):
        logger.warning("git_add_stage_failed")
        return False

    commit_message = f"[AUTONOMOUS] {date_str} - {workflow_type} - {result_summary}"
    if not _git_commit(repo_root, commit_message):
        logger.warning("git_commit_failed")
        return False
    logger.info("git_commit_created", message=commit_message)

    if not _git_pull(repo_root):
        logger.warning("git_pull_failed")
        return False

    if not _git_push(repo_root):
        logger.warning("git_push_failed")
        return False

    logger.info("git_push_completed", filename=snapshot_filename)
    return True


def _run_git(
    args: list[str],
    repo_root: Path | None = None,
    timeout: int = 5,
) -> CompletedProcess[Any] | None:
    """Run a git command, returning CompletedProcess or None on timeout/error."""
    cmd = ["git"]
    if repo_root is not None:
        cmd += ["-C", str(repo_root)]
    cmd += args
    try:
        return safe_subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except TimeoutExpired:
        logger.error("git_timeout", args=args, timeout_seconds=timeout)
        return None
    except Exception as e:
        logger.error("git_error", args=args, error=str(e), exc_info=True)
        return None


def _no_remote(result: CompletedProcess[Any]) -> bool:
    """Return True if the git output indicates no remote is configured."""
    output = (result.stdout + result.stderr).lower()
    return "no remote" in output or "does not appear to be a" in output


def _git_add(repo_root: Path, file_path: str) -> bool:
    """Stage a file with git add."""
    result = _run_git(["add", file_path], repo_root=repo_root)
    if result is None:
        return False
    if result.returncode != 0:
        logger.warning("git_add_failed", stderr=result.stderr, returncode=result.returncode)
        return False
    return True


def _git_commit(repo_root: Path, message: str) -> bool:
    """Create a git commit with the given message."""
    result = _run_git(["commit", "-m", message], repo_root=repo_root)
    if result is None:
        return False
    if result.returncode != 0:
        if "nothing to commit" in result.stdout:
            logger.debug("git_nothing_to_commit")
            return True
        logger.warning("git_commit_failed", stderr=result.stderr, returncode=result.returncode)
        return False
    return True


def _git_pull(repo_root: Path) -> bool:
    """Pull from remote (fast-forward only) before push."""
    result = _run_git(["pull", "--ff-only", "origin", "main"], repo_root=repo_root, timeout=10)
    if result is None:
        return False
    if result.returncode == 0:
        return True
    if _no_remote(result):
        logger.info("git_no_remote_configured")
        return True
    if "fatal: Not possible to fast-forward" in result.stderr:
        logger.warning("git_merge_conflict_detected")
        return False
    logger.warning("git_pull_failed", stderr=result.stderr, returncode=result.returncode)
    return False


def _git_push(repo_root: Path) -> bool:
    """Push commits to remote (origin/main)."""
    result = _run_git(["push", "origin", "main"], repo_root=repo_root, timeout=10)
    if result is None:
        return False
    if result.returncode == 0:
        return True
    if _no_remote(result):
        logger.info("git_no_remote_configured")
        return True
    logger.warning("git_push_failed", stderr=result.stderr, returncode=result.returncode)
    return False
