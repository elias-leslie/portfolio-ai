"""Manage Gemini CLI for interactive chat with streaming."""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import AsyncIterator

from .constants import DEFAULT_GEMINI_MODEL
from .stream_parser import StreamMessage, ContentBlock, MessageType, ContentType

logger = logging.getLogger(__name__)


class GeminiProcessError(Exception):
    """Error from Gemini process."""

    pass


class GeminiSession:
    """Manages a Gemini conversation session using the Gemini CLI.

    Uses the Gemini CLI with stream-json output format for proper streaming.
    Supports conversation resumption via session IDs.
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str | Path = ".",
        model: str = DEFAULT_GEMINI_MODEL,
    ):
        """Initialize session.

        Args:
            session_id: Unique session identifier (our internal ID)
            working_dir: Working directory for this session
            model: Gemini model to use (gemini-3-flash-preview, gemini-3-pro-preview)
        """
        self.session_id = session_id
        self.working_dir = Path(working_dir).resolve()
        self.model = model
        self._cli_path = shutil.which("gemini")
        self._connected = False
        self._gemini_session_id: str | None = None  # Gemini's internal session ID
        self._active_process: asyncio.subprocess.Process | None = None
        self._conversation_history: list[dict[str, str]] = []

        if not self._cli_path:
            raise GeminiProcessError("Gemini CLI not found in PATH")

    async def start(self) -> None:
        """Start the session."""
        self._connected = True
        logger.info(f"Gemini session {self.session_id} started in {self.working_dir}")

    async def send(self, message: str) -> AsyncIterator[StreamMessage]:
        """Send a message and stream the response.

        Args:
            message: User message to send

        Yields:
            StreamMessage objects from Gemini's response
        """
        if not self._connected:
            raise GeminiProcessError("Session not started")

        logger.info(f"Sending message to Gemini: {message[:100]}...")

        try:
            # Build command with stream-json output
            cmd = [
                self._cli_path,
                "-o",
                "stream-json",
                "-m",
                self.model,
            ]

            # Resume previous conversation if we have a session ID
            # NOTE: When resuming, Gemini CLI requires -p flag, stdin doesn't work
            if self._gemini_session_id:
                cmd.extend(["--resume", self._gemini_session_id])
                cmd.extend(["-p", message])  # Must use -p when resuming

            # Auto-approve ALL tools (user consented by sending message)
            # Note: auto_edit only approves file edits, not save_memory etc.
            cmd.extend(["--approval-mode", "yolo"])

            logger.info(f"Gemini command: {' '.join(cmd)}")
            logger.info(f"Session ID for resume: {self._gemini_session_id}")

            # Start process - use stdin only for first message (no resume)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if not self._gemini_session_id else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
            )
            self._active_process = process

            # Send message via stdin only for first message (no session ID yet)
            if not self._gemini_session_id and process.stdin:
                process.stdin.write(f"{message}\n".encode())
                await process.stdin.drain()
                process.stdin.close()

            # Track accumulated text for this response
            accumulated_text = ""

            # Read and parse stream-json output
            logger.info("Starting to read Gemini stdout...")
            if process.stdout:
                async for line in process.stdout:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue

                    try:
                        data = json.loads(line_str)
                        msg_type = data.get("type", "")

                        # Handle init message - capture session ID
                        if msg_type == "init":
                            self._gemini_session_id = data.get("session_id")
                            logger.info(f"Gemini session ID: {self._gemini_session_id}")
                            continue

                        # Handle streaming message chunks
                        if msg_type == "message" and data.get("role") == "assistant":
                            content = data.get("content", "")
                            is_delta = data.get("delta", False)

                            if content:
                                if is_delta:
                                    accumulated_text += content
                                else:
                                    accumulated_text = content

                                yield StreamMessage(
                                    type=MessageType.ASSISTANT,
                                    content=[
                                        ContentBlock(type=ContentType.TEXT, text=content)
                                    ],
                                    model=self.model,
                                )

                        # Handle result message - capture stats
                        elif msg_type == "result":
                            stats = data.get("stats", {})
                            logger.info(
                                f"Gemini stats: {stats.get('total_tokens', 0)} tokens, "
                                f"{stats.get('duration_ms', 0)}ms"
                            )
                            # Store in conversation history
                            if accumulated_text:
                                self._conversation_history.append(
                                    {"role": "user", "content": message}
                                )
                                self._conversation_history.append(
                                    {"role": "assistant", "content": accumulated_text}
                                )

                        # Handle tool use - Gemini CLI uses tool_name/parameters fields
                        elif msg_type == "tool_use":
                            tool_name = data.get("tool_name", "unknown")
                            tool_input = data.get("parameters", {})
                            tool_id = data.get("tool_id")
                            logger.info(f"Gemini tool_use: {tool_name}")
                            yield StreamMessage(
                                type=MessageType.ASSISTANT,
                                content=[
                                    ContentBlock(
                                        type=ContentType.TOOL_USE,
                                        tool_name=tool_name,
                                        tool_input=tool_input,
                                        tool_use_id=tool_id,
                                    )
                                ],
                            )

                        # Handle tool result
                        elif msg_type == "tool_result":
                            tool_id = data.get("tool_id")
                            status = data.get("status", "unknown")
                            output = data.get("output", "")
                            logger.info(f"Gemini tool_result: {status}")
                            yield StreamMessage(
                                type=MessageType.ASSISTANT,
                                content=[
                                    ContentBlock(
                                        type=ContentType.TOOL_RESULT,
                                        text=f"[{status}] {output}",
                                        tool_use_id=tool_id,
                                    )
                                ],
                            )

                        # Log any unhandled message types for debugging
                        elif msg_type and msg_type not in ("init", "message", "result"):
                            logger.info(f"Gemini unhandled msg_type: {msg_type}, data: {data}")

                    except json.JSONDecodeError:
                        # Non-JSON output - treat as system message
                        logger.debug(f"Non-JSON line: {line_str[:100]}")
                        continue
            logger.info("Finished reading Gemini stdout")

            # Wait for process to complete
            await process.wait()
            self._active_process = None
            logger.info(f"Gemini process exited with code: {process.returncode}")

            # Always read stderr for debugging
            stderr = ""
            if process.stderr:
                stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
                if stderr:
                    logger.info(f"Gemini stderr: {stderr[:500]}")

            # Check for errors
            if process.returncode not in (0, 1):
                logger.error(f"Gemini process failed: {stderr[:500]}")
                yield StreamMessage(
                    type=MessageType.SYSTEM,
                    content=[
                        ContentBlock(
                            type=ContentType.TEXT,
                            text=f"Error: Gemini process failed: {stderr[:200]}",
                        )
                    ],
                )

        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Gemini query cancelled")
            if self._active_process:
                self._active_process.terminate()
                self._active_process = None
            return

        except Exception as e:
            logger.error(f"Error in Gemini session: {e}")
            yield StreamMessage(
                type=MessageType.SYSTEM,
                content=[ContentBlock(type=ContentType.TEXT, text=f"Error: {e}")],
            )
        finally:
            self._active_process = None

    async def interrupt(self) -> bool:
        """Send interrupt signal to stop current query.

        Returns:
            True if interrupt was sent, False if no active query
        """
        if not self._active_process:
            logger.warning(f"[{self.session_id}] No active query to interrupt")
            return False

        try:
            self._active_process.terminate()
            logger.info(f"[{self.session_id}] Interrupt signal sent")
            return True
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to interrupt: {e}")
            return False

    async def stop(self) -> None:
        """Stop the session."""
        self._connected = False
        if self._active_process:
            self._active_process.terminate()
            self._active_process = None
        logger.info(f"Gemini session {self.session_id} stopped")

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._connected

    @property
    def sdk_session_id(self) -> str | None:
        """Get Gemini's internal session ID (for DB storage)."""
        return self._gemini_session_id

    @sdk_session_id.setter
    def sdk_session_id(self, value: str | None) -> None:
        """Set Gemini's internal session ID (for resumption)."""
        self._gemini_session_id = value


# Alias for consistency with ClaudeProcess
GeminiProcess = GeminiSession
