"""Vision Content router - endpoints for VISION.md narrative content.

This module provides REST API endpoints for vision content:
- GET /vision - Get all vision content (grouped by type)
- GET /vision/mission - Get mission statement
- GET /vision/narrative - Get vision narrative (what/why)
- GET /vision/principles - Get core principles
- GET /vision/success-metrics - Get success metrics
- GET /vision/roadmap - Get roadmap phases
- GET /vision/examples - Get principles in practice examples
- PATCH /vision/content/{content_key} - Update any content by key
- PATCH /vision/roadmap/{content_key} - Update roadmap phase status
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/vision", tags=["vision"])


class VisionContent(BaseModel):
    """Model for a piece of vision content."""

    id: int
    content_type: str
    content_key: str
    title: str | None = None
    content: str
    order_num: int = 0
    metadata: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None


class VisionContentUpdate(BaseModel):
    """Request model for updating vision content."""

    title: str | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None
    order_num: int | None = None


class RoadmapStatusUpdate(BaseModel):
    """Request model for updating roadmap phase status."""

    status: str  # planned, in_progress, complete
    features: list[str] | None = None  # Optional list of feature IDs


@router.get("/", response_model=dict[str, Any])
async def get_all_vision_content() -> dict[str, Any]:
    """Get all vision content grouped by type."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_type, content_key, title, content, order_num, metadata,
                       created_at, updated_at
                FROM vision_content
                ORDER BY content_type, order_num
                """
            ).fetchall()

            # Group by content_type
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                content_type = row[1]
                if content_type not in grouped:
                    grouped[content_type] = []

                grouped[content_type].append({
                    "id": row[0],
                    "content_type": row[1],
                    "content_key": row[2],
                    "title": row[3],
                    "content": row[4],
                    "order_num": row[5],
                    "metadata": row[6],
                    "created_at": row[7].isoformat() if row[7] else None,
                    "updated_at": row[8].isoformat() if row[8] else None,
                })

            return {
                "content_types": list(grouped.keys()),
                "content": grouped,
            }

    except Exception as e:
        logger.error("get_all_vision_content_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/mission", response_model=dict[str, Any])
async def get_mission_statement() -> dict[str, Any]:
    """Get the mission statement."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            row = conn.execute(
                """
                SELECT id, content_key, title, content, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'mission'
                ORDER BY order_num
                LIMIT 1
                """
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Mission statement not found")

            return {
                "id": row[0],
                "content_key": row[1],
                "title": row[2],
                "content": row[3],
                "metadata": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_mission_statement_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/narrative", response_model=dict[str, Any])
async def get_vision_narrative() -> dict[str, Any]:
    """Get the vision narrative (what we're building and why)."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_key, title, content, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'vision'
                ORDER BY order_num
                """
            ).fetchall()

            if not rows:
                raise HTTPException(status_code=404, detail="Vision narrative not found")

            return {
                "sections": [
                    {
                        "id": row[0],
                        "content_key": row[1],
                        "title": row[2],
                        "content": row[3],
                        "metadata": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "updated_at": row[6].isoformat() if row[6] else None,
                    }
                    for row in rows
                ],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_vision_narrative_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/principles", response_model=dict[str, Any])
async def get_core_principles() -> dict[str, Any]:
    """Get the 6 core principles."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_key, title, content, order_num, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'principle'
                ORDER BY order_num
                """
            ).fetchall()

            return {
                "count": len(rows),
                "principles": [
                    {
                        "id": row[0],
                        "content_key": row[1],
                        "title": row[2],
                        "content": row[3],
                        "order_num": row[4],
                        "metadata": row[5],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None,
                    }
                    for row in rows
                ],
            }

    except Exception as e:
        logger.error("get_core_principles_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/success-metrics", response_model=dict[str, Any])
