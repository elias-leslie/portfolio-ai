"""Notes router - capability notes endpoints.

This module provides REST API endpoints for capability notes:
- POST /notes - Create a new capability note
- GET /notes - List notes (with filtering)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from .database import get_table_name, note_from_row
from .models import NoteCreateRequest, NoteCreateResponse, NotesListResponse

logger = get_logger(__name__)

router = APIRouter()


# Endpoints
@router.post("/notes", response_model=NoteCreateResponse)
async def create_note(note: NoteCreateRequest) -> NoteCreateResponse:
    """Create a new capability note.

    Body:
        - capability_type: Type of capability (db, celery, api)
        - capability_id: ID of the capability (optional)
        - insight_id: ID of related insight (optional)
        - note_type: Type of note (observation, recommendation, question, decision, reference)
        - note: Note content
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Validate capability exists if capability_id provided
            if note.capability_id:
                table = get_table_name(note.capability_type)
                check_query = f"SELECT id FROM {table} WHERE id = %s"
                result = conn.execute(check_query, [note.capability_id]).fetchone()
                if not result:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Capability not found: {note.capability_type}/{note.capability_id}",
                    )

            # Validate insight exists if insight_id provided
            if note.insight_id:
                check_query = "SELECT id FROM capability_insights WHERE id = %s"
                result = conn.execute(check_query, [note.insight_id]).fetchone()
                if not result:
                    raise HTTPException(
                        status_code=404, detail=f"Insight not found: {note.insight_id}"
                    )

            # Insert note
            insert_query = """
                INSERT INTO capability_notes
                    (capability_type, capability_id, insight_id, note_type, note, created_by)
                VALUES (%s, %s, %s, %s, %s, 'human')
                RETURNING id
            """
            result = conn.execute(
                insert_query,
                [
                    note.capability_type,
                    note.capability_id,
                    note.insight_id,
                    note.note_type,
                    note.note,
                ],
            )
            note_id = result.fetchone()[0]
            conn.commit()

            logger.info(
                "note_created",
                note_id=note_id,
                capability_type=note.capability_type,
                capability_id=note.capability_id,
                insight_id=note.insight_id,
                note_type=note.note_type,
            )

            return NoteCreateResponse(id=note_id, message=f"Note {note_id} created successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("note_create_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create note: {e}") from e


@router.get("/notes", response_model=NotesListResponse)
async def get_notes(
    capability_type: str | None = Query(None, description="Filter by capability type"),
    capability_id: int | None = Query(None, description="Filter by capability ID"),
    insight_id: int | None = Query(None, description="Filter by insight ID"),
) -> NotesListResponse:
    """Get notes filtered by capability or insight.

    Query params:
        - capability_type: Filter by capability type (db, celery, api)
        - capability_id: Filter by capability ID
        - insight_id: Filter by insight ID
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build WHERE clause
            where_clauses = []
            params: list[Any] = []

            if capability_type:
                where_clauses.append("capability_type = %s")
                params.append(capability_type)
            if capability_id is not None:
                where_clauses.append("capability_id = %s")
                params.append(capability_id)
            if insight_id is not None:
                where_clauses.append("insight_id = %s")
                params.append(insight_id)

            where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            # Query notes
            query = f"""
                SELECT * FROM capability_notes
                {where_sql}
                ORDER BY created_at DESC
            """

            result = conn.execute(query, params)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchall()
            notes = [note_from_row(row, columns) for row in rows]

            logger.info(
                "notes_retrieved",
                capability_type=capability_type,
                capability_id=capability_id,
                insight_id=insight_id,
                count=len(notes),
            )

            return NotesListResponse(notes=notes)

    except Exception as e:
        logger.error("notes_list_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve notes: {e}") from e
