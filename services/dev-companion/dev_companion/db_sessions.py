"""Session CRUD operations for dev-companion SQLite database."""

import json
import logging
from datetime import datetime

import aiosqlite

logger = logging.getLogger(__name__)


def _row_to_session(row: aiosqlite.Row) -> dict[str, object]:
    """Convert a database row to a session dict."""
    keys = row.keys()
    return {
        "id": row["id"],
        "working_dir": row["working_dir"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "metadata": json.loads(row["metadata"]),
        "original_provider": row["original_provider"] if "original_provider" in keys else None,
        "message_count": row["message_count"] if "message_count" in keys else 0,
        "description": row["description"] if "description" in keys else None,
        "participants": (
            json.loads(row["participants"])
            if "participants" in keys and row["participants"]
            else []
        ),
    }


async def create_session(
    conn: aiosqlite.Connection,
    session_id: str,
    working_dir: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Create a new session record."""
    now = datetime.utcnow().isoformat()
    await conn.execute(
        """
        INSERT INTO sessions (id, working_dir, created_at, updated_at, metadata)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, working_dir, now, now, json.dumps(metadata or {})),
    )
    await conn.commit()
    return {
        "id": session_id,
        "working_dir": working_dir,
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {},
    }


async def get_session(
    conn: aiosqlite.Connection,
    session_id: str,
) -> dict[str, object] | None:
    """Get a session by ID, returning None if not found."""
    async with conn.execute(
        "SELECT * FROM sessions WHERE id = ?",
        (session_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return _row_to_session(row) if row else None


async def update_session(
    conn: aiosqlite.Connection,
    session_id: str,
    metadata: dict[str, object] | None = None,
) -> None:
    """Update session updated_at and optionally merge metadata."""
    now = datetime.utcnow().isoformat()
    if not metadata:
        await conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        await conn.commit()
        return

    existing = await get_session(conn, session_id)
    if existing:
        merged = {**existing.get("metadata", {}), **metadata}  # type: ignore[arg-type]
        await conn.execute(
            "UPDATE sessions SET updated_at = ?, metadata = ? WHERE id = ?",
            (now, json.dumps(merged), session_id),
        )
    else:
        await conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
    await conn.commit()


async def list_sessions(
    conn: aiosqlite.Connection,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, object]]:
    """List sessions ordered by last update."""
    sessions: list[dict[str, object]] = []
    async with conn.execute(
        """
        SELECT * FROM sessions
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ) as cursor:
        async for row in cursor:
            sessions.append(_row_to_session(row))
    return sessions


async def delete_session(
    conn: aiosqlite.Connection,
    session_id: str,
) -> bool:
    """Delete a session by ID. Returns True if deleted."""
    cursor = await conn.execute(
        "DELETE FROM sessions WHERE id = ?",
        (session_id,),
    )
    await conn.commit()
    return cursor.rowcount > 0


async def set_original_provider(
    conn: aiosqlite.Connection,
    session_id: str,
    provider: str,
) -> None:
    """Set original_provider only if not already set."""
    await conn.execute(
        """
        UPDATE sessions
        SET original_provider = ?
        WHERE id = ? AND original_provider IS NULL
        """,
        (provider, session_id),
    )
    await conn.commit()


async def increment_message_count(
    conn: aiosqlite.Connection,
    session_id: str,
) -> None:
    """Increment message count for a session."""
    await conn.execute(
        "UPDATE sessions SET message_count = COALESCE(message_count, 0) + 1 WHERE id = ?",
        (session_id,),
    )
    await conn.commit()


async def add_participant(
    conn: aiosqlite.Connection,
    session_id: str,
    agent: str,
) -> None:
    """Add agent to participants list if not already present."""
    async with conn.execute(
        "SELECT participants FROM sessions WHERE id = ?",
        (session_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if not row:
        return

    participants: list[str] = json.loads(row[0] or "[]")
    if agent in participants:
        return

    participants.append(agent)
    await conn.execute(
        "UPDATE sessions SET participants = ? WHERE id = ?",
        (json.dumps(participants), session_id),
    )
    await conn.commit()


async def update_session_description(
    conn: aiosqlite.Connection,
    session_id: str,
    description: str,
) -> None:
    """Update session description field."""
    await conn.execute(
        "UPDATE sessions SET description = ? WHERE id = ?",
        (description, session_id),
    )
    await conn.commit()
