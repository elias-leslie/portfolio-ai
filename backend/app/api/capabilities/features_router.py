"""Features router - endpoints for feature capability tracking.

This module provides REST API endpoints for feature capabilities:
- GET /features - List all features with filtering
- GET /features/{feature_id} - Get single feature detail
- GET /features/summary - Get feature statistics
- POST /features - Add new feature (task_it agent)
- PATCH /features/{feature_id}/passes - Update passes status (do_it agent)

Subtask endpoints (all-in-DB approach):
- GET /features/{feature_id}/tasks - List subtasks for a feature
- POST /features/{feature_id}/tasks - Add subtask to a feature
- PATCH /features/{feature_id}/tasks/{task_id} - Toggle task completion
- DELETE /features/{feature_id}/tasks/{task_id} - Delete a subtask

Implements Anthropic's long-running agent patterns:
- Restricted modification (passes field only for do_it agent)
- All-in-DB task tracking (replaces markdown file parsing)
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...logging_config import get_logger
from ...services.capability_feature_scanner import FeatureScanner
from ...storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/features", tags=["features"])


# Pydantic models for request/response
class FeatureCreate(BaseModel):
    """Request model for creating a new feature."""

    feature_id: str | None = None  # Auto-generated if not provided
    name: str
    category: str
    description: str | None = None
    task_file: str | None = None
    task_section: str | None = None


class FeaturePassesUpdate(BaseModel):
    """Request model for updating feature passes status.

    passes can be:
    - true: Feature verified working
    - false: Feature known to be broken
    - null: Feature needs review (unverified)
    """

    passes: bool | None
    verified_by: str = "manual"


class FeatureLayersUpdate(BaseModel):
    """Request model for updating feature verification layers."""

    layers: list[str]  # e.g., ["UI", "API", "Backend", "DB", "Tasks"]


class FeatureLayerResultUpdate(BaseModel):
    """Request model for updating a single layer's verification result."""

    layer: str  # e.g., "UI", "API", "Backend", "DB", "Tasks"
    passed: bool
    evidence: str | None = None


class TaskResponse(BaseModel):
    """Response model for a single subtask."""

    id: int | None = None
    task_id: str
    description: str
    completed: bool
    order_num: int
    completed_at: str | None = None
    completed_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TaskCreate(BaseModel):
    """Request model for creating a subtask."""

    task_id: str
    description: str
    order_num: int | None = None  # Auto-calculated if not provided


class TaskToggle(BaseModel):
    """Request model for toggling task completion."""

    completed: bool
    completed_by: str = "manual"


class AcceptanceCriterion(BaseModel):
    """Model for a single acceptance criterion."""

    id: str  # e.g., "ac-001"
    criterion: str  # What needs to be true
    verification: str  # How to verify (curl command, screenshot, etc.)
    type: str  # api, ui, db, backend, quality, content
    passed: bool | None = None  # null = not checked, true/false = result


class FeatureResponse(BaseModel):
    """Response model for a single feature."""

    id: int | None = None
    feature_id: str
    name: str
    category: str | None
    description: str | None
    passes: bool | None
    layers: list[str] = []  # Verification layers: Frontend, Backend, UI, API, DB, Tasks
    layer_results: dict[str, dict] = {}  # Per-layer verification: {"UI": {"passed": true}}
    test_count: int = 0  # Number of tests covering this feature
    task_file: str | None = None  # Deprecated - for migration
    task_section: str | None = None  # Deprecated - for migration
    task_file_exists: bool = False  # Deprecated - for migration
    total_tasks: int = 0  # From DB or markdown
    completed_tasks: int = 0  # From DB or markdown
    completion_pct: int = 0
    health_status: str
    needs_review: bool
    last_verified_at: str | None = None
    verified_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    tasks: list[TaskResponse] = []  # Subtasks from DB
    # New spec-driven fields
    priority: int | None = None  # User override (1-5), null = auto
    effective_priority: int = 5  # Calculated priority (1-5)
    acceptance_criteria: list[AcceptanceCriterion] = []  # Testable criteria
    vision_goals: list[str] = []  # Links to VISION.md goals


class FeaturesListResponse(BaseModel):
    """Response model for list of features."""

    features: list[FeatureResponse]
    total: int
    filtered: int


