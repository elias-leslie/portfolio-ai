"""Message and session log operations for dev-companion SQLite database."""

import json
import logging
from datetime import datetime

import aiosqlite

logger = logging.getLogger(__name__)


async def add_message(
    conn: aiosqlite.Connection,
    session_id: str,
    role: str,
    content: str,
    metadata: dict[str, object] | None = None,
    agent: str | None = None,
) -> int:
    """Insert a message record and return the new row ID."""
    now = datetime.utcnow().isoformat()
    cursor = await conn.execute(
        """
        INSERT INTO messages (session_id, role, content, created_at, metadata, agent)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, role, content, now, json.dumps(metadata or {}), agent),
    )
    await conn.commit()
    return cursor.lastrowid or 0


async def get_messages(
    conn: aiosqlite.Connection,
    session_id: str,
    limit: int = 100,
) -> list[dict[str, object]]:
    """Return messages for a session ordered by creation time."""
    messages: list[dict[str, object]] = []
    async with conn.execute(
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


async def add_session_log(
    conn: aiosqlite.Connection,
    session_id: str,
    agent: str,
    log_entry: str | None = None,
    key_files: str | None = None,
    learnings: str | None = None,
) -> int:
    """Insert a session log entry and return the new row ID."""
    now = datetime.utcnow().isoformat()
    cursor = await conn.execute(
        """
        INSERT INTO session_logs (session_id, timestamp, agent, log_entry, key_files, learnings)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, now, agent, log_entry, key_files, learnings),
    )
    await conn.commit()
    return cursor.lastrowid or 0


async def get_session_logs(
    conn: aiosqlite.Connection,
    session_id: str,
    limit: int = 20,
) -> list[dict[str, object]]:
    """Return log entries for a session (most recent first)."""
    logs: list[dict[str, object]] = []
    async with conn.execute(
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
