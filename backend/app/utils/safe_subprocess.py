"""Subprocess helpers safe for API-adjacent code paths."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

Command = Sequence[str | os.PathLike[str]]


def _resolve_command(args: Command) -> list[str]:
    """Return command with an absolute executable path."""
    if not args:
        raise ValueError("subprocess command cannot be empty")

    command = [os.fspath(part) for part in args]
    executable = command[0]
    if Path(executable).is_absolute():
        return command

    resolved = shutil.which(executable)
    if resolved is None:
        raise FileNotFoundError(executable)

    command[0] = resolved
    return command


def run(args: Command, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    """Run a command with fork-safe defaults.

    Python can use posix_spawn for subprocesses when close_fds is false and the
    executable path is absolute, avoiding fork hazards in ASGI request paths.
    """
    if kwargs.pop("shell", False):
        raise ValueError("safe_subprocess.run does not support shell=True")

    check = kwargs.pop("check", False)
    kwargs["close_fds"] = False
    return subprocess.run(_resolve_command(args), check=check, **kwargs)
