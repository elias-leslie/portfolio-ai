"""Parse Claude Code's stream-json output format."""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    """Types of messages in Claude's stream-json output."""

    ASSISTANT = "assistant"
    USER = "user"
    SYSTEM = "system"
    RESULT = "result"


class ContentType(str, Enum):
    """Types of content blocks."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"


@dataclass
class ContentBlock:
    """A content block within a message."""

    type: ContentType
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_use_id: str | None = None
    is_error: bool = False


@dataclass
class StreamMessage:
    """A parsed message from Claude's stream-json output."""

    type: MessageType
    content: list[ContentBlock] = field(default_factory=list)
    model: str | None = None
    stop_reason: str | None = None
    session_id: str | None = None
    raw: dict[str, Any] | None = None


def parse_stream_line(line: str | bytes) -> StreamMessage | None:
    """Parse a single line of stream-json output.

    Args:
        line: A line from Claude's stdout (may be bytes or str)

    Returns:
        Parsed StreamMessage or None if line is empty/invalid
    """
    if isinstance(line, bytes):
        line = line.decode("utf-8", errors="replace")

    line = line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Not JSON - could be plain text output
        return StreamMessage(
            type=MessageType.SYSTEM,
            content=[ContentBlock(type=ContentType.TEXT, text=line)],
        )

    return _parse_message(data)


def _parse_message(data: dict[str, Any]) -> StreamMessage:
    """Parse a JSON message into a StreamMessage."""
    msg_type = data.get("type", "system")

    # Map to our enum
    try:
        message_type = MessageType(msg_type)
    except ValueError:
        message_type = MessageType.SYSTEM

    content_blocks = []

    # Parse content array if present
    if "content" in data:
        for block in data.get("content", []):
            content_blocks.append(_parse_content_block(block))

    # Handle message field (sometimes used instead of content)
    elif "message" in data:
        msg = data["message"]
        if isinstance(msg, str):
            content_blocks.append(ContentBlock(type=ContentType.TEXT, text=msg))
        elif isinstance(msg, dict) and "content" in msg:
            for block in msg.get("content", []):
                content_blocks.append(_parse_content_block(block))

    # Handle text field directly
    elif "text" in data:
        content_blocks.append(ContentBlock(type=ContentType.TEXT, text=data["text"]))

    return StreamMessage(
        type=message_type,
        content=content_blocks,
        model=data.get("model"),
        stop_reason=data.get("stop_reason"),
        session_id=data.get("session_id"),
        raw=data,
    )


def _parse_content_block(block: dict[str, Any] | str) -> ContentBlock:
    """Parse a content block."""
    if isinstance(block, str):
        return ContentBlock(type=ContentType.TEXT, text=block)

    block_type = block.get("type", "text")

    try:
        content_type = ContentType(block_type)
    except ValueError:
        content_type = ContentType.TEXT

    return ContentBlock(
        type=content_type,
        text=block.get("text"),
        tool_name=block.get("name") or block.get("tool_name"),
        tool_input=block.get("input") or block.get("tool_input"),
        tool_use_id=block.get("id") or block.get("tool_use_id"),
        is_error=block.get("is_error", False),
    )


def message_to_dict(msg: StreamMessage) -> dict[str, Any]:
    """Convert a StreamMessage to a JSON-serializable dict."""
    return {
        "type": msg.type.value,
        "content": [
            {
                "type": block.type.value,
                "text": block.text,
                "tool_name": block.tool_name,
                "tool_input": block.tool_input,
                "tool_use_id": block.tool_use_id,
                "is_error": block.is_error,
            }
            for block in msg.content
        ],
        "model": msg.model,
        "stop_reason": msg.stop_reason,
        "session_id": msg.session_id,
    }
