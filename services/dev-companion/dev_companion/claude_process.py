"""Manage Claude Code via the official Claude Agent SDK."""

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Callable, Any

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import (
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from .stream_parser import StreamMessage, ContentBlock, MessageType, ContentType

logger = logging.getLogger(__name__)


# Type for permission request callback
PermissionCallback = Callable[
    [str, dict[str, Any], ToolPermissionContext], asyncio.Future[bool]
]


class ClaudeProcessError(Exception):
    """Error from Claude process."""

    pass


class ClaudeSession:
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
        """Initialize session.

        Args:
            session_id: Unique session identifier
            working_dir: Working directory for this session
            permission_callback: Callback for handling permission requests.
                                 Called with (tool_name, input, context).
                                 Should return a Future[bool] for allow/deny.
        """
        self.session_id = session_id
        self.working_dir = Path(working_dir).resolve()
        self._client: ClaudeSDKClient | None = None
        self._options: ClaudeAgentOptions | None = None
        self._connected = False
        self._sdk_session_id: str | None = None  # Track SDK's internal session ID
        self._active_client: ClaudeSDKClient | None = None  # Client during active query
        self._permission_callback = permission_callback
        self._pending_permission: asyncio.Future[bool] | None = None

    async def start(self) -> None:
        """Start the session by initializing the SDK client."""
        self._options = ClaudeAgentOptions(
            cwd=str(self.working_dir),
            # Use default permission mode (will prompt for dangerous operations)
            permission_mode="default",
            # Load user AND project settings for OAuth + custom slash commands
            setting_sources=["user", "project"],
            # Use system CLI instead of bundled (bundled 2.0.62 has OAuth issues)
            cli_path="/home/kasadis/.local/bin/claude",
        )
        self._client = ClaudeSDKClient(options=self._options)
        self._connected = True
        logger.info(f"Session {self.session_id} started in {self.working_dir}")

    async def send(self, message: str) -> AsyncIterator[StreamMessage]:
        """Send a message and stream the response.

        Args:
            message: User message to send

        Yields:
            StreamMessage objects from Claude's response
        """
        if not self._options:
            raise ClaudeProcessError("Session not started")

        logger.info(f"Sending message to Claude: {message[:100]}...")

        try:
            # Create options with resume if we have a previous SDK session
            options = ClaudeAgentOptions(
                cwd=str(self.working_dir),
                permission_mode="default",
                # Load user AND project settings for custom slash commands
                setting_sources=["user", "project"],
                cli_path="/home/kasadis/.local/bin/claude",
                # Resume previous conversation if we have a session ID
                resume=self._sdk_session_id,
                # Permission callback for handling dangerous operations
                can_use_tool=self._handle_permission_request
                if self._permission_callback
                else None,
            )

            client = ClaudeSDKClient(options=options)
            self._active_client = client  # Track for interrupt capability
            try:
                async with client:
                    await client.query(message)

                    async for msg in client.receive_response():
                        # Log all message types for debugging
                        msg_type = type(msg).__name__
                        logger.info(f"[{self.session_id}] Received: {msg_type}")

                        # Capture SDK session ID from init message
                        if isinstance(msg, SystemMessage) and msg.subtype == "init":
                            self._sdk_session_id = msg.data.get("session_id")
                            logger.info(f"SDK session ID: {self._sdk_session_id}")

                        stream_msg = self._convert_message(msg)
                        if stream_msg:
                            yield stream_msg
                        else:
                            logger.debug(
                                f"[{self.session_id}] Skipped {msg_type}: {str(msg)[:200]}"
                            )
            finally:
                self._active_client = None

        except GeneratorExit:
            # Consumer closed the generator - clean exit, don't yield anything
            logger.info(f"[{self.session_id}] Generator closed by consumer")
            return
        except Exception as e:
            # Only yield error if it's not a cancellation/cleanup issue
            error_str = str(e)
            if "GeneratorExit" in error_str or "cancel" in error_str.lower():
                logger.info(f"[{self.session_id}] Session cancelled: {e}")
                return
            logger.error(f"Error in Claude session: {e}")
            yield StreamMessage(
                type=MessageType.SYSTEM,
                content=[ContentBlock(type=ContentType.TEXT, text=f"Error: {e}")],
            )

    def _convert_message(self, msg) -> StreamMessage | None:
        """Convert SDK message to our StreamMessage format."""
        content_blocks = []

        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    content_blocks.append(
                        ContentBlock(
                            type=ContentType.TEXT,
                            text=block.text,
                        )
                    )
                elif isinstance(block, ToolUseBlock):
                    content_blocks.append(
                        ContentBlock(
                            type=ContentType.TOOL_USE,
                            tool_name=block.name,
                            tool_input=block.input if hasattr(block, "input") else None,
                            tool_use_id=block.id if hasattr(block, "id") else None,
                        )
                    )
                elif isinstance(block, ToolResultBlock):
                    content_blocks.append(
                        ContentBlock(
                            type=ContentType.TOOL_RESULT,
                            text=str(block.content)
                            if hasattr(block, "content")
                            else None,
                            tool_use_id=block.tool_use_id
                            if hasattr(block, "tool_use_id")
                            else None,
                        )
                    )

            if content_blocks:
                return StreamMessage(
                    type=MessageType.ASSISTANT,
                    content=content_blocks,
                    stop_reason=msg.stop_reason
                    if hasattr(msg, "stop_reason")
                    else None,
                )

        # Handle UserMessage (slash command output, tool results echoed back)
        elif isinstance(msg, UserMessage):
            content = msg.content
            # Content can be a string (e.g., <local-command-stdout>...</local-command-stdout>)
            # or a list of content blocks
            if isinstance(content, str):
                # Extract content from local-command-stdout tags if present
                import re

                stdout_match = re.search(
                    r"<local-command-stdout>(.*?)</local-command-stdout>",
                    content,
                    re.DOTALL,
                )
                if stdout_match:
                    text = stdout_match.group(1).strip()
                else:
                    text = content
                content_blocks.append(
                    ContentBlock(
                        type=ContentType.TEXT,
                        text=text,
                    )
                )
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, TextBlock):
                        content_blocks.append(
                            ContentBlock(
                                type=ContentType.TEXT,
                                text=block.text,
                            )
                        )

            if content_blocks:
                return StreamMessage(
                    type=MessageType.SYSTEM,  # Use SYSTEM type for slash command output
                    content=content_blocks,
                )

        # Handle ResultMessage - don't duplicate the text, it's already been streamed
        # Just return a result marker without the text content
        elif isinstance(msg, ResultMessage):
            # Skip - text was already sent via AssistantMessage
            # Only useful for metadata like is_error, total_cost, etc.
            return None

        # Handle SystemMessage (init, etc.)
        elif isinstance(msg, SystemMessage):
            # Skip init messages, they're not useful to display
            if msg.subtype == "init":
                return None

        return None

    async def interrupt(self) -> bool:
        """Send interrupt signal to stop current query.

        Returns:
            True if interrupt was sent, False if no active query
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

    async def _handle_permission_request(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Handle permission requests from Claude SDK.

        Called when Claude wants to use a tool that requires permission.
        Sends request to the callback (which sends to WebSocket) and waits for response.
        """
        logger.info(f"[{self.session_id}] Permission request for tool: {tool_name}")

        if not self._permission_callback:
            # No callback configured - deny by default for safety
            logger.warning(
                f"[{self.session_id}] No permission callback - denying {tool_name}"
            )
            return PermissionResultDeny(message="No permission handler configured")

        try:
            # Create a future that the WebSocket handler will resolve
            loop = asyncio.get_event_loop()
            self._pending_permission = loop.create_future()

            # Call the callback which sends to WebSocket and returns immediately
            # The callback should store this future so WebSocket can resolve it
            await self._permission_callback(tool_name, tool_input, context)

            # Wait for user response (with timeout)
            try:
                allowed = await asyncio.wait_for(
                    self._pending_permission, timeout=300
                )  # 5 min timeout
            except asyncio.TimeoutError:
                logger.warning(
                    f"[{self.session_id}] Permission request timed out for {tool_name}"
                )
                return PermissionResultDeny(message="Permission request timed out")

            if allowed:
                logger.info(f"[{self.session_id}] Permission ALLOWED for {tool_name}")
                return PermissionResultAllow()
            else:
                logger.info(f"[{self.session_id}] Permission DENIED for {tool_name}")
                return PermissionResultDeny(message="User denied permission")

        except Exception as e:
            logger.error(f"[{self.session_id}] Error handling permission: {e}")
            return PermissionResultDeny(message=f"Permission error: {e}")
        finally:
            self._pending_permission = None

    def resolve_permission(self, allowed: bool) -> bool:
        """Resolve a pending permission request.

        Called by WebSocket handler when user responds to permission prompt.

        Args:
            allowed: True if user allowed, False if denied

        Returns:
            True if there was a pending request to resolve
        """
        if self._pending_permission and not self._pending_permission.done():
            self._pending_permission.set_result(allowed)
            return True
        return False

    @property
    def has_pending_permission(self) -> bool:
        """Check if there's a pending permission request."""
        return (
            self._pending_permission is not None and not self._pending_permission.done()
        )

    async def stop(self) -> None:
        """Stop the session."""
        self._connected = False
        self._client = None
        self._active_client = None
        logger.info(f"Session {self.session_id} stopped")

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._connected and self._client is not None


# Keep old class name for backwards compatibility
ClaudeProcess = ClaudeSession