class FeatureSummaryResponse(BaseModel):
    """Response model for feature statistics."""

    total: int
    passes_breakdown: dict[str, int]
    category_breakdown: dict[str, int]
    health_breakdown: dict[str, int]


# Helper functions
def _feature_to_response(f: dict[str, Any]) -> FeatureResponse:
    """Convert feature dict from scanner to response model."""
    # Convert task dicts to TaskResponse
    tasks = [
        TaskResponse(
            id=t.get("id"),
            task_id=t["task_id"],
            description=t["description"],
            completed=t["completed"],
            order_num=t["order_num"],
            completed_at=t["completed_at"].isoformat() if t.get("completed_at") else None,
            completed_by=t.get("completed_by"),
            created_at=t["created_at"].isoformat() if t.get("created_at") else None,
            updated_at=t["updated_at"].isoformat() if t.get("updated_at") else None,
        )
        for t in f.get("tasks", [])
    ]

    # Convert acceptance_criteria from JSONB to list of AcceptanceCriterion
    raw_criteria = f.get("acceptance_criteria", [])
    acceptance_criteria = [
        AcceptanceCriterion(
            id=c.get("id", ""),
            criterion=c.get("criterion", ""),
            verification=c.get("verification", ""),
            type=c.get("type", ""),
            passed=c.get("passed"),
        )
        for c in raw_criteria
        if isinstance(c, dict)
    ]

    return FeatureResponse(
        id=f.get("id"),
        feature_id=f["feature_id"],
        name=f["name"],
        category=f.get("category"),
        description=f.get("description"),
        passes=f.get("passes"),
        layers=f.get("layers", []),
        layer_results=f.get("layer_results", {}),
        test_count=f.get("test_count", 0),
        task_file=f.get("task_file"),
        task_section=f.get("task_section"),
        task_file_exists=f.get("task_file_exists", False),
        total_tasks=f.get("total_tasks", 0),
        completed_tasks=f.get("completed_tasks", 0),
        completion_pct=f.get("completion_pct", 0),
        health_status=f.get("health_status", "unknown"),
        needs_review=f.get("needs_review", False),
        last_verified_at=(
            f["last_verified_at"].isoformat() if f.get("last_verified_at") else None
        ),
        verified_by=f.get("verified_by"),
        created_at=f["created_at"].isoformat() if f.get("created_at") else None,
        updated_at=f["updated_at"].isoformat() if f.get("updated_at") else None,
        tasks=tasks,
        priority=f.get("priority"),
        effective_priority=f.get("effective_priority", 5),
        acceptance_criteria=acceptance_criteria,
        vision_goals=f.get("vision_goals", []),
    )