async def get_success_metrics() -> dict[str, Any]:
    """Get the success metrics targets."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_key, title, content, order_num, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'success_metric'
                ORDER BY order_num
                """
            ).fetchall()

            return {
                "count": len(rows),
                "categories": [
                    {
                        "id": row[0],
                        "content_key": row[1],
                        "title": row[2],
                        "content": row[3],
                        "order_num": row[4],
                        "metrics": row[5].get("metrics", []) if row[5] else [],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None,
                    }
                    for row in rows
                ],
            }

    except Exception as e:
        logger.error("get_success_metrics_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/roadmap", response_model=dict[str, Any])
async def get_roadmap() -> dict[str, Any]:
    """Get the roadmap phases."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_key, title, content, order_num, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'roadmap_phase'
                ORDER BY order_num
                """
            ).fetchall()

            return {
                "count": len(rows),
                "phases": [
                    {
                        "id": row[0],
                        "content_key": row[1],
                        "title": row[2],
                        "content": row[3],
                        "phase_number": row[4],
                        "status": row[5].get("status", "unknown") if row[5] else "unknown",
                        "features": row[5].get("features", []) if row[5] else [],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None,
                    }
                    for row in rows
                ],
            }

    except Exception as e:
        logger.error("get_roadmap_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/examples", response_model=dict[str, Any])
async def get_principles_in_practice() -> dict[str, Any]:
    """Get the principles in practice examples."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, content_key, title, content, order_num, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'example'
                ORDER BY order_num
                """
            ).fetchall()

            return {
                "count": len(rows),
                "examples": [
                    {
                        "id": row[0],
                        "content_key": row[1],
                        "title": row[2],
                        "content": row[3],
                        "order_num": row[4],
                        "principles_applied": row[5].get("principles_applied", []) if row[5] else [],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None,
                    }
                    for row in rows
                ],
            }

    except Exception as e:
        logger.error("get_principles_in_practice_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/closing", response_model=dict[str, Any])
