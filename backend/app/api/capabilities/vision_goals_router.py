"""Vision Goals router - endpoints for vision goals management.

This module provides REST API endpoints for vision goals:
- GET /vision-goals - List all goals with feature counts
- GET /vision-goals/{code} - Get single goal with linked features
- GET /vision-goals/summary - Get summary stats per goal
- POST /vision-goals - Create new goal
- PATCH /vision-goals/{code} - Update goal
- DELETE /vision-goals/{code} - Delete goal (if no features linked)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/vision-goals", tags=["vision-goals"])


class VisionGoal(BaseModel):
    """Model for a vision goal."""

    code: str  # VG-INTEL, VG-AUTO, etc.
    name: str
    description: str | None = None
    category: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class VisionGoalWithStats(VisionGoal):
    """Vision goal with linked feature statistics."""

    feature_count: int = 0
    criteria_passed: int = 0
    criteria_total: int = 0
    pass_rate: float = 0.0


class VisionGoalCreate(BaseModel):
    """Request model for creating a vision goal."""

    code: str
    name: str
    description: str | None = None
    category: str | None = None


class VisionGoalUpdate(BaseModel):
    """Request model for updating a vision goal."""

    name: str | None = None
    description: str | None = None
    category: str | None = None


@router.get("/", response_model=list[VisionGoalWithStats])
async def get_vision_goals() -> list[VisionGoalWithStats]:
    """Get all vision goals with feature and criteria statistics."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get all vision goals
            goals = conn.execute(
                """
                SELECT code, name, description, category, created_at, updated_at
                FROM vision_goals
                ORDER BY code
                """
            ).fetchall()

            # Get feature counts and criteria stats per goal
            stats = conn.execute(
                """
                SELECT
                    unnest(vision_goals) as goal_code,
                    COUNT(DISTINCT feature_id) as feature_count,
                    SUM(jsonb_array_length(COALESCE(acceptance_criteria, '[]'))) as criteria_total,
                    SUM((
                        SELECT COUNT(*)
                        FROM jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                        WHERE c->>'passed' = 'true'
                    )) as criteria_passed
                FROM feature_capabilities
                WHERE vision_goals IS NOT NULL AND array_length(vision_goals, 1) > 0
                GROUP BY goal_code
                """
            ).fetchall()

            # Build stats lookup
            stats_map = {
                row[0]: {
                    "feature_count": row[1],
                    "criteria_total": row[2] or 0,
                    "criteria_passed": row[3] or 0,
                }
                for row in stats
            }

            result = []
            for g in goals:
                code = g[0]
                s = stats_map.get(code, {"feature_count": 0, "criteria_total": 0, "criteria_passed": 0})
                pass_rate = s["criteria_passed"] / s["criteria_total"] if s["criteria_total"] > 0 else 0.0
                result.append(
                    VisionGoalWithStats(
                        code=code,
                        name=g[1],
                        description=g[2],
                        category=g[3],
                        created_at=g[4].isoformat() if g[4] else None,
                        updated_at=g[5].isoformat() if g[5] else None,
                        feature_count=s["feature_count"],
                        criteria_total=s["criteria_total"],
                        criteria_passed=s["criteria_passed"],
                        pass_rate=round(pass_rate, 3),
                    )
                )

            return result

    except Exception as e:
        logger.error("get_vision_goals_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/summary", response_model=dict[str, Any])
