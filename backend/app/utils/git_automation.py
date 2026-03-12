"""Git automation for autonomous workflow results.

This module provides functionality to automatically commit workflow results
to the git repository with snapshot data as JSON files.

Capabilities:
- Creates snapshot files in reports/autonomous/ directory
- Commits workflow results with formatted messages to main branch
- Auto-pushes commits to remote (origin/main)
- Graceful error handling (git failures don't crash workflows)
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

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
        workflow_type: Type of workflow (e.g., "daily_gap_analysis", "paper_trade_validation")
        date: Date of workflow execution (datetime or string YYYY-MM-DD format)
        result_summary: Human-readable summary of results (e.g., "3 gaps identified, 2 resolved")
        snapshot_data: Dictionary containing workflow results to save as JSON

    Returns:
        True if commit and push succeeded, False if any step failed
        (failures are logged but do not raise exceptions)

    Example:
        ```python
        snapshot = {
            "gaps_analyzed": 3,
            "coverage_pct": 0.65,
            "trends": ["sector rotation", "volatility spike"],
            "recommendations": ["increase position", "hedge downside"],
        }
        success = commit_workflow_results(
            "daily_gap_analysis",
            "2025-11-18",
            "3 gaps identified, 65% coverage",
            snapshot,
        )
        if success:
            logger.info("Workflow results committed to git")
        else:
            logger.warning("Failed to commit workflow results (workflow continues)")
        ```
    """
    try:
        # Parse date if string
        if isinstance(date, str):
            date_str = date
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError as e:
                logger.error(
                    "invalid_date_format",
                    date_str=date_str,
                    expected="YYYY-MM-DD",
                    error=str(e),
                )
                return False
        else:
            date_str = date.strftime("%Y-%m-%d")

        # Ensure reports/autonomous directory exists
        repo_root = _get_repo_root()
        if not repo_root:
            logger.warning("git_not_in_repository")
            return False

        # Execute git workflow (file creation, add, commit, pull, push)
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


def _get_repo_root() -> Path | None:
    """Get the root directory of the git repository.

    Returns:
        Path to repository root, or None if not in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None
    except Exception as e:
        logger.error("git_root_failed", error=str(e), exc_info=True)
        return None


def _execute_git_workflow(
    repo_root: Path,
    workflow_type: str,
    date_str: str,
    result_summary: str,
    snapshot_data: dict[str, Any],
) -> bool:
    """Execute the complete git workflow for snapshot creation and commit.

    Internal helper to reduce cyclomatic complexity of main function.

    Args:
        repo_root: Root directory of git repository
        workflow_type: Type of workflow
        date_str: Date string in YYYY-MM-DD format
        result_summary: Human-readable summary
        snapshot_data: Snapshot data to save

    Returns:
        True if all steps succeeded, False otherwise
    """
    # Create reports/autonomous directory
    reports_dir = repo_root / "reports" / "autonomous"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Create snapshot filename and write file
    snapshot_filename = f"{date_str}-{workflow_type}.json"
    snapshot_path = reports_dir / snapshot_filename

    with snapshot_path.open("w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2, default=str)
        f.write("\n")  # Ensure file ends with newline (pre-commit requirement)

    logger.debug("snapshot_file_created", path=str(snapshot_path))

    # Stage file with git add
    if not _git_add(repo_root, str(snapshot_path)):
        logger.warning("git_add_stage_failed")
        return False

    # Create and commit with git commit
    commit_message = f"[AUTONOMOUS] {date_str} - {workflow_type} - {result_summary}"
    if not _git_commit(repo_root, commit_message):
        logger.warning("git_commit_failed")
        return False

    logger.info("git_commit_created", message=commit_message)

    # Pull before push to handle merge conflicts
    if not _git_pull(repo_root):
        logger.warning("git_pull_failed")
        return False

    # Push to remote (origin/main)
    if not _git_push(repo_root):
        logger.warning("git_push_failed")
        return False

    logger.info("git_push_completed", filename=snapshot_filename)
    return True


def _git_add(repo_root: Path, file_path: str) -> bool:
    """Stage a file with git add.

    Args:
        repo_root: Root directory of git repository
        file_path: Absolute path to file to stage

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "add", file_path],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "git_add_failed",
                stderr=result.stderr,
                returncode=result.returncode,
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("git_add_timeout", timeout_seconds=5)
        return False
    except Exception as e:
        logger.error("git_add_error", error=str(e), exc_info=True)
        return False


def _git_commit(repo_root: Path, message: str) -> bool:
    """Create a git commit with the given message.

    Args:
        repo_root: Root directory of git repository
        message: Commit message

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "commit", "-m", message],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            # Check if "nothing to commit" (not an error for our purposes)
            if "nothing to commit" in result.stdout:
                logger.debug("git_nothing_to_commit")
                return True
            logger.warning(
                "git_commit_failed",
                stderr=result.stderr,
                returncode=result.returncode,
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("git_commit_timeout", timeout_seconds=5)
        return False
    except Exception as e:
        logger.error("git_commit_error", error=str(e), exc_info=True)
        return False


def _git_pull(repo_root: Path) -> bool:
    """Pull from remote to handle merge conflicts before push.

    Args:
        repo_root: Root directory of git repository

    Returns:
        True if successful or no remote configured, False on error
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "pull", "--ff-only", "origin", "main"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode == 0:
            return True

        # Combine stdout and stderr for error checking
        output = (result.stdout + result.stderr).lower()

        # If no remote configured, that's okay
        if "no remote" in output or "does not appear to be a" in output:
            logger.info("git_no_remote_configured")
            return True

        # Check for fast-forward merge conflicts
        if "fatal: Not possible to fast-forward" in result.stderr:
            logger.warning("git_merge_conflict_detected")
            return False

        logger.warning(
            "git_pull_failed",
            stderr=result.stderr,
            returncode=result.returncode,
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error("git_pull_timeout", timeout_seconds=10)
        return False
    except Exception as e:
        logger.error("git_pull_error", error=str(e), exc_info=True)
        return False


def _git_push(repo_root: Path) -> bool:
    """Push commits to remote (origin/main).

    Args:
        repo_root: Root directory of git repository

    Returns:
        True if successful or no remote configured, False on error
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "push", "origin", "main"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode == 0:
            return True

        # Combine stdout and stderr for error checking
        output = (result.stdout + result.stderr).lower()

        # If no remote configured, that's okay (local dev)
        if "no remote" in output or "does not appear to be a" in output:
            logger.info("git_no_remote_configured")
            return True

        logger.warning(
            "git_push_failed",
            stderr=result.stderr,
            returncode=result.returncode,
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error("git_push_timeout", timeout_seconds=10)
        return False
    except Exception as e:
        logger.error("git_push_error", error=str(e), exc_info=True)
        return False
