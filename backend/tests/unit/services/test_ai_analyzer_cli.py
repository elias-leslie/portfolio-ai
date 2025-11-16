"""Unit tests for AI analyzer CLI integration.

Tests CLI detection and initialization without making actual API calls.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_analyzer import CapabilityAnalyzer


class TestCLIDetection:
    """Test Claude CLI detection logic."""

    def test_find_cli_from_env_variable(self, mock_conn_mgr: MagicMock) -> None:
        """Test that CLAUDE_CLI_PATH environment variable is respected."""
        test_path = "/custom/path/to/claude"

        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": test_path}),
            patch("os.path.isfile", return_value=True),
            patch("os.access", return_value=True),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            assert analyzer.cli_path == test_path

    def test_find_cli_from_standard_location(self, mock_conn_mgr: MagicMock) -> None:
        """Test that CLI is found in standard locations."""

        def mock_isfile(path: str) -> bool:
            return path == "/home/kasadis/.local/bin/claude"

        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": ""}, clear=True),
            patch("os.path.isfile", side_effect=mock_isfile),
            patch("os.access", return_value=True),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            assert analyzer.cli_path == "/home/kasadis/.local/bin/claude"

    def test_find_cli_from_path(self, mock_conn_mgr: MagicMock) -> None:
        """Test that CLI is found via PATH search."""
        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": ""}, clear=True),
            patch("os.path.isfile", return_value=False),
            patch("shutil.which", return_value="/usr/local/bin/claude"),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            assert analyzer.cli_path == "/usr/local/bin/claude"

    def test_cli_not_found(self, mock_conn_mgr: MagicMock) -> None:
        """Test that FileNotFoundError is caught and cli_path set to None."""
        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": ""}, clear=True),
            patch("os.path.isfile", return_value=False),
            patch("shutil.which", return_value=None),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            assert analyzer.cli_path is None

    def test_find_cli_method_raises_when_not_found(self, mock_conn_mgr: MagicMock) -> None:
        """Test that _find_claude_cli raises FileNotFoundError when CLI not found."""
        analyzer = CapabilityAnalyzer(mock_conn_mgr)

        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": ""}, clear=True),
            patch("os.path.isfile", return_value=False),
            patch("shutil.which", return_value=None),
            pytest.raises(FileNotFoundError),
        ):
            analyzer._find_claude_cli()


class TestAnalyzerInitialization:
    """Test analyzer initialization with CLI."""

    def test_analyzer_initializes_with_cli(self, mock_conn_mgr: MagicMock) -> None:
        """Test that analyzer initializes correctly with CLI available."""

        def mock_isfile(path: str) -> bool:
            # Return True for the standard location to test that code path
            return path == "/home/kasadis/.local/bin/claude"

        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": ""}, clear=True),
            patch("os.path.isfile", side_effect=mock_isfile),
            patch("os.access", return_value=True),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            assert analyzer.cli_path == "/home/kasadis/.local/bin/claude"
            assert analyzer.enabled is True
            assert analyzer.model == "claude-sonnet-4.5"
            assert analyzer.confidence_threshold == 0.70

    def test_analyzer_initializes_without_cli(self, mock_conn_mgr: MagicMock) -> None:
        """Test that analyzer initializes gracefully without CLI."""
        with (
            patch.dict(os.environ, {"CLAUDE_CLI_PATH": ""}, clear=True),
            patch("os.path.isfile", return_value=False),
            patch("shutil.which", return_value=None),
        ):
            analyzer = CapabilityAnalyzer(mock_conn_mgr)
            assert analyzer.cli_path is None
            assert analyzer.enabled is True  # Still enabled, just can't execute


@pytest.fixture
def mock_conn_mgr() -> MagicMock:
    """Create mock connection manager."""
    mock = MagicMock()
    mock.connection.return_value.__enter__ = MagicMock()
    mock.connection.return_value.__exit__ = MagicMock()
    return mock
