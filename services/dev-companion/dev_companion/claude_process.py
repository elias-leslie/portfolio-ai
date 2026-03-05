"""Manage Claude Code via the official Claude Agent SDK."""

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import SystemMessage

from .claude_message_converter import convert_sdk_message
from .claude_permissions import PermissionCallback, PermissionMixin
from .stream_parser import StreamMessage, ContentBlock, MessageType, ContentType

logger = logging.getLogger(__name__)

# Path to the Claude CLI binary. Resolved from:
# 1. CLAUDE_CLI_PATH env var (explicit override)
# 2. shutil.which('claude') (system PATH lookup)
# 3. '/usr/local/bin/claude' (fallback default)
_CLAUDE_CLI_PATH = os.environ.get("CLAUDE_CLI_PATH") or shutil.which("claude") or "/usr/local/bin/claude"


class ClaudeProcessError(Exception):
    """Error from Claude process."""


class ClaudeSession(PermissionMixin):
    """Manages a Claude conversation session using the official SDK.

    Uses ClaudeSDKClient for proper streaming, session management,
    and all Claude Code features (slash commands, skills, etc.).
    """

    def __init__(
        self,
        session_id: str,
        working_dir: str | Path = ".",
        permission_callback: PermissionCallback | None = None,
    ):
        """Initialise session.

        Args:
            session_id: Unique session identifier.
            working_dir: Working directory for this session.
            permission_callback: Callback for handling permission requests.
                                 Called with (tool_name, input, context).
                                 Should return a Future[bool] for allow/deny.
        """
        self.session_id = session_id
        self.working_dir = Path(working_dir).resolve()
        self._client: ClaudeSDKClient | None = None
        self._options: ClaudeAgentOptions | None = None
        self._connected = False
        self._sdk_session_id: str | None = None
        self._active_client: ClaudeSDKClient | None = None
        self._permission_callback = permission_callback
        self._pending_permission: asyncio.Future[bool] | None = None

    async def start(self) -> None:
        """Start the session by initialising the SDK client."""
        self._options = ClaudeAgentOptions(
            cwd=str(self.working_dir),
            permission_mode="default",
            setting_sources=["user", "project"],
            cli_path=_CLAUDE_CLI_PATH,
        )
        self._client = ClaudeSDKClient(options=self._options)
        self._connected = True
        logger.info(f"Session {self.session_id} started in {self.working_dir}")

    async def send(self, message: str) -> AsyncIterator[StreamMessage]:
        """Send a message and stream the response.

        Args:
            message: User message to send.

        Yields:
            StreamMessage objects from Claude's response.
        """
        if not self._options:
            raise ClaudeProcessError("Session not started")

        logger.info(f"Sending message to Claude: {message[:100]}...")

        try:
            async for stream_msg in self._run_query(message):
                yield stream_msg
        except GeneratorExit:
            logger.info(f"[{self.session_id}] Generator closed by consumer")
            return
        except Exception as e:
            yield self._error_message_for(e)

    async def _iter_sdk_messages(
        self, client: ClaudeSDKClient, message: str
    ) -> AsyncIterator[StreamMessage]:
        """Convert and filter SDK messages for a query."""
        await client.query(message)
        async for msg in client.receive_response():
            logger.info(f"[{self.session_id}] Received: {type(msg).__name__}")
            self._capture_sdk_session_id(msg)
            stream_msg = convert_sdk_message(msg)
            if stream_msg:
                yield stream_msg
            else:
                logger.debug(
                    f"[{self.session_id}] Skipped"
                    f" {type(msg).__name__}: {str(msg)[:200]}"
                )

    async def _run_query(self, message: str) -> AsyncIterator[StreamMessage]:
        """Execute the SDK query and yield converted messages."""
        options = ClaudeAgentOptions(
            cwd=str(self.working_dir),
            permission_mode="default",
            setting_sources=["user", "project"],
            cli_path=_CLAUDE_CLI_PATH,
            resume=self._sdk_session_id,
            can_use_tool=self._handle_permission_request
            if self._permission_callback
            else None,
        )
        client = ClaudeSDKClient(options=options)
        self._active_client = client
        try:
            async with client:
                async for stream_msg in self._iter_sdk_messages(client, message):
                    yield stream_msg
        finally:
            self._active_client = None

    def _capture_sdk_session_id(self, msg: object) -> None:
        """Persist the SDK session ID from an init SystemMessage."""
        if (
            isinstance(msg, SystemMessage)
            and msg.subtype == "init"
            and isinstance(msg.data, dict)
        ):
            self._sdk_session_id = msg.data.get("session_id")
            logger.info(f"SDK session ID: {self._sdk_session_id}")

    def _error_message_for(self, exc: Exception) -> StreamMessage:
        """Build an error StreamMessage, or re-raise if it's a cancellation."""
        error_str = str(exc)
        if "GeneratorExit" in error_str or "cancel" in error_str.lower():
            logger.info(f"[{self.session_id}] Session cancelled: {exc}")
            raise exc
        logger.error(f"Error in Claude session: {exc}")
        return StreamMessage(
            type=MessageType.SYSTEM,
            content=[ContentBlock(type=ContentType.TEXT, text=f"Error: {exc}")],
        )

    async def interrupt(self) -> bool:
        """Send interrupt signal to stop the current query.

        Returns:
            True if interrupt was sent, False if no active query.
        """
        if not self._active_client:
            logger.warning(f"[{self.session_id}] No active query to interrupt")
            return False
        try:
            await self._active_client.interrupt()
            logger.info(f"[{self.session_id}] Interrupt signal sent")
            return True
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to interrupt: {e}")
            return False

    async def stop(self) -> None:
        """Stop the session."""
        self._connected = False
        self._client = None
        self._active_client = None
        logger.info(f"Session {self.session_id} stopped")

    @property
    def is_active(self) -> bool:
        """True if the session is connected and the client is ready."""
        return self._connected and self._client is not None


# Keep old class name for backwards compatibility
ClaudeProcess = ClaudeSession
