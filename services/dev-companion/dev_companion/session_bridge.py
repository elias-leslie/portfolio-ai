"""Bridge between web sessions and Claude Code sessions."""

import logging
import uuid
from pathlib import Path
from typing import Any

from .claude_process import ClaudeSession
from .database import Database
from .stream_parser import StreamMessage, message_to_dict

logger = logging.getLogger(__name__)


class SessionBridge:
    """Manages the mapping between web sessions and Claude processes.

    This bridge:
    - Creates and tracks Claude sessions
    - Persists session metadata to SQLite
    - Handles session resume/reconnect
    - Routes messages between web clients and Claude
    """

    def __init__(self, db: Database, default_working_dir: str | Path | None = None):
        """Initialize session bridge.

        Args:
            db: Database instance for persistence
            default_working_dir: Default working directory for new sessions
        """
        self.db = db
        self.default_working_dir = Path(
            default_working_dir or Path.home() / "portfolio-ai"
        ).resolve()
        self._active_sessions: dict[str, ClaudeSession] = {}

    async def create_session(
        self,
        working_dir: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a new session.

        Args:
            working_dir: Working directory (uses default if None)
            metadata: Optional metadata for the session

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())[:8]  # Short ID for convenience
        work_dir = Path(working_dir) if working_dir else self.default_working_dir

        # Persist to database
        await self.db.create_session(
            session_id=session_id,
            working_dir=str(work_dir),
            metadata=metadata,
        )

        logger.info(f"Created session {session_id} with working dir {work_dir}")
        return session_id

    async def get_session(self, session_id: str) -> ClaudeSession | None:
        """Get or create a Claude session.

        If the session exists in the database but isn't active,
        it will be started.

        Args:
            session_id: Session identifier

        Returns:
            Active ClaudeSession or None if not found
        """
        # Check if already active
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            if session.is_active:
                return session
            # Clean up dead session
            del self._active_sessions[session_id]

        # Look up in database
        db_session = await self.db.get_session(session_id)
        if not db_session:
            return None

        # Create and start Claude session
        session = ClaudeSession(
            session_id=session_id,
            working_dir=db_session["working_dir"],
        )
        await session.start()

        self._active_sessions[session_id] = session
        return session

    async def send_message(
        self,
        session_id: str,
        message: str,
    ) -> list[StreamMessage]:
        """Send a message to a session and collect the response.

        Args:
            session_id: Session identifier
            message: User message

        Returns:
            List of response messages
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Store user message
        await self.db.add_message(
            session_id=session_id,
            role="user",
            content=message,
        )

        # Send to Claude and collect response
        responses: list[StreamMessage] = []
        async for msg in session.send(message):
            responses.append(msg)

        # Store assistant response
        if responses:
            import json

            content = json.dumps([message_to_dict(m) for m in responses])
            await self.db.add_message(
                session_id=session_id,
                role="assistant",
                content=content,
            )

        return responses

    async def stop_session(self, session_id: str) -> None:
        """Stop an active session.

        Args:
            session_id: Session identifier
        """
        if session_id in self._active_sessions:
            session = self._active_sessions[session_id]
            await session.stop()
            del self._active_sessions[session_id]
            logger.info(f"Stopped session {session_id}")

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session completely.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted
        """
        # Stop if active
        await self.stop_session(session_id)

        # Delete from database
        return await self.db.delete_session(session_id)

    async def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all sessions.

        Args:
            limit: Maximum sessions to return

        Returns:
            List of session records with active status
        """
        sessions = await self.db.list_sessions(limit=limit)

        # Add active status
        for session in sessions:
            session["is_active"] = session["id"] in self._active_sessions

        return sessions

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get message history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum messages to return

        Returns:
            List of messages
        """
        return await self.db.get_messages(session_id, limit=limit)

    async def cleanup_inactive(self) -> int:
        """Stop all inactive Claude processes.

        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0
        to_remove = []

        for session_id, session in self._active_sessions.items():
            if not session.is_active:
                to_remove.append(session_id)

        for session_id in to_remove:
            await self.stop_session(session_id)
            cleaned += 1

        return cleaned

    async def shutdown(self) -> None:
        """Shutdown all active sessions."""
        for session_id in list(self._active_sessions.keys()):
            await self.stop_session(session_id)
