"""SQLite database for session persistence."""

import logging
from pathlib import Path

import aiosqlite

from .db_messages import (
    add_message as _add_message,
    add_session_log as _add_session_log,
    get_messages as _get_messages,
    get_session_logs as _get_session_logs,
)
from .db_schema import create_tables
from .db_sessions import (
    add_participant as _add_participant,
    create_session as _create_session,
    delete_session as _delete_session,
    get_session as _get_session,
    increment_message_count as _increment_message_count,
    list_sessions as _list_sessions,
    set_original_provider as _set_original_provider,
    update_session as _update_session,
    update_session_description as _update_session_description,
)

logger = logging.getLogger(__name__)

# Default storage location
DEFAULT_DB_PATH = Path.home() / ".portfolio-dev-companion" / "sessions.db"


class _DatabaseCore:
    """Connection management and session CRUD (≤10 methods)."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database and create tables if needed."""
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await create_tables(self._conn)

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    def _require_conn(self) -> aiosqlite.Connection:
        """Return connection or raise RuntimeError if not connected."""
        if not self._conn:
            raise RuntimeError("Database not connected")
        return self._conn

    async def create_session(
        self,
        session_id: str,
        working_dir: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Create a new session."""
        return await _create_session(self._require_conn(), session_id, working_dir, metadata)

    async def get_session(self, session_id: str) -> dict[str, object] | None:
        """Get a session by ID."""
        return await _get_session(self._require_conn(), session_id)

    async def update_session(
        self,
        session_id: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Update session metadata."""
        await _update_session(self._require_conn(), session_id, metadata)

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        """List sessions ordered by last update."""
        return await _list_sessions(self._require_conn(), limit, offset)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        return await _delete_session(self._require_conn(), session_id)


class _SessionMetaMixin:
    """Session metadata helpers (≤8 methods). Requires _require_conn from parent."""

    def _require_conn(self) -> aiosqlite.Connection:  # type: ignore[empty-body]
        """Provided by _DatabaseCore."""
        ...

    async def set_original_provider(self, session_id: str, provider: str) -> None:
        """Set original_provider only if not already set."""
        await _set_original_provider(self._require_conn(), session_id, provider)

    async def increment_message_count(self, session_id: str) -> None:
        """Increment message count for a session."""
        await _increment_message_count(self._require_conn(), session_id)

    async def add_participant(self, session_id: str, agent: str) -> None:
        """Add agent to participants array if not already present."""
        await _add_participant(self._require_conn(), session_id, agent)

    async def update_session_description(
        self,
        session_id: str,
        description: str,
    ) -> None:
        """Update session description."""
        await _update_session_description(self._require_conn(), session_id, description)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
        agent: str | None = None,
    ) -> int:
        """Add a message to a session and touch updated_at."""
        conn = self._require_conn()
        msg_id = await _add_message(conn, session_id, role, content, metadata, agent)
        await _update_session(conn, session_id)
        return msg_id

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Get messages for a session."""
        return await _get_messages(self._require_conn(), session_id, limit)

    async def add_session_log(
        self,
        session_id: str,
        agent: str,
        log_entry: str | None = None,
        key_files: str | None = None,
        learnings: str | None = None,
    ) -> int:
        """Add a log entry to session_logs table."""
        return await _add_session_log(
            self._require_conn(), session_id, agent, log_entry, key_files, learnings
        )

    async def get_session_logs(
        self,
        session_id: str,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        """Get recent log entries for a session."""
        return await _get_session_logs(self._require_conn(), session_id, limit)


class Database(_DatabaseCore, _SessionMetaMixin):
    """Async SQLite database for session storage."""
