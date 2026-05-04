"""Unit tests for git_automation module.

Tests the git automation functionality including:
- Snapshot file creation
- Git commit handling
- Error resilience (graceful failure)
- Merge conflict handling
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from app.utils.git_automation import (
    _get_repo_root,
    _git_add,
    _git_commit,
    _git_pull,
    _git_push,
    commit_workflow_results,
)


class TestGetRepoRoot:
    """Tests for _get_repo_root function."""

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_returns_valid_repo_root(self, mock_run: Mock) -> None:
        """Test successful retrieval of repo root."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="/home/testuser/portfolio-ai\n",
        )
        result = _get_repo_root()
        assert result == Path("/home/testuser/portfolio-ai")

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_returns_none_on_git_failure(self, mock_run: Mock) -> None:
        """Test returns None when git command fails."""
        mock_run.return_value = MagicMock(returncode=128)
        result = _get_repo_root()
        assert result is None

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_handles_exception(self, mock_run: Mock) -> None:
        """Test handles subprocess exceptions gracefully."""
        mock_run.side_effect = Exception("Git not installed")
        result = _get_repo_root()
        assert result is None


class TestGitAdd:
    """Tests for _git_add function."""

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_successful_git_add(self, mock_run: Mock) -> None:
        """Test successful git add operation."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _git_add(Path("/repo"), "/repo/file.txt")
        assert result is True
        mock_run.assert_called_once()

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_add_failure(self, mock_run: Mock) -> None:
        """Test git add failure handling."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: not a git repository",
            stdout="",
        )
        result = _git_add(Path("/repo"), "/repo/file.txt")
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_add_timeout(self, mock_run: Mock) -> None:
        """Test timeout handling in git add."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
        result = _git_add(Path("/repo"), "/repo/file.txt")
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_add_exception(self, mock_run: Mock) -> None:
        """Test exception handling in git add."""
        mock_run.side_effect = OSError("Pipe error")
        result = _git_add(Path("/repo"), "/repo/file.txt")
        assert result is False


class TestGitCommit:
    """Tests for _git_commit function."""

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_successful_git_commit(self, mock_run: Mock) -> None:
        """Test successful git commit."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _git_commit(Path("/repo"), "Test commit message")
        assert result is True

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_nothing_to_commit_is_success(self, mock_run: Mock) -> None:
        """Test that 'nothing to commit' is treated as success."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="On branch main\nnothing to commit, working tree clean",
            stderr="",
        )
        result = _git_commit(Path("/repo"), "Test message")
        assert result is True

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_commit_failure(self, mock_run: Mock) -> None:
        """Test git commit failure handling."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: not a git repository",
            stdout="",
        )
        result = _git_commit(Path("/repo"), "Test message")
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_commit_timeout(self, mock_run: Mock) -> None:
        """Test timeout handling in git commit."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
        result = _git_commit(Path("/repo"), "Test message")
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_commit_exception(self, mock_run: Mock) -> None:
        """Test exception handling in git commit."""
        mock_run.side_effect = RuntimeError("Unknown error")
        result = _git_commit(Path("/repo"), "Test message")
        assert result is False


class TestGitPull:
    """Tests for _git_pull function."""

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_successful_git_pull(self, mock_run: Mock) -> None:
        """Test successful git pull."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _git_pull(Path("/repo"))
        assert result is True

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_no_remote_configured(self, mock_run: Mock) -> None:
        """Test handling of 'no remote' scenario."""
        mock_run.return_value = MagicMock(
            returncode=128,
            stderr="fatal: 'origin' does not appear to be a 'git' repository",
            stdout="",
        )
        result = _git_pull(Path("/repo"))
        assert result is True  # Treated as success for local dev

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_merge_conflict_detected(self, mock_run: Mock) -> None:
        """Test merge conflict detection."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: Not possible to fast-forward, aborting",
            stdout="",
        )
        result = _git_pull(Path("/repo"))
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_pull_timeout(self, mock_run: Mock) -> None:
        """Test timeout handling in git pull."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        result = _git_pull(Path("/repo"))
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_pull_exception(self, mock_run: Mock) -> None:
        """Test exception handling in git pull."""
        mock_run.side_effect = OSError("Network error")
        result = _git_pull(Path("/repo"))
        assert result is False


