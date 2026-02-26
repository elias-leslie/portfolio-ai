"""Convert Claude SDK messages to StreamMessage format."""

import re
import logging
from typing import Union

from claude_agent_sdk.types import (
    AssistantMessage,
    UserMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)

from .stream_parser import StreamMessage, ContentBlock, MessageType, ContentType

logger = logging.getLogger(__name__)

# Pattern for extracting local command stdout content
_LOCAL_COMMAND_STDOUT_RE = re.compile(
    r"<local-command-stdout>(.*?)</local-command-stdout>",
    re.DOTALL,
)

SdkMessage = Union[AssistantMessage, UserMessage, ResultMessage, SystemMessage]


def _convert_text_block(block: TextBlock) -> ContentBlock:
    return ContentBlock(type=ContentType.TEXT, text=block.text)


def _convert_tool_use_block(block: ToolUseBlock) -> ContentBlock:
    return ContentBlock(
        type=ContentType.TOOL_USE,
        tool_name=block.name,
        tool_input=block.input if hasattr(block, "input") else None,
        tool_use_id=block.id if hasattr(block, "id") else None,
    )


def _convert_tool_result_block(block: ToolResultBlock) -> ContentBlock:
    return ContentBlock(
        type=ContentType.TOOL_RESULT,
        text=str(block.content) if hasattr(block, "content") else None,
        tool_use_id=block.tool_use_id if hasattr(block, "tool_use_id") else None,
    )


def _convert_assistant_message(msg: AssistantMessage) -> StreamMessage | None:
    content_blocks: list[ContentBlock] = []
    for block in msg.content:
        if isinstance(block, TextBlock):
            content_blocks.append(_convert_text_block(block))
        elif isinstance(block, ToolUseBlock):
            content_blocks.append(_convert_tool_use_block(block))
        elif isinstance(block, ToolResultBlock):
            content_blocks.append(_convert_tool_result_block(block))
    if not content_blocks:
        return None
    return StreamMessage(
        type=MessageType.ASSISTANT,
        content=content_blocks,
        stop_reason=msg.stop_reason if hasattr(msg, "stop_reason") else None,
    )


def _extract_user_text(content: str) -> str:
    """Extract text from local-command-stdout tags if present, else return as-is."""
    match = _LOCAL_COMMAND_STDOUT_RE.search(content)
    return match.group(1).strip() if match else content


def _convert_user_message(msg: UserMessage) -> StreamMessage | None:
    content_blocks: list[ContentBlock] = []
    content = msg.content
    if isinstance(content, str):
        text = _extract_user_text(content)
        content_blocks.append(ContentBlock(type=ContentType.TEXT, text=text))
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, TextBlock):
                content_blocks.append(_convert_text_block(block))
    if not content_blocks:
        return None
    return StreamMessage(
        type=MessageType.SYSTEM,
        content=content_blocks,
    )


def convert_sdk_message(msg: SdkMessage) -> StreamMessage | None:
    """Convert an SDK message to our StreamMessage format.

    Returns None for messages that should not be forwarded to the client
    (e.g. ResultMessage, SystemMessage init).
    """
    if isinstance(msg, AssistantMessage):
        return _convert_assistant_message(msg)
    if isinstance(msg, UserMessage):
        return _convert_user_message(msg)
    if isinstance(msg, ResultMessage):
        # Text already streamed via AssistantMessage; skip duplicates.
        return None
    if isinstance(msg, SystemMessage):
        # Init messages are not useful to display.
        return None
    return None