# Endpoints
@router.get("/", response_model=FeaturesListResponse)
async def get_features(
    category: str | None = Query(None, description="Filter by category"),
    passes: str | None = Query(
        None, description="Filter by passes: true, false, null (unreviewed)"
    ),
    health_status: str | None = Query(
        None, description="Filter by health: active, suspect, orphaned"
    ),
    needs_review: bool | None = Query(None, description="Filter by needs_review flag"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> FeaturesListResponse:
    """Get paginated list of features.

    Query params:
        - category: Filter by category (Dashboard, Watchlist, etc.)
        - passes: Filter by passes status (true|false|null)
        - health_status: Filter by health (active|suspect|orphaned)
        - needs_review: Filter by needs_review flag
        - limit: Results per page (default 50, max 200)
        - offset: Results offset for pagination
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        # Get all features (scanner handles validation)
        all_features = scanner.scan()

        # Apply filters
        filtered_features = all_features

        if category:
            filtered_features = [
                f for f in filtered_features if f.get("category") == category
            ]

        if passes is not None:
            if passes.lower() == "true":
                filtered_features = [
                    f for f in filtered_features if f.get("passes") is True
                ]
            elif passes.lower() == "false":
                filtered_features = [
                    f for f in filtered_features if f.get("passes") is False
                ]
            elif passes.lower() == "null":
                filtered_features = [
                    f for f in filtered_features if f.get("passes") is None
                ]

        if health_status:
            filtered_features = [
                f for f in filtered_features if f.get("health_status") == health_status
            ]

        if needs_review is not None:
            filtered_features = [
                f for f in filtered_features if f.get("needs_review") == needs_review
            ]

        # Apply pagination
        total_filtered = len(filtered_features)
        paginated = filtered_features[offset : offset + limit]

        # Convert to response format
        features_response = [
            _feature_to_response(f) for f in paginated
        ]

        return FeaturesListResponse(
            features=features_response,
            total=len(all_features),
            filtered=total_filtered,
        )

    except Exception as e:
        logger.error("get_features_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/summary", response_model=FeatureSummaryResponse)
async def get_features_summary() -> FeatureSummaryResponse:
    """Get feature statistics summary.

    Returns counts by passes status, category, and health status.
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        summary = scanner.get_summary()

        return FeatureSummaryResponse(
            total=summary["total"],
            passes_breakdown=summary["passes_breakdown"],
            category_breakdown=summary["category_breakdown"],
            health_breakdown=summary["health_breakdown"],
        )

    except Exception as e:
        logger.error("get_features_summary_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{feature_id}", response_model=FeatureResponse)
async def get_feature(feature_id: str) -> FeatureResponse:
    """Get single feature by ID.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        # Scan all features and find the one we want
        all_features = scanner.scan()
        feature = next(
            (f for f in all_features if f["feature_id"] == feature_id), None
        )

        if not feature:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

        return _feature_to_response(feature)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_feature_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/", response_model=dict[str, Any])
async def create_feature(feature: FeatureCreate) -> dict[str, Any]:
    """Create a new feature.

    This endpoint is intended for the /task_it agent to add new features.
    New features start with passes=NULL (not yet reviewed).

    Args:
        feature: Feature data (name, category, description, task_file, task_section)
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        # Auto-generate feature_id if not provided
        feature_id = feature.feature_id or scanner.get_next_feature_id()

        success = scanner.add_feature(
            feature_id=feature_id,
            name=feature.name,
            category=feature.category,
            description=feature.description,
            task_file=feature.task_file,
            task_section=feature.task_section,
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to create feature")

        logger.info(
            "feature_created",
            feature_id=feature_id,
            name=feature.name,
            category=feature.category,
        )

        return {
            "status": "created",
            "feature_id": feature_id,
            "name": feature.name,
            "category": feature.category,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_feature_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{feature_id}/passes", response_model=dict[str, Any])
async def update_feature_passes(
    feature_id: str, update: FeaturePassesUpdate
) -> dict[str, Any]:
    """Update the passes status for a feature.

    This endpoint is intended for the /do_it agent to verify features.
    This is the ONLY field that can be modified after creation.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New passes value and verified_by
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        success = scanner.update_passes(
            feature_id=feature_id,
            passes=update.passes,
            verified_by=update.verified_by,
        )

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Feature {feature_id} not found"
            )

        logger.info(
            "feature_passes_updated",
            feature_id=feature_id,
            passes=update.passes,
            verified_by=update.verified_by,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "passes": update.passes,
            "verified_by": update.verified_by,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_passes_failed", feature_id=feature_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{feature_id}/layers", response_model=dict[str, Any])
async def update_feature_layers(
    feature_id: str, update: FeatureLayersUpdate
) -> dict[str, Any]:
    """Update the verification layers for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New layers list
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET layers = %s, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id
                """,
                (update.layers, feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

        logger.info(
            "feature_layers_updated",
            feature_id=feature_id,
            layers=update.layers,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "layers": update.layers,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_layers_failed", feature_id=feature_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{feature_id}/layer-result", response_model=dict[str, Any])
async def update_feature_layer_result(
    feature_id: str, update: FeatureLayerResultUpdate
) -> dict[str, Any]:
    """Update a single layer's verification result.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: Layer name, passed status, and evidence
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Update the specific layer in layer_results JSONB
            layer_data = json.dumps(
                {update.layer: {"passed": update.passed, "evidence": update.evidence}}
            )
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET layer_results = layer_results || %s::jsonb,
                    updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id, layer_results
                """,
                (layer_data, feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

        logger.info(
            "feature_layer_result_updated",
            feature_id=feature_id,
            layer=update.layer,
            passed=update.passed,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "layer": update.layer,
            "passed": update.passed,
            "evidence": update.evidence,
            "layer_results": result[1],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_layer_result_failed", feature_id=feature_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


class FeatureTestCountUpdate(BaseModel):
    """Request model for updating feature test count."""

    test_count: int  # Number of tests covering this feature


@router.patch("/{feature_id}/test-count", response_model=dict[str, Any])
async def update_feature_test_count(
    feature_id: str, update: FeatureTestCountUpdate
) -> dict[str, Any]:
    """Update the test count for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New test count
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET test_count = %s, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id, test_count
                """,
                (update.test_count, feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

        logger.info(
            "feature_test_count_updated",
            feature_id=feature_id,
            test_count=update.test_count,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "test_count": update.test_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_test_count_failed", feature_id=feature_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Spec-Driven Endpoints (priority, acceptance criteria, vision goals)
# =========================================================================


class FeaturePriorityUpdate(BaseModel):
    """Request model for updating feature priority."""

    priority: int | None  # 1-5 for user override, null to auto-calculate


@router.patch("/{feature_id}/priority", response_model=dict[str, Any])
async def update_feature_priority(
    feature_id: str, update: FeaturePriorityUpdate
) -> dict[str, Any]:
    """Update the priority for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New priority (1-5) or null for auto-calculate
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET priority = %s, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id, priority
                """,
                (update.priority, feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

        logger.info(
            "feature_priority_updated",
            feature_id=feature_id,
            priority=update.priority,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "priority": update.priority,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_priority_failed", feature_id=feature_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


class AcceptanceCriteriaUpdate(BaseModel):
    """Request model for updating acceptance criteria."""

    acceptance_criteria: list[dict[str, Any]]  # Full replacement of criteria array


@router.patch("/{feature_id}/acceptance-criteria", response_model=dict[str, Any])
async def update_feature_acceptance_criteria(
    feature_id: str, update: AcceptanceCriteriaUpdate
) -> dict[str, Any]:
    """Update the acceptance criteria for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New acceptance criteria array
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET acceptance_criteria = %s::jsonb, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id, acceptance_criteria
                """,
                (json.dumps(update.acceptance_criteria), feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

        logger.info(
            "feature_acceptance_criteria_updated",
            feature_id=feature_id,
            criteria_count=len(update.acceptance_criteria),
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "acceptance_criteria": result[1],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_acceptance_criteria_failed",
            feature_id=feature_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


class AcceptanceCriterionPassedUpdate(BaseModel):
    """Request model for updating a single criterion's passed status."""

    passed: bool | None  # true, false, or null to reset
    evidence: str | None = None  # Evidence for the pass/fail decision


@router.patch(
    "/{feature_id}/acceptance-criteria/{criterion_id}", response_model=dict[str, Any]
)
async def update_acceptance_criterion_passed(
    feature_id: str, criterion_id: str, update: AcceptanceCriterionPassedUpdate
) -> dict[str, Any]:
    """Update the passed status of a single acceptance criterion.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        criterion_id: Criterion ID within the feature (e.g., ac-001)
        update: New passed status and optional evidence
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get current acceptance_criteria
            row = conn.execute(
                """
                SELECT acceptance_criteria
                FROM feature_capabilities
                WHERE feature_id = %s
                """,
                (feature_id,),
            ).fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

            criteria = row[0] if row[0] else []

            # Find and update the specific criterion
            found = False
            for c in criteria:
                if c.get("id") == criterion_id:
                    c["passed"] = update.passed
                    if update.evidence:
                        c["evidence"] = update.evidence
                    found = True
                    break

            if not found:
                raise HTTPException(
                    status_code=404,
                    detail=f"Criterion {criterion_id} not found in feature {feature_id}",
                )

            # Update the database
            conn.execute(
                """
                UPDATE feature_capabilities
                SET acceptance_criteria = %s::jsonb, updated_at = NOW()
                WHERE feature_id = %s
                """,
                (json.dumps(criteria), feature_id),
            )
            conn.commit()

        logger.info(
            "acceptance_criterion_passed_updated",
            feature_id=feature_id,
            criterion_id=criterion_id,
            passed=update.passed,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "criterion_id": criterion_id,
            "passed": update.passed,
            "evidence": update.evidence,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_acceptance_criterion_passed_failed",
            feature_id=feature_id,
            criterion_id=criterion_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


class VisionGoalsUpdate(BaseModel):
    """Request model for updating vision goals."""

    vision_goals: list[str]  # List of VISION.md goal identifiers


@router.patch("/{feature_id}/vision-goals", response_model=dict[str, Any])
async def update_feature_vision_goals(
    feature_id: str, update: VisionGoalsUpdate
) -> dict[str, Any]:
    """Update the vision goals for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New vision goals list
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET vision_goals = %s, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id, vision_goals
                """,
                (update.vision_goals, feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Feature {feature_id} not found"
                )

        logger.info(
            "feature_vision_goals_updated",
            feature_id=feature_id,
            vision_goals=update.vision_goals,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "vision_goals": result[1],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_feature_vision_goals_failed", feature_id=feature_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Subtask Endpoints (all-in-DB approach)
# =========================================================================


@router.get("/{feature_id}/tasks", response_model=list[TaskResponse])
async def get_feature_tasks(feature_id: str) -> list[TaskResponse]:
    """Get all subtasks for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        tasks = scanner.get_tasks(feature_id)

        return [
            TaskResponse(
                id=t.get("id"),
                task_id=t["task_id"],
                description=t["description"],
                completed=t["completed"],
                order_num=t["order_num"],
                completed_at=t["completed_at"].isoformat() if t.get("completed_at") else None,
                completed_by=t.get("completed_by"),
                created_at=t["created_at"].isoformat() if t.get("created_at") else None,
                updated_at=t["updated_at"].isoformat() if t.get("updated_at") else None,
            )
            for t in tasks
        ]

    except Exception as e:
        logger.error("get_feature_tasks_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{feature_id}/tasks", response_model=dict[str, Any])
async def create_feature_task(feature_id: str, task: TaskCreate) -> dict[str, Any]:
    """Add a subtask to a feature.

    This endpoint is intended for the /task_it agent to define work items.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        task: Task data (task_id, description, order_num)
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        success = scanner.add_task(
            feature_id=feature_id,
            task_id=task.task_id,
            description=task.description,
            order_num=task.order_num,
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create task. Feature {feature_id} may not exist.",
            )

        logger.info(
            "task_created",
            feature_id=feature_id,
            task_id=task.task_id,
        )

        return {
            "status": "created",
            "feature_id": feature_id,
            "task_id": task.task_id,
            "description": task.description,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "create_task_failed",
            feature_id=feature_id,
            task_id=task.task_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{feature_id}/tasks/{task_id}", response_model=dict[str, Any])
async def toggle_feature_task(
    feature_id: str, task_id: str, toggle: TaskToggle
) -> dict[str, Any]:
    """Toggle completion status of a subtask.

    This endpoint is intended for the /do_it agent to track progress.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        task_id: Task ID within feature (e.g., 1.1)
        toggle: New completion status and completed_by
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        success = scanner.toggle_task(
            feature_id=feature_id,
            task_id=task_id,
            completed=toggle.completed,
            completed_by=toggle.completed_by,
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found for feature {feature_id}",
            )

        logger.info(
            "task_toggled",
            feature_id=feature_id,
            task_id=task_id,
            completed=toggle.completed,
        )

        return {
            "status": "updated",
            "feature_id": feature_id,
            "task_id": task_id,
            "completed": toggle.completed,
            "completed_by": toggle.completed_by,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "toggle_task_failed",
            feature_id=feature_id,
            task_id=task_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{feature_id}/tasks/{task_id}", response_model=dict[str, Any])
async def delete_feature_task(feature_id: str, task_id: str) -> dict[str, Any]:
    """Delete a subtask from a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        task_id: Task ID within feature (e.g., 1.1)
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        success = scanner.delete_task(feature_id=feature_id, task_id=task_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found for feature {feature_id}",
            )

        logger.info("task_deleted", feature_id=feature_id, task_id=task_id)

        return {
            "status": "deleted",
            "feature_id": feature_id,
            "task_id": task_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_task_failed",
            feature_id=feature_id,
            task_id=task_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e)) from e
