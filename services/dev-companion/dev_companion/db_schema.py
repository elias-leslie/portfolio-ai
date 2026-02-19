"""SQLite schema creation and migrations for dev-companion."""

import logging

import aiosqlite

logger = logging.getLogger(__name__)

_CREATE_SESSIONS = """
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
"""

_CREATE_MESSAGES = """
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
"""

_CREATE_SESSION_LOGS = """
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
"""

_CREATE_INDEXES = """
    CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, created_at);

    CREATE INDEX IF NOT EXISTS idx_session_logs_session
    ON session_logs(session_id);
"""

_SESSIONS_MIGRATIONS: list[tuple[str, str]] = [
    ("original_provider", "TEXT"),
    ("message_count", "INTEGER DEFAULT 0"),
    ("description", "TEXT"),
    ("participants", "TEXT DEFAULT '[]'"),
]


async def create_tables(conn: aiosqlite.Connection) -> None:
    """Create all database tables and indexes."""
    await conn.executescript(
        _CREATE_SESSIONS + _CREATE_MESSAGES + _CREATE_SESSION_LOGS + _CREATE_INDEXES
    )
    await conn.commit()
    await _migrate_sessions_table(conn)
    await _migrate_messages_table(conn)


async def _migrate_sessions_table(conn: aiosqlite.Connection) -> None:
    """Add new columns to existing sessions table if missing."""
    async with conn.execute("PRAGMA table_info(sessions)") as cursor:
        existing_cols = {row[1] async for row in cursor}

    for col_name, col_type in _SESSIONS_MIGRATIONS:
        if col_name in existing_cols:
            continue
        try:
            await conn.execute(
                f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}"
            )
            logger.info("Added column %s to sessions table", col_name)
        except Exception as e:
            logger.warning("Could not add column %s: %s", col_name, e)

    await conn.commit()


async def _migrate_messages_table(conn: aiosqlite.Connection) -> None:
    """Add agent column to existing messages table if missing."""
    async with conn.execute("PRAGMA table_info(messages)") as cursor:
        existing_cols = {row[1] async for row in cursor}

    if "agent" in existing_cols:
        return

    try:
        await conn.execute("ALTER TABLE messages ADD COLUMN agent TEXT")
        logger.info("Added column agent to messages table")
    except Exception as e:
        logger.warning("Could not add column agent: %s", e)

    await conn.commit()
