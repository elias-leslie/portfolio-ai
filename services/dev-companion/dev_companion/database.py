"""SQLite database for session persistence."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Default storage location
DEFAULT_DB_PATH = Path.home() / ".portfolio-dev-companion" / "sessions.db"


class Database:
    """Async SQLite database for session storage."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database and create tables if needed."""
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        """Create database tables."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                working_dir TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                original_provider TEXT,
                message_count INTEGER DEFAULT 0,
                description TEXT,
                participants TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                agent TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, created_at);

            CREATE TABLE IF NOT EXISTS session_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                agent TEXT NOT NULL,
                log_entry TEXT,
                key_files TEXT,
                learnings TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_session_logs_session
            ON session_logs(session_id);
        """)
        await self._conn.commit()

        # Add columns to existing tables if they don't exist (migrations)
        await self._migrate_sessions_table()
        await self._migrate_messages_table()

    async def create_session(
        self,
        session_id: str,
        working_dir: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new session.

        Args:
            session_id: Unique session identifier
            working_dir: Working directory for this session
            metadata: Optional metadata dict

        Returns:
            Session record
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        now = datetime.utcnow().isoformat()

        await self._conn.execute(
            """
            INSERT INTO sessions (id, working_dir, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, working_dir, now, now, json.dumps(metadata or {})),
        )
        await self._conn.commit()

        return {
            "id": session_id,
            "working_dir": working_dir,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session record or None
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "working_dir": row["working_dir"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"]),
                    "original_provider": row["original_provider"]
                    if "original_provider" in row.keys()
                    else None,
                    "message_count": row["message_count"]
                    if "message_count" in row.keys()
                    else 0,
                    "description": row["description"]
                    if "description" in row.keys()
                    else None,
                    "participants": json.loads(row["participants"])
                    if "participants" in row.keys() and row["participants"]
                    else [],
                }
        return None

    async def update_session(
        self,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Update session metadata.

        Args:
            session_id: Session identifier
            metadata: New metadata to merge
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        now = datetime.utcnow().isoformat()

        if metadata:
            # Merge with existing metadata
            existing = await self.get_session(session_id)
            if existing:
                merged = {**existing.get("metadata", {}), **metadata}
                await self._conn.execute(
                    "UPDATE sessions SET updated_at = ?, metadata = ? WHERE id = ?",
                    (now, json.dumps(merged), session_id),
                )
            else:
                await self._conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (now, session_id),
                )
        else:
            await self._conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

        await self._conn.commit()

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List sessions ordered by last update.

        Args:
            limit: Maximum sessions to return
            offset: Offset for pagination

        Returns:
            List of session records
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        sessions = []
        async with self._conn.execute(
            """
            SELECT * FROM sessions
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ) as cursor:
            async for row in cursor:
                sessions.append(
                    {
                        "id": row["id"],
                        "working_dir": row["working_dir"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "metadata": json.loads(row["metadata"]),
                        "original_provider": row["original_provider"]
                        if "original_provider" in row.keys()
                        else None,
                        "message_count": row["message_count"]
                        if "message_count" in row.keys()
                        else 0,
                        "description": row["description"]
                        if "description" in row.keys()
                        else None,
                        "participants": json.loads(row["participants"])
                        if "participants" in row.keys() and row["participants"]
                        else [],
                    }
                )
        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            "DELETE FROM sessions WHERE id = ?",
            (session_id,),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        agent: str | None = None,
    ) -> int:
        """Add a message to a session.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content (JSON string for complex content)
            metadata: Optional message metadata
            agent: Which agent produced this message (claude, gemini)

        Returns:
            Message ID
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        now = datetime.utcnow().isoformat()

        cursor = await self._conn.execute(
            """
            INSERT INTO messages (session_id, role, content, created_at, metadata, agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, now, json.dumps(metadata or {}), agent),
        )
        await self._conn.commit()

        # Update session's updated_at
        await self.update_session(session_id)

        return cursor.lastrowid or 0

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get messages for a session.

        Args:
            session_id: Session identifier
            limit: Maximum messages to return

        Returns:
            List of message records
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        messages = []
        async with self._conn.execute(
            """
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, limit),
        ) as cursor:
            async for row in cursor:
                messages.append(
                    {
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "role": row["role"],
                        "content": row["content"],
                        "created_at": row["created_at"],
                        "metadata": json.loads(row["metadata"]),
                        "agent": row["agent"],
                    }
                )
        return messages

    async def _migrate_sessions_table(self) -> None:
        """Add new columns to existing sessions table if they don't exist."""
        if not self._conn:
            return

        # Check existing columns
        async with self._conn.execute("PRAGMA table_info(sessions)") as cursor:
            existing_cols = {row[1] async for row in cursor}

        # Add missing columns
        migrations = [
            ("original_provider", "TEXT"),
            ("message_count", "INTEGER DEFAULT 0"),
            ("description", "TEXT"),
            ("participants", "TEXT DEFAULT '[]'"),
        ]

        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                try:
                    await self._conn.execute(
                        f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"Added column {col_name} to sessions table")
                except Exception as e:
                    logger.warning(f"Could not add column {col_name}: {e}")

        await self._conn.commit()

    async def _migrate_messages_table(self) -> None:
        """Add agent column to existing messages table if it doesn't exist."""
        if not self._conn:
            return

        # Check existing columns
        async with self._conn.execute("PRAGMA table_info(messages)") as cursor:
            existing_cols = {row[1] async for row in cursor}

        # Add agent column if missing
        if "agent" not in existing_cols:
            try:
                await self._conn.execute("ALTER TABLE messages ADD COLUMN agent TEXT")
                logger.info("Added column agent to messages table")
            except Exception as e:
                logger.warning(f"Could not add column agent: {e}")

        await self._conn.commit()

    async def set_original_provider(
        self,
        session_id: str,
        provider: str,
    ) -> None:
        """Set original_provider on first message (only if not already set).

        Args:
            session_id: Session identifier
            provider: Provider name (claude, gemini, both)
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Only set if not already set
        await self._conn.execute(
            """
            UPDATE sessions
            SET original_provider = ?
            WHERE id = ? AND original_provider IS NULL
            """,
            (provider, session_id),
        )
        await self._conn.commit()

    async def increment_message_count(self, session_id: str) -> None:
        """Increment message count for a session."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            "UPDATE sessions SET message_count = COALESCE(message_count, 0) + 1 WHERE id = ?",
            (session_id,),
        )
        await self._conn.commit()

    async def add_participant(self, session_id: str, agent: str) -> None:
        """Add agent to participants array if not already present.

        Args:
            session_id: Session identifier
            agent: Agent name (claude or gemini)
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Get current participants
        async with self._conn.execute(
            "SELECT participants FROM sessions WHERE id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return

            participants = json.loads(row[0] or "[]")
            if agent not in participants:
                participants.append(agent)
                await self._conn.execute(
                    "UPDATE sessions SET participants = ? WHERE id = ?",
                    (json.dumps(participants), session_id),
                )
                await self._conn.commit()

    async def update_session_description(
        self,
        session_id: str,
        description: str,
    ) -> None:
        """Update session description."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            "UPDATE sessions SET description = ? WHERE id = ?",
            (description, session_id),
        )
        await self._conn.commit()

    async def add_session_log(
        self,
        session_id: str,
        agent: str,
        log_entry: str | None = None,
        key_files: str | None = None,
        learnings: str | None = None,
    ) -> int:
        """Add a log entry to session_logs table.

        Args:
            session_id: Session identifier
            agent: Agent name (claude or gemini)
            log_entry: Terse worklog-style entry
            key_files: JSON array of file:line references
            learnings: Any lessons learned

        Returns:
            Log entry ID
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        now = datetime.utcnow().isoformat()

        cursor = await self._conn.execute(
            """
            INSERT INTO session_logs (session_id, timestamp, agent, log_entry, key_files, learnings)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, now, agent, log_entry, key_files, learnings),
        )
        await self._conn.commit()

        return cursor.lastrowid or 0

    async def get_session_logs(
        self,
        session_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get recent log entries for a session.

        Args:
            session_id: Session identifier
            limit: Maximum entries to return

        Returns:
            List of log entry records (most recent first)
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        logs = []
        async with self._conn.execute(
            """
            SELECT * FROM session_logs
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit),
        ) as cursor:
            async for row in cursor:
                logs.append(
                    {
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "timestamp": row["timestamp"],
                        "agent": row["agent"],
                        "log_entry": row["log_entry"],
                        "key_files": row["key_files"],
                        "learnings": row["learnings"],
                    }
                )
        return logs
