"""Claude progress logging API.

Provides endpoints for logging and querying Claude session progress.
Replaces text-based claude-progress.txt with queryable database.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/claude", tags=["claude"])


class ProgressEntry(BaseModel):
    """Request model for logging a progress entry."""

    session_id: str | None = None
    action: str
    action_type: str | None = None  # start, progress, complete, verify, audit, pause, plan
    feature_id: str | None = None
    task_file: str | None = None
    files_modified: list[str] | None = None
    details: dict[str, Any] | None = None
    git_commit: str | None = None
    context_percent: int | None = None


class ProgressResponse(BaseModel):
    """Response model for a progress entry."""

    id: int
    session_id: str | None
    logged_at: str
    action: str
    action_type: str | None
    feature_id: str | None
    task_file: str | None
    files_modified: list[str] | None
    details: dict[str, Any] | None
    git_commit: str | None
    context_percent: int | None


@router.post("/progress", response_model=dict[str, str])
async def log_progress(entry: ProgressEntry) -> dict[str, str]:
    """Log a progress entry.

    Args:
        entry: Progress data to log

    Returns:
        {"status": "logged"}
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            conn.execute(
                """
                INSERT INTO claude_progress_log
                (session_id, action, action_type, feature_id, task_file,
                 files_modified, details, git_commit, context_percent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry.session_id,
                    entry.action,
                    entry.action_type,
                    entry.feature_id,
                    entry.task_file,
                    entry.files_modified,
                    json.dumps(entry.details) if entry.details else None,
                    entry.git_commit,
                    entry.context_percent,
                ),
            )
            conn.commit()

        logger.info(
            "progress_logged",
            session_id=entry.session_id,
            action_type=entry.action_type,
            feature_id=entry.feature_id,
        )

        return {"status": "logged"}

    except Exception as e:
        logger.error("log_progress_failed", error=str(e))
        return {"status": "error", "error": str(e)}


@router.get("/progress", response_model=dict[str, Any])
async def get_progress(
    limit: int = Query(25, le=100, description="Max entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session_id: str | None = Query(None, description="Filter by session ID"),
    feature_id: str | None = Query(None, description="Filter by feature ID"),
    action_type: str | None = Query(None, description="Filter by action type"),
    since: str | None = Query(None, description="Filter entries after ISO timestamp"),
) -> dict[str, Any]:
    """Get progress entries with filtering.

    Args:
        limit: Max entries to return (default 25, max 100)
        offset: Offset for pagination
        session_id: Filter by session ID
        feature_id: Filter by feature ID
        action_type: Filter by action type
        since: Filter entries after this ISO timestamp

    Returns:
        {"entries": [...], "limit": N, "offset": N}
    """
    conn_mgr = get_connection_manager()

    try:
        conditions: list[str] = []
        params: list[Any] = []

        if session_id:
            conditions.append("session_id = %s")
            params.append(session_id)
        if feature_id:
            conditions.append("feature_id = %s")
            params.append(feature_id)
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        if since:
            conditions.append("logged_at >= %s")
            params.append(since)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        with conn_mgr.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, session_id, logged_at, action, action_type,
                       feature_id, task_file, files_modified, details,
                       git_commit, context_percent
                FROM claude_progress_log
                {where_clause}
                ORDER BY logged_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params),
            ).fetchall()

            entries = [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "logged_at": r[2].isoformat() if r[2] else None,
                    "action": r[3],
                    "action_type": r[4],
                    "feature_id": r[5],
                    "task_file": r[6],
                    "files_modified": r[7],
                    "details": r[8],
                    "git_commit": r[9],
                    "context_percent": r[10],
                }
                for r in rows
            ]

        return {"entries": entries, "limit": limit, "offset": offset}

    except Exception as e:
        logger.error("get_progress_failed", error=str(e))
        return {"entries": [], "limit": limit, "offset": offset, "error": str(e)}


@router.get("/progress/latest", response_model=dict[str, Any])
async def get_latest_session() -> dict[str, Any]:
    """Get the most recent session's progress.

    Returns:
        {"entries": [...]} for the latest session
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, logged_at, action, action_type,
                       feature_id, task_file, files_modified, details,
                       git_commit, context_percent
                FROM claude_progress_log
                WHERE session_id = (
                    SELECT session_id FROM claude_progress_log
                    WHERE session_id IS NOT NULL
                    ORDER BY logged_at DESC LIMIT 1
                )
                ORDER BY logged_at DESC
                """
            ).fetchall()

            entries = [
                {
                    "id": r[0],
                    "session_id": r[1],
                    "logged_at": r[2].isoformat() if r[2] else None,
                    "action": r[3],
                    "action_type": r[4],
                    "feature_id": r[5],
                    "task_file": r[6],
                    "files_modified": r[7],
                    "details": r[8],
                    "git_commit": r[9],
                    "context_percent": r[10],
                }
                for r in rows
            ]

        return {"entries": entries}

    except Exception as e:
        logger.error("get_latest_session_failed", error=str(e))
        return {"entries": [], "error": str(e)}
