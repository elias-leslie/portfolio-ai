"""Manage Claude Code via the official Claude Agent SDK."""

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.types import (
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)

from .stream_parser import StreamMessage, ContentBlock, MessageType, ContentType

logger = logging.getLogger(__name__)


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
    ):
        """Initialize session.

        Args:
            session_id: Unique session identifier
            working_dir: Working directory for this session
        """
        self.session_id = session_id
        self.working_dir = Path(working_dir).resolve()
        self._client: ClaudeSDKClient | None = None
        self._options: ClaudeAgentOptions | None = None
        self._connected = False

    async def start(self) -> None:
        """Start the session by initializing the SDK client."""
        self._options = ClaudeAgentOptions(
            cwd=str(self.working_dir),
            # Use default permission mode (will prompt for dangerous operations)
            permission_mode="default",
            # Load user settings to enable OAuth credentials from ~/.claude/.credentials.json
            setting_sources=["user"],
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
        if not self._client:
            raise ClaudeProcessError("Session not started")

        logger.info(f"Sending message to Claude: {message[:100]}...")

        try:
            async with self._client as client:
                await client.query(message)

                async for msg in client.receive_response():
                    stream_msg = self._convert_message(msg)
                    if stream_msg:
                        yield stream_msg

        except Exception as e:
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
                    content_blocks.append(ContentBlock(
                        type=ContentType.TEXT,
                        text=block.text,
                    ))
                elif isinstance(block, ToolUseBlock):
                    content_blocks.append(ContentBlock(
                        type=ContentType.TOOL_USE,
                        tool_name=block.name,
                        tool_input=block.input if hasattr(block, 'input') else None,
                        tool_use_id=block.id if hasattr(block, 'id') else None,
                    ))
                elif isinstance(block, ToolResultBlock):
                    content_blocks.append(ContentBlock(
                        type=ContentType.TOOL_RESULT,
                        text=str(block.content) if hasattr(block, 'content') else None,
                        tool_use_id=block.tool_use_id if hasattr(block, 'tool_use_id') else None,
                    ))

            if content_blocks:
                return StreamMessage(
                    type=MessageType.ASSISTANT,
                    content=content_blocks,
                    stop_reason=msg.stop_reason if hasattr(msg, 'stop_reason') else None,
                )

        # Handle UserMessage (slash command output, tool results echoed back)
        elif isinstance(msg, UserMessage):
            content = msg.content
            # Content can be a string (e.g., <local-command-stdout>...</local-command-stdout>)
            # or a list of content blocks
            if isinstance(content, str):
                # Extract content from local-command-stdout tags if present
                import re
                stdout_match = re.search(r'<local-command-stdout>(.*?)</local-command-stdout>', content, re.DOTALL)
                if stdout_match:
                    text = stdout_match.group(1).strip()
                else:
                    text = content
                content_blocks.append(ContentBlock(
                    type=ContentType.TEXT,
                    text=text,
                ))
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, TextBlock):
                        content_blocks.append(ContentBlock(
                            type=ContentType.TEXT,
                            text=block.text,
                        ))

            if content_blocks:
                return StreamMessage(
                    type=MessageType.SYSTEM,  # Use SYSTEM type for slash command output
                    content=content_blocks,
                )

        # Handle ResultMessage
        elif isinstance(msg, ResultMessage):
            result_text = msg.result
            if result_text:
                content_blocks.append(ContentBlock(
                    type=ContentType.TEXT,
                    text=str(result_text),
                ))
                return StreamMessage(
                    type=MessageType.RESULT,
                    content=content_blocks,
                    stop_reason="end_turn",
                )

        # Handle SystemMessage (init, etc.)
        elif isinstance(msg, SystemMessage):
            # Skip init messages, they're not useful to display
            if msg.subtype == 'init':
                return None

        return None

    async def stop(self) -> None:
        """Stop the session."""
        self._connected = False
        self._client = None
        logger.info(f"Session {self.session_id} stopped")

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._connected and self._client is not None


# Keep old class name for backwards compatibility
ClaudeProcess = ClaudeSession
