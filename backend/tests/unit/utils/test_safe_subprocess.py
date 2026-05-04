from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.utils import safe_subprocess


@patch("app.utils.safe_subprocess.subprocess.run")
@patch("app.utils.safe_subprocess.shutil.which")
def test_run_resolves_executable_and_forces_close_fds_false(
    mock_which: Mock,
    mock_run: Mock,
) -> None:
    mock_which.return_value = "/usr/bin/git"

    safe_subprocess.run(["git", "status"], capture_output=True, text=True)

    mock_run.assert_called_once_with(
        ["/usr/bin/git", "status"],
        capture_output=True,
        text=True,
        check=False,
        close_fds=False,
    )


def test_run_rejects_shell() -> None:
    with pytest.raises(ValueError, match="shell=True"):
        safe_subprocess.run(["git"], shell=True)


@patch("app.utils.safe_subprocess.shutil.which")
def test_run_raises_when_executable_missing(mock_which: Mock) -> None:
    mock_which.return_value = None

    with pytest.raises(FileNotFoundError):
        safe_subprocess.run(["missing-tool"])