async def get_vision_goals_summary() -> dict[str, Any]:
    """Get summary statistics for all vision goals."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get goal count
            goal_count = conn.execute("SELECT COUNT(*) FROM vision_goals").fetchone()[0]

            # Get per-goal stats
            stats = conn.execute(
                """
                SELECT
                    vg.code,
                    vg.name,
                    COUNT(DISTINCT fc.feature_id) as feature_count,
                    COALESCE(SUM(jsonb_array_length(COALESCE(fc.acceptance_criteria, '[]'))), 0) as criteria_total,
                    COALESCE(SUM((
                        SELECT COUNT(*)
                        FROM jsonb_array_elements(COALESCE(fc.acceptance_criteria, '[]')) c
                        WHERE c->>'passed' = 'true'
                    )), 0) as criteria_passed
                FROM vision_goals vg
                LEFT JOIN feature_capabilities fc ON vg.code = ANY(fc.vision_goals)
                GROUP BY vg.code, vg.name
                ORDER BY vg.code
                """
            ).fetchall()

            goals = []
            for row in stats:
                criteria_total = row[3] or 0
                criteria_passed = row[4] or 0
                pass_rate = criteria_passed / criteria_total if criteria_total > 0 else 0.0
                goals.append({
                    "code": row[0],
                    "name": row[1],
                    "feature_count": row[2],
                    "criteria_total": criteria_total,
                    "criteria_passed": criteria_passed,
                    "pass_rate": round(pass_rate, 3),
                })

            return {
                "total_goals": goal_count,
                "goals": goals,
            }

    except Exception as e:
        logger.error("get_vision_goals_summary_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{code}", response_model=dict[str, Any])
async def get_vision_goal(code: str) -> dict[str, Any]:
    """Get a single vision goal with linked features."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get the goal
            goal = conn.execute(
                """
                SELECT code, name, description, category, created_at, updated_at
                FROM vision_goals
                WHERE code = %s
                """,
                (code,),
            ).fetchone()

            if not goal:
                raise HTTPException(status_code=404, detail=f"Vision goal {code} not found")

            # Get linked features
            features = conn.execute(
                """
                SELECT
                    feature_id,
                    name,
                    passes,
                    jsonb_array_length(COALESCE(acceptance_criteria, '[]')) as criteria_total,
                    (
                        SELECT COUNT(*)
                        FROM jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                        WHERE c->>'passed' = 'true'
                    ) as criteria_passed
                FROM feature_capabilities
                WHERE %s = ANY(vision_goals)
                ORDER BY feature_id
                """,
                (code,),
            ).fetchall()

            return {
                "code": goal[0],
                "name": goal[1],
                "description": goal[2],
                "category": goal[3],
                "created_at": goal[4].isoformat() if goal[4] else None,
                "updated_at": goal[5].isoformat() if goal[5] else None,
                "feature_count": len(features),
                "features": [
                    {
                        "feature_id": f[0],
                        "name": f[1],
                        "passes": f[2],
                        "criteria_total": f[3],
                        "criteria_passed": f[4],
                    }
                    for f in features
                ],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_vision_goal_failed", code=code, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/", response_model=dict[str, Any])
async def create_vision_goal(goal: VisionGoalCreate) -> dict[str, Any]:
    """Create a new vision goal."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                INSERT INTO vision_goals (code, name, description, category)
                VALUES (%s, %s, %s, %s)
                RETURNING code, name, description, category
                """,
                (goal.code, goal.name, goal.description, goal.category),
            ).fetchone()
            conn.commit()

            logger.info("vision_goal_created", code=goal.code, name=goal.name)

            return {
                "status": "created",
                "code": result[0],
                "name": result[1],
                "description": result[2],
                "category": result[3],
            }

    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Vision goal {goal.code} already exists") from e
        logger.error("create_vision_goal_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{code}", response_model=dict[str, Any])
async def update_vision_goal(code: str, update: VisionGoalUpdate) -> dict[str, Any]:
    """Update a vision goal."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build update query dynamically
            updates = []
            values = []
            if update.name is not None:
                updates.append("name = %s")
                values.append(update.name)
            if update.description is not None:
                updates.append("description = %s")
                values.append(update.description)
            if update.category is not None:
                updates.append("category = %s")
                values.append(update.category)

            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            updates.append("updated_at = NOW()")
            values.append(code)

            query = f"""
                UPDATE vision_goals
                SET {", ".join(updates)}
                WHERE code = %s
                RETURNING code, name, description, category
            """

            result = conn.execute(query, tuple(values)).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(status_code=404, detail=f"Vision goal {code} not found")

            logger.info("vision_goal_updated", code=code)

            return {
                "status": "updated",
                "code": result[0],
                "name": result[1],
                "description": result[2],
                "category": result[3],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_vision_goal_failed", code=code, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{code}", response_model=dict[str, Any])
async def delete_vision_goal(code: str) -> dict[str, Any]:
    """Delete a vision goal (only if no features are linked)."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Check if any features are linked
            linked_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM feature_capabilities
                WHERE %s = ANY(vision_goals)
                """,
                (code,),
            ).fetchone()[0]

            if linked_count > 0:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot delete: {linked_count} features are linked to {code}",
                )

            result = conn.execute(
                """
                DELETE FROM vision_goals
                WHERE code = %s
                RETURNING code
                """,
                (code,),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(status_code=404, detail=f"Vision goal {code} not found")

            logger.info("vision_goal_deleted", code=code)

            return {"status": "deleted", "code": code}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_vision_goal_failed", code=code, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