async def get_closing_statement() -> dict[str, Any]:
    """Get the closing/north star statement."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            row = conn.execute(
                """
                SELECT id, content_key, title, content, metadata, created_at, updated_at
                FROM vision_content
                WHERE content_type = 'closing'
                ORDER BY order_num
                LIMIT 1
                """
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Closing statement not found")

            return {
                "id": row[0],
                "content_key": row[1],
                "title": row[2],
                "content": row[3],
                "metadata": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "updated_at": row[6].isoformat() if row[6] else None,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_closing_statement_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/context", response_model=dict[str, Any])
async def get_vision_context() -> dict[str, Any]:
    """Get full vision context for slash commands.

    Returns mission, principles, and key points in a format
    optimized for AI command consumption.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get mission
            mission = conn.execute(
                """
                SELECT content FROM vision_content
                WHERE content_type = 'mission' LIMIT 1
                """
            ).fetchone()

            # Get principles
            principles = conn.execute(
                """
                SELECT title, content FROM vision_content
                WHERE content_type = 'principle'
                ORDER BY order_num
                """
            ).fetchall()

            # Get vision goals with criteria progress
            goals = conn.execute(
                """
                SELECT
                    vg.code,
                    vg.name,
                    vg.description,
                    COUNT(DISTINCT fc.feature_id) as feature_count,
                    COALESCE(SUM((
                        SELECT COUNT(*) FROM jsonb_array_elements(COALESCE(fc.acceptance_criteria, '[]')) c
                        WHERE c->>'passed' = 'true'
                    )), 0) as criteria_passed,
                    COALESCE(SUM(jsonb_array_length(COALESCE(fc.acceptance_criteria, '[]'))), 0) as criteria_total
                FROM vision_goals vg
                LEFT JOIN feature_capabilities fc ON vg.code = ANY(fc.vision_goals)
                GROUP BY vg.code, vg.name, vg.description
                ORDER BY vg.code
                """
            ).fetchall()

            return {
                "mission": mission[0] if mission else None,
                "principles": [
                    {"title": p[0], "content": p[1]}
                    for p in principles
                ],
                "goals": [
                    {
                        "code": g[0],
                        "name": g[1],
                        "description": g[2],
                        "feature_count": g[3],
                        "criteria_passed": g[4] or 0,
                        "criteria_total": g[5] or 0,
                        "progress_pct": round((g[4] or 0) / (g[5] or 1) * 100, 1),
                    }
                    for g in goals
                ],
            }

    except Exception as e:
        logger.error("get_vision_context_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Update Endpoints
# =========================================================================


@router.patch("/content/{content_key}", response_model=dict[str, Any])
async def update_vision_content(
    content_key: str, update: VisionContentUpdate
) -> dict[str, Any]:
    """Update any vision content by content_key.

    Can update title, content, metadata, or order_num.
    Only provided fields are updated.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Check content exists
            existing = conn.execute(
                "SELECT id, content_type FROM vision_content WHERE content_key = %s",
                (content_key,),
            ).fetchone()

            if not existing:
                raise HTTPException(
                    status_code=404, detail=f"Content '{content_key}' not found"
                )

            # Build dynamic update
            updates = []
            values = []

            if update.title is not None:
                updates.append("title = %s")
                values.append(update.title)
            if update.content is not None:
                updates.append("content = %s")
                values.append(update.content)
            if update.metadata is not None:
                updates.append("metadata = %s::jsonb")
                values.append(json.dumps(update.metadata))
            if update.order_num is not None:
                updates.append("order_num = %s")
                values.append(update.order_num)

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            updates.append("updated_at = NOW()")
            values.append(content_key)

            query = f"""
                UPDATE vision_content
                SET {", ".join(updates)}
                WHERE content_key = %s
                RETURNING id, content_type, content_key, title, content, order_num, metadata
            """

            result = conn.execute(query, tuple(values)).fetchone()
            conn.commit()

            logger.info(
                "vision_content_updated",
                content_key=content_key,
                content_type=existing[1],
            )

            return {
                "status": "updated",
                "id": result[0],
                "content_type": result[1],
                "content_key": result[2],
                "title": result[3],
                "content": result[4],
                "order_num": result[5],
                "metadata": result[6],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_vision_content_failed", content_key=content_key, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/roadmap/{content_key}/status", response_model=dict[str, Any])
async def update_roadmap_status(
    content_key: str, update: RoadmapStatusUpdate
) -> dict[str, Any]:
    """Update roadmap phase status and optionally link features.

    status values: planned, in_progress, complete
    features: Optional list of feature IDs to associate with this phase
    """
    valid_statuses = {"planned", "in_progress", "complete"}
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Must be one of: {valid_statuses}",
        )

    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Check roadmap phase exists
            existing = conn.execute(
                """
                SELECT id, metadata FROM vision_content
                WHERE content_key = %s AND content_type = 'roadmap_phase'
                """,
                (content_key,),
            ).fetchone()

            if not existing:
                raise HTTPException(
                    status_code=404, detail=f"Roadmap phase '{content_key}' not found"
                )

            # Merge metadata
            current_metadata = existing[1] or {}
            current_metadata["status"] = update.status
            if update.features is not None:
                current_metadata["features"] = update.features

            result = conn.execute(
                """
                UPDATE vision_content
                SET metadata = %s::jsonb, updated_at = NOW()
                WHERE content_key = %s
                RETURNING id, content_key, title, metadata
                """,
                (json.dumps(current_metadata), content_key),
            ).fetchone()
            conn.commit()

            logger.info(
                "roadmap_status_updated",
                content_key=content_key,
                status=update.status,
            )

            return {
                "status": "updated",
                "id": result[0],
                "content_key": result[1],
                "title": result[2],
                "phase_status": result[3].get("status") if result[3] else None,
                "features": result[3].get("features", []) if result[3] else [],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_roadmap_status_failed", content_key=content_key, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