class TestGitPush:
    """Tests for _git_push function."""

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_successful_git_push(self, mock_run: Mock) -> None:
        """Test successful git push."""
        mock_run.return_value = MagicMock(returncode=0)
        result = _git_push(Path("/repo"))
        assert result is True

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_no_remote_configured(self, mock_run: Mock) -> None:
        """Test handling of 'no remote' scenario."""
        mock_run.return_value = MagicMock(
            returncode=128,
            stderr="fatal: 'origin' does not appear to be a 'git' repository",
            stdout="",
        )
        result = _git_push(Path("/repo"))
        assert result is True  # Treated as success for local dev

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_push_failure(self, mock_run: Mock) -> None:
        """Test git push failure."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="fatal: unable to access 'https://...': Permission denied",
            stdout="",
        )
        result = _git_push(Path("/repo"))
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_push_timeout(self, mock_run: Mock) -> None:
        """Test timeout handling in git push."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)
        result = _git_push(Path("/repo"))
        assert result is False

    @patch("app.utils.git_automation.safe_subprocess.run")
    def test_git_push_exception(self, mock_run: Mock) -> None:
        """Test exception handling in git push."""
        mock_run.side_effect = RuntimeError("SSH key error")
        result = _git_push(Path("/repo"))
        assert result is False


