"""Utilities for session management and context building."""

import logging
from typing import Any

from .database import Database
from .session_bridge import SessionBridge
from .claude_process import ClaudeSession
from .gemini_process import GeminiSession

logger = logging.getLogger(__name__)


async def get_or_create_gemini_session(
    bridge: SessionBridge,
    session_id: str,
) -> GeminiSession | None:
    """Get or create a Gemini session.

    Uses a separate namespace to avoid conflicts with Claude sessions.
    """
    gemini_key = f"gemini:{session_id}"

    # Check if already active
    if gemini_key in bridge._active_sessions:
        session = bridge._active_sessions[gemini_key]
        if session.is_active:
            return session
        # Clean up dead session
        del bridge._active_sessions[gemini_key]

    # Look up in database
    db_session = await bridge.db.get_session(session_id)
    if not db_session:
        return None

    # Create Gemini session
    session = GeminiSession(
        session_id=session_id,
        working_dir=db_session["working_dir"],
    )
    await session.start()

    # Restore Gemini session ID if we have one
    metadata = db_session.get("metadata", {})
    if metadata.get("sdk_session_id") and metadata.get("provider") == "gemini":
        session.sdk_session_id = metadata["sdk_session_id"]
        logger.info(f"Restored Gemini session ID: {session.sdk_session_id}")

    bridge._active_sessions[gemini_key] = session
    return session


async def get_or_create_session_with_permissions(
    bridge: SessionBridge,
    session_id: str,
    permission_callback: Any,
) -> ClaudeSession | None:
    """Get or create a Claude session with permission callback.

    This is a custom version that injects the permission callback.
    """
    # Check if already active
    if session_id in bridge._active_sessions:
        session = bridge._active_sessions[session_id]
        if session.is_active:
            # Update permission callback for this WebSocket connection
            session._permission_callback = permission_callback
            return session
        # Clean up dead session
        del bridge._active_sessions[session_id]

    # Look up in database
    db_session = await bridge.db.get_session(session_id)
    if not db_session:
        return None

    # Create Claude session with permission callback
    session = ClaudeSession(
        session_id=session_id,
        working_dir=db_session["working_dir"],
        permission_callback=permission_callback,
    )
    await session.start()

    # Restore SDK session ID if we have one
    metadata = db_session.get("metadata", {})
    if metadata.get("sdk_session_id"):
        session._sdk_session_id = metadata["sdk_session_id"]
        logger.info(f"Restored SDK session ID: {session._sdk_session_id}")

    bridge._active_sessions[session_id] = session
    return session


async def build_roundtable_context(db: Database, session_id: str) -> str:
    """Build full conversation context for roundtable mode.

    Parses message history and formats with clear attribution so both
    agents understand who said what in previous exchanges.

    Args:
        db: Database instance
        session_id: Session identifier

    Returns:
        Formatted conversation history string, empty if no history
    """
    messages = await db.get_messages(session_id)

    if not messages:
        return ""

    context_parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            context_parts.append(f"[USER] {content}")
        elif role == "assistant":
            # Parse agent attribution from content prefix
            if content.startswith("[CLAUDE]"):
                context_parts.append(f"[CLAUDE] {content[8:].strip()}")
            elif content.startswith("[GEMINI]"):
                context_parts.append(f"[GEMINI] {content[8:].strip()}")
            elif " - Discussion Round " in content:
                # Handle discussion round format: [CLAUDE - Discussion Round 1]
                context_parts.append(content)
            else:
                context_parts.append(f"[ASSISTANT] {content}")

    return "\n\n".join(context_parts)


async def build_handoff_context(db: Database, session_id: str) -> str:
    """Build handoff context for agent switching.

    Includes actual conversation history so the new agent understands
    what was discussed. Falls back to session metadata if no messages.

    Args:
        db: Database instance
        session_id: Session identifier

    Returns:
        Formatted handoff context string
    """
    session = await db.get_session(session_id)
    if not session:
        return ""

    # Build header with session info
    parts = []
    parts.append(f"## Session Context (ID: {session_id[:8]})")
    parts.append(f"**Started by**: {session.get('original_provider') or 'Unknown'}")

    participants = session.get("participants", [])
    if participants:
        parts.append(f"**Participants so far**: {', '.join(participants)}")
    parts.append("")

    # Include actual conversation history (most important for context)
    messages = await db.get_messages(session_id, limit=20)
    if messages:
        parts.append("## Conversation History")
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            agent = msg.get("agent")

            if role == "user":
                parts.append(f"[USER] {content}")
            elif role == "assistant":
                # Use agent field if available, else parse from content
                if agent:
                    agent_label = agent.upper()
                elif content.startswith("[CLAUDE]"):
                    agent_label = "CLAUDE"
                    content = content[8:].strip()
                elif content.startswith("[GEMINI]"):
                    agent_label = "GEMINI"
                    content = content[8:].strip()
                else:
                    agent_label = "ASSISTANT"
                parts.append(f"[{agent_label}] {content}")
        parts.append("")

    parts.append(
        "You are now joining this conversation. Continue naturally from where it left off."
    )

    return "\n".join(parts)


async def store_agent_message(
    db: Database, session_id: str, content: str, agent: str
) -> None:
    """Store an agent message and update session metadata.

    Args:
        db: Database instance
        session_id: Session identifier
        content: Message content
        agent: Agent name (e.g., "claude", "gemini")
    """
    await db.add_message(
        session_id=session_id,
        role="assistant",
        content=content,
        agent=agent,
    )
    await db.increment_message_count(session_id)
    await db.add_participant(session_id, agent)
