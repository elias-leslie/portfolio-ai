"""Manage Claude Code CLI process."""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import AsyncIterator

from .stream_parser import StreamMessage, parse_stream_line

logger = logging.getLogger(__name__)


class ClaudeProcessError(Exception):
    """Error from Claude process."""

    pass


class ClaudeProcess:
    """Manages a Claude Code CLI process.

    This class spawns and manages the real `claude` CLI binary,
    streaming its output back to callers.
    """

    def __init__(
        self,
        working_dir: str | Path = ".",
        session_id: str | None = None,
        claude_path: str | None = None,
    ):
        """Initialize Claude process manager.

        Args:
            working_dir: Working directory for Claude operations
            session_id: Optional session ID to resume
            claude_path: Path to claude binary (auto-detected if None)
        """
        self.working_dir = Path(working_dir).resolve()
        self.session_id = session_id
        self.claude_path = claude_path or self._find_claude()
        self.process: asyncio.subprocess.Process | None = None
        self._running = False

    def _find_claude(self) -> str:
        """Find the claude binary."""
        # Check common locations
        paths_to_check = [
            "claude",  # In PATH
            "/usr/local/bin/claude",
            "/usr/bin/claude",
            os.path.expanduser("~/.local/bin/claude"),
            os.path.expanduser("~/.npm-global/bin/claude"),
        ]

        for path in paths_to_check:
            if path == "claude":
                found = shutil.which("claude")
                if found:
                    return found
            elif os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        raise ClaudeProcessError(
            "Claude CLI not found. Please install it: npm install -g @anthropic-ai/claude-code"
        )

    async def start(self) -> None:
        """Start the Claude process."""
        if self._running:
            raise ClaudeProcessError("Process already running")

        # Build command
        cmd = [
            self.claude_path,
            "--output-format",
            "stream-json",
        ]

        # Add session resume if specified
        if self.session_id:
            cmd.extend(["--resume", self.session_id])

        # Environment - ensure we use OAuth, not API key
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)  # Force OAuth auth

        logger.info(f"Starting Claude process: {' '.join(cmd)}")
        logger.info(f"Working directory: {self.working_dir}")

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.working_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._running = True

    async def send_message(self, message: str) -> None:
        """Send a message to Claude.

        Args:
            message: The message to send
        """
        if not self.process or not self.process.stdin:
            raise ClaudeProcessError("Process not started")

        # Send the message followed by newline
        self.process.stdin.write(f"{message}\n".encode())
        await self.process.stdin.drain()

    async def stream_output(self) -> AsyncIterator[StreamMessage]:
        """Stream parsed output from Claude.

        Yields:
            StreamMessage objects parsed from Claude's output
        """
        if not self.process or not self.process.stdout:
            raise ClaudeProcessError("Process not started")

        async for line in self.process.stdout:
            msg = parse_stream_line(line)
            if msg:
                yield msg

    async def stream_stderr(self) -> AsyncIterator[str]:
        """Stream stderr output (errors, warnings).

        Yields:
            Lines from stderr
        """
        if not self.process or not self.process.stderr:
            return

        async for line in self.process.stderr:
            yield line.decode("utf-8", errors="replace").strip()

    async def stop(self) -> int:
        """Stop the Claude process.

        Returns:
            Exit code
        """
        if not self.process:
            return 0

        self._running = False

        # Try graceful shutdown first
        if self.process.stdin:
            try:
                self.process.stdin.close()
            except Exception:
                pass

        try:
            # Wait a bit for graceful exit
            return await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # Force kill
            self.process.kill()
            return await self.process.wait()

    @property
    def is_running(self) -> bool:
        """Check if process is running."""
        return self._running and self.process is not None and self.process.returncode is None


class ClaudeSession:
    """Manages a Claude conversation session.

    Handles starting, stopping, and communicating with Claude,
    plus session persistence.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str | Path = ".",
    ):
        """Initialize session.

        Args:
            session_id: Unique session identifier
            working_dir: Working directory for this session
        """
        self.session_id = session_id
        self.working_dir = Path(working_dir).resolve()
        self.process: ClaudeProcess | None = None
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()

    async def start(self) -> None:
        """Start the session."""
        self.process = ClaudeProcess(
            working_dir=self.working_dir,
            session_id=self.session_id,
        )
        await self.process.start()

    async def send(self, message: str) -> AsyncIterator[StreamMessage]:
        """Send a message and stream the response.

        Args:
            message: User message to send

        Yields:
            StreamMessage objects from Claude's response
        """
        if not self.process:
            raise ClaudeProcessError("Session not started")

        await self.process.send_message(message)

        async for msg in self.process.stream_output():
            yield msg

            # Check for end of response
            if msg.stop_reason:
                break

    async def stop(self) -> None:
        """Stop the session."""
        if self.process:
            await self.process.stop()
            self.process = None

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.process is not None and self.process.is_running