class TestCommitWorkflowResults:
    """Integration tests for commit_workflow_results function."""

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_successful_commit_with_string_date(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test successful workflow result commit with string date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            reports_dir = repo_path / "reports" / "autonomous"

            mock_repo_root.return_value = repo_path
            mock_add.return_value = True
            mock_commit.return_value = True
            mock_pull.return_value = True
            mock_push.return_value = True

            snapshot_data = {
                "gaps_analyzed": 3,
                "coverage_pct": 0.65,
                "trends": ["sector rotation"],
            }

            result = commit_workflow_results(
                "daily_gap_analysis",
                "2025-11-18",
                "3 gaps identified, 65% coverage",
                snapshot_data,
            )

            assert result is True
            assert (reports_dir / "2025-11-18-daily_gap_analysis.json").exists()

            # Verify file contents
            snapshot_file = reports_dir / "2025-11-18-daily_gap_analysis.json"
            with snapshot_file.open(encoding="utf-8") as f:
                saved_data = json.load(f)
            assert saved_data == snapshot_data

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_successful_commit_with_datetime(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test successful workflow result commit with datetime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            mock_repo_root.return_value = repo_path
            mock_add.return_value = True
            mock_commit.return_value = True
            mock_pull.return_value = True
            mock_push.return_value = True

            snapshot_data = {"symbol": "NVDA", "action": "BUY"}

            result = commit_workflow_results(
                "paper_trade_validation",
                datetime(2025, 11, 18, 10, 30, 0),
                "NVDA BUY approved",
                snapshot_data,
            )

            assert result is True
            assert (
                repo_path / "reports" / "autonomous" / "2025-11-18-paper_trade_validation.json"
            ).exists()

    @patch("app.utils.git_automation._get_repo_root")
    def test_invalid_date_format(self, mock_repo_root: Mock) -> None:
        """Test error handling for invalid date format."""
        mock_repo_root.return_value = Path("/repo")

        result = commit_workflow_results(
            "daily_gap_analysis",
            "18-11-2025",  # Wrong format
            "Test",
            {},
        )

        assert result is False

    @patch("app.utils.git_automation._get_repo_root")
    def test_not_in_git_repo(self, mock_repo_root: Mock) -> None:
        """Test graceful handling when not in a git repository."""
        mock_repo_root.return_value = None

        result = commit_workflow_results(
            "daily_gap_analysis",
            "2025-11-18",
            "Test",
            {},
        )

        assert result is False

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_handles_git_add_failure(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test error handling when git add fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "reports" / "autonomous").mkdir(parents=True, exist_ok=True)

            mock_repo_root.return_value = repo_path
            mock_add.return_value = False  # git add fails

            result = commit_workflow_results(
                "daily_gap_analysis",
                "2025-11-18",
                "Test",
                {"test": "data"},
            )

            assert result is False
            # File should still be created
            assert (
                repo_path / "reports" / "autonomous" / "2025-11-18-daily_gap_analysis.json"
            ).exists()

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_handles_git_commit_failure(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test error handling when git commit fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "reports" / "autonomous").mkdir(parents=True, exist_ok=True)

            mock_repo_root.return_value = repo_path
            mock_add.return_value = True
            mock_commit.return_value = False  # git commit fails

            result = commit_workflow_results(
                "daily_gap_analysis",
                "2025-11-18",
                "Test",
                {"test": "data"},
            )

            assert result is False

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_handles_git_pull_failure(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test error handling when git pull fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "reports" / "autonomous").mkdir(parents=True, exist_ok=True)

            mock_repo_root.return_value = repo_path
            mock_add.return_value = True
            mock_commit.return_value = True
            mock_pull.return_value = False  # git pull fails

            result = commit_workflow_results(
                "daily_gap_analysis",
                "2025-11-18",
                "Test",
                {"test": "data"},
            )

            assert result is False

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_handles_git_push_failure(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test error handling when git push fails (continues gracefully)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "reports" / "autonomous").mkdir(parents=True, exist_ok=True)

            mock_repo_root.return_value = repo_path
            mock_add.return_value = True
            mock_commit.return_value = True
            mock_pull.return_value = True
            mock_push.return_value = False  # git push fails

            result = commit_workflow_results(
                "daily_gap_analysis",
                "2025-11-18",
                "Test",
                {"test": "data"},
            )

            assert result is False

    @patch("app.utils.git_automation._get_repo_root")
    def test_handles_general_exception(self, mock_repo_root: Mock) -> None:
        """Test handling of unexpected exceptions."""
        mock_repo_root.side_effect = Exception("Unexpected error")

        result = commit_workflow_results(
            "daily_gap_analysis",
            "2025-11-18",
            "Test",
            {"test": "data"},
        )

        assert result is False

    @patch("app.utils.git_automation._git_push")
    @patch("app.utils.git_automation._git_pull")
    @patch("app.utils.git_automation._git_commit")
    @patch("app.utils.git_automation._git_add")
    @patch("app.utils.git_automation._get_repo_root")
    def test_snapshot_data_serialization(
        self,
        mock_repo_root: Mock,
        mock_add: Mock,
        mock_commit: Mock,
        mock_pull: Mock,
        mock_push: Mock,
    ) -> None:
        """Test that complex data types are serialized correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            (repo_path / "reports" / "autonomous").mkdir(parents=True, exist_ok=True)

            mock_repo_root.return_value = repo_path
            mock_add.return_value = True
            mock_commit.return_value = True
            mock_pull.return_value = True
            mock_push.return_value = True

            # Include datetime in snapshot (requires 'default=str')
            snapshot_data = {
                "timestamp": datetime(2025, 11, 18, 10, 30),
                "metrics": {"sharpe": 1.2, "win_rate": 0.58},
                "list": [1, 2, 3],
            }

            result = commit_workflow_results(
                "test_workflow",
                "2025-11-18",
                "Test serialization",
                snapshot_data,
            )

            assert result is True
            # Verify file can be read and deserialized
            snapshot_file = repo_path / "reports" / "autonomous" / "2025-11-18-test_workflow.json"
            with snapshot_file.open(encoding="utf-8") as f:
                saved_data = json.load(f)
            assert saved_data["timestamp"] == str(datetime(2025, 11, 18, 10, 30))
            assert saved_data["metrics"]["sharpe"] == 1.2
