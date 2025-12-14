"""Features router - endpoints for feature capability tracking.

This module provides REST API endpoints for feature capabilities:
- GET /features - List all features with filtering
- GET /features/{feature_id} - Get single feature detail
- GET /features/summary - Get feature statistics
- POST /features - Add new feature (task_it agent)
- DELETE /features/{feature_id} - Delete a feature and its subtasks
- PATCH /features/{feature_id}/verified - Mark verification timestamp
- PATCH /features/{feature_id}/status - Update work status
- PATCH /features/{feature_id}/effort - Update effort estimate
- PATCH /features/{feature_id}/priority - Update priority
- PATCH /features/{feature_id}/layers - Update verification layers
- PATCH /features/{feature_id}/implementation-notes - Update implementation notes
- PATCH /features/{feature_id}/acceptance-criteria - Update acceptance criteria

Subtask endpoints (all-in-DB approach):
- GET /features/{feature_id}/tasks - List subtasks for a feature
- POST /features/{feature_id}/tasks - Add subtask to a feature
- PATCH /features/{feature_id}/tasks/{task_id} - Toggle task completion
- PUT /features/{feature_id}/tasks/{task_id} - Update task details
- DELETE /features/{feature_id}/tasks/{task_id} - Delete a subtask

Dependency endpoints:
- GET /features/{feature_id}/dependencies - List feature dependencies
- POST /features/{feature_id}/dependencies - Add dependency
- DELETE /features/{feature_id}/dependencies/{depends_on_feature_id} - Remove dependency

Vision goal endpoints:
- PATCH /features/{feature_id}/vision-goals - Update vision goals

Verification endpoints:
- POST /features/verify-all - Run verification on all automatable criteria
- POST /features/verify-batch - Verify a batch of criteria
- POST /features/{feature_id}/verify - Queue verification for a feature
- GET /features/verification-summary - Get verification statistics
- GET /features/criteria/failing - List failing criteria
- GET /features/criteria/pending - List pending criteria

Implements Anthropic's long-running agent patterns:
- Verification status calculated dynamically (tasks=0 AND all criteria passed)
- All-in-DB task tracking (replaces markdown file parsing)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

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


class QuickFeatureCreate(BaseModel):
    """Request model for creating a quick debug feature from Agent Hub."""

    url: str  # The page URL being captured
    description: str | None = None  # Optional description

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        from urllib.parse import urlparse  # noqa: PLC0415

        if not v:
            raise ValueError("URL is required")
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must be http or https")
        return v


class FeatureLayersUpdate(BaseModel):
    """Request model for updating feature verification layers."""

    layers: list[str]  # e.g., ["UI", "API", "Backend", "DB", "Tasks"]


class FeatureLayerResultUpdate(BaseModel):
    """Request model for updating a single layer's verification result."""

    layer: str  # e.g., "UI", "API", "Backend", "DB", "Tasks"
    passed: bool
    evidence: str | None = None


# Task models REMOVED - use Beads CLI for task management.
# All task tracking now via: bd ready, bd create, bd update, bd close


class AcceptanceCriterion(BaseModel):
    """Model for a single acceptance criterion."""

    id: str  # e.g., "ac-001"
    criterion: str  # What needs to be true
    verification: str  # How to verify (curl command, screenshot, etc.)
    type: str  # api, ui, db, backend, quality, content
    passed: bool | None = None  # null = not checked, true/false = result
    # Verification tracking fields (added for auto-verification)
    verified_at: str | None = None  # ISO timestamp of last verification
    verification_output: str | None = None  # Actual output (truncated)


class FeatureResponse(BaseModel):
    """Response model for a single feature."""

    id: int | None = None
    feature_id: str
    name: str
    category: str | None
    description: str | None
    layers: list[str] = []  # Verification layers: Frontend, Backend, UI, API, DB, Tasks
    layer_results: dict[
        str, dict[str, Any]
    ] = {}  # Per-layer verification: {"UI": {"passed": true}}
    total_tasks: int = 0  # From DB
    completed_tasks: int = 0  # From DB
    completion_pct: int = 0
    health_status: str  # active or orphaned (based on tasks)
    last_verified_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    # tasks field removed - use Beads CLI (bd ready, bd list)
    # Spec-driven fields
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
    category_breakdown: dict[str, int]
    health_breakdown: dict[str, int]


# Helper functions
def _feature_to_response(f: dict[str, Any]) -> FeatureResponse:
    """Convert feature dict from scanner to response model."""
    # Tasks removed - use Beads CLI (bd ready, bd list)

    # Convert acceptance_criteria from JSONB to list of AcceptanceCriterion
    raw_criteria = f.get("acceptance_criteria", [])
    acceptance_criteria = [
        AcceptanceCriterion(
            id=c.get("id", ""),
            criterion=c.get("criterion", ""),
            verification=c.get("verification", ""),
            type=c.get("type", ""),
            passed=c.get("passed"),
            verified_at=c.get("verified_at"),
            verification_output=c.get("verification_output"),
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
        layers=f.get("layers", []),
        layer_results=f.get("layer_results", {}),
        total_tasks=f.get("total_tasks", 0),
        completed_tasks=f.get("completed_tasks", 0),
        completion_pct=f.get("completion_pct", 0),
        health_status=f.get("health_status", "unknown"),
        last_verified_at=(f["last_verified_at"].isoformat() if f.get("last_verified_at") else None),
        created_at=f["created_at"].isoformat() if f.get("created_at") else None,
        updated_at=f["updated_at"].isoformat() if f.get("updated_at") else None,
        priority=f.get("priority"),
        effective_priority=f.get("effective_priority", 5),
        acceptance_criteria=acceptance_criteria,
        vision_goals=f.get("vision_goals", []),
    )


# Endpoints
@router.get("/", response_model=FeaturesListResponse)
async def get_features(
    category: str | None = Query(None, description="Filter by category"),
    health_status: str | None = Query(None, description="Filter by health: active, orphaned"),
    limit: int = Query(50, ge=1, le=500, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> FeaturesListResponse:
    """Get paginated list of features.

    Query params:
        - category: Filter by category (Dashboard, Watchlist, etc.)
        - health_status: Filter by health (active|orphaned)
        - limit: Results per page (default 50, max 500)
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
            filtered_features = [f for f in filtered_features if f.get("category") == category]

        if health_status:
            filtered_features = [
                f for f in filtered_features if f.get("health_status") == health_status
            ]

        # Apply pagination
        total_filtered = len(filtered_features)
        paginated = filtered_features[offset : offset + limit]

        # Convert to response format
        features_response = [_feature_to_response(f) for f in paginated]

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

    Returns counts by category and health status.
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        summary = scanner.get_summary()

        return FeatureSummaryResponse(
            total=summary["total"],
            category_breakdown=summary["category_breakdown"],
            health_breakdown=summary["health_breakdown"],
        )

    except Exception as e:
        logger.error("get_features_summary_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Verification Summary Endpoints (MUST come before /{feature_id} routes)
# =========================================================================


class VerificationSummary(BaseModel):
    """Response model for verification summary."""

    total_criteria: int
    passed: int
    failed: int
    pending: int
    by_type: dict[str, dict[str, int]]
    last_run_at: str | None


@router.get("/verification-summary", response_model=VerificationSummary)
async def get_verification_summary() -> VerificationSummary:
    """Get summary statistics for acceptance criteria verification."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get all criteria counts
            row = conn.execute(
                """
                SELECT
                    SUM(jsonb_array_length(COALESCE(acceptance_criteria, '[]'))) as total,
                    SUM((
                        SELECT COUNT(*)
                        FROM jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                        WHERE c->>'passed' = 'true'
                    )) as passed,
                    SUM((
                        SELECT COUNT(*)
                        FROM jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                        WHERE c->>'passed' = 'false'
                    )) as failed
                FROM feature_capabilities
                """
            ).fetchone()

            total_val: int = int(row[0]) if row and row[0] else 0
            passed_val: int = int(row[1]) if row and row[1] else 0
            failed_val: int = int(row[2]) if row and row[2] else 0
            pending_val: int = total_val - passed_val - failed_val

            # Get by-type breakdown
            type_rows = conn.execute(
                """
                SELECT
                    c->>'type' as type,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE c->>'passed' = 'true') as passed,
                    COUNT(*) FILTER (WHERE c->>'passed' = 'false') as failed
                FROM feature_capabilities,
                     jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                GROUP BY c->>'type'
                """
            ).fetchall()

            by_type: dict[str, dict[str, int]] = {}
            for r in type_rows:
                ctype = str(r[0]) if r[0] else "unknown"
                type_total = int(r[1]) if r[1] else 0
                type_passed = int(r[2]) if r[2] else 0
                type_failed = int(r[3]) if r[3] else 0
                by_type[ctype] = {
                    "total": type_total,
                    "passed": type_passed,
                    "failed": type_failed,
                    "pending": type_total - type_passed - type_failed,
                }

            # Get last run timestamp
            last_run_at: str | None
            try:
                last_run = conn.execute(
                    """
                    SELECT run_at
                    FROM criteria_verification_runs
                    ORDER BY run_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                if last_run and last_run[0]:
                    run_at_val = last_run[0]
                    if isinstance(run_at_val, datetime):
                        last_run_at = run_at_val.isoformat()
                    else:
                        last_run_at = None
                else:
                    last_run_at = None
            except Exception:
                last_run_at = None

            return VerificationSummary(
                total_criteria=total_val,
                passed=passed_val,
                failed=failed_val,
                pending=pending_val,
                by_type=by_type,
                last_run_at=last_run_at,
            )

    except Exception as e:
        logger.error("get_verification_summary_failed", error=str(e))
        return VerificationSummary(
            total_criteria=0,
            passed=0,
            failed=0,
            pending=0,
            by_type={},
            last_run_at=None,
        )


@router.get("/criteria/failing", response_model=list[dict[str, Any]])
async def get_failing_criteria() -> list[dict[str, Any]]:
    """Get all failing acceptance criteria for quick triage."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    fc.feature_id,
                    fc.name as feature_name,
                    c->>'id' as criterion_id,
                    c->>'criterion' as criterion,
                    c->>'verification' as verification,
                    c->>'verification_output' as verification_output,
                    c->>'verified_at' as verified_at
                FROM feature_capabilities fc,
                     jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                WHERE c->>'passed' = 'false'
                ORDER BY c->>'verified_at' DESC NULLS LAST
                LIMIT 100
                """
            ).fetchall()

            return [
                {
                    "feature_id": r[0],
                    "feature_name": r[1],
                    "criterion_id": r[2],
                    "criterion": r[3],
                    "verification": r[4],
                    "verification_output": r[5],
                    "failed_at": r[6],
                }
                for r in rows
            ]

    except Exception as e:
        logger.error("get_failing_criteria_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/criteria/pending", response_model=list[dict[str, Any]])
async def get_pending_criteria(
    type_filter: str | None = Query(None, alias="type", description="Filter by type"),
) -> list[dict[str, Any]]:
    """Get all pending (unverified) acceptance criteria."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            if type_filter:
                rows = conn.execute(
                    """
                    SELECT
                        fc.feature_id,
                        c->>'id' as criterion_id,
                        c->>'criterion' as criterion,
                        c->>'verification' as verification,
                        c->>'type' as type
                    FROM feature_capabilities fc,
                         jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                    WHERE c->>'passed' IS NULL
                      AND c->>'type' = %s
                    ORDER BY fc.feature_id, c->>'id'
                    LIMIT 100
                    """,
                    (type_filter,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        fc.feature_id,
                        c->>'id' as criterion_id,
                        c->>'criterion' as criterion,
                        c->>'verification' as verification,
                        c->>'type' as type
                    FROM feature_capabilities fc,
                         jsonb_array_elements(COALESCE(acceptance_criteria, '[]')) c
                    WHERE c->>'passed' IS NULL
                    ORDER BY fc.feature_id, c->>'id'
                    LIMIT 100
                    """
                ).fetchall()

            return [
                {
                    "feature_id": r[0],
                    "criterion_id": r[1],
                    "criterion": r[2],
                    "verification": r[3],
                    "type": r[4],
                }
                for r in rows
            ]

    except Exception as e:
        logger.error("get_pending_criteria_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/verify-all", response_model=dict[str, Any])
async def verify_all_features(
    type_filter: str | None = Query(None, description="Filter by type: api, test, ui"),
    limit: int | None = Query(None, description="Limit number of criteria to verify"),
) -> dict[str, Any]:
    """Trigger verification of all auto-verifiable criteria.

    This queues the verification as a Celery task and returns immediately.
    """
    from ...tasks.verify_criteria import verify_all_acceptance_criteria  # noqa: PLC0415

    try:
        task = verify_all_acceptance_criteria.delay(type_filter=type_filter, limit=limit)
        logger.info(
            "bulk_verification_queued", task_id=task.id, type_filter=type_filter, limit=limit
        )
        return {"status": "queued", "task_id": task.id, "type_filter": type_filter, "limit": limit}
    except Exception as e:
        logger.error("queue_bulk_verification_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/verify-batch", response_model=dict[str, Any])
async def verify_batch(feature_ids: list[str]) -> dict[str, Any]:
    """Trigger verification for multiple features."""
    from ...tasks.verify_criteria import verify_criteria_batch  # noqa: PLC0415

    try:
        task = verify_criteria_batch.delay(feature_ids)
        logger.info("batch_verification_queued", task_id=task.id, feature_count=len(feature_ids))
        return {
            "status": "queued",
            "task_id": task.id,
            "feature_ids": feature_ids,
            "estimated_seconds": len(feature_ids) * 5,
        }
    except Exception as e:
        logger.error("queue_batch_verification_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Feature Detail and Update Endpoints
# =========================================================================


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
        feature = next((f for f in all_features if f["feature_id"] == feature_id), None)

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
    New features start with no tasks (needs setup).

    Args:
        feature: Feature data (name, category, description)
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


@router.post("/quick", response_model=dict[str, Any])
async def create_quick_feature(request: QuickFeatureCreate) -> dict[str, Any]:
    """Create a quick debug feature for Agent Hub evidence capture.

    This endpoint auto-creates a feature with:
    - ID: FEAT-DEBUG-YYYYMMDD-HHMMSS
    - Category: Debug
    - Single acceptance criterion: "Evidence capture from {url}"

    Args:
        request: URL and optional description

    Returns:
        feature_id, criterion_id, and name for immediate use
    """
    import json  # noqa: PLC0415

    conn_mgr = get_connection_manager()

    try:
        # Generate timestamp-based feature ID (short format to fit varchar(20))
        now = datetime.now()
        feature_id = f"DBG-{now.strftime('%m%d-%H%M%S')}"

        # Extract path from URL for display name
        from urllib.parse import urlparse  # noqa: PLC0415

        parsed = urlparse(request.url)
        path = parsed.path or "/"
        name = f"Debug: {path}"

        # Create single acceptance criterion
        criterion_id = "ac-001"
        acceptance_criteria = [
            {
                "id": criterion_id,
                "criterion": f"Evidence capture from {path}",
                "verification": f"screenshot {path}",
                "type": "ui",
                "passed": None,
            }
        ]

        description = (
            request.description or f"Quick debug feature created from Agent Hub for {path}"
        )

        with conn_mgr.connection() as conn:
            conn.execute(
                """
                INSERT INTO feature_capabilities
                    (feature_id, name, category, description, acceptance_criteria, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                """,
                (feature_id, name, "Debug", description, json.dumps(acceptance_criteria)),
            )
            conn.commit()

        logger.info(
            "quick_feature_created",
            feature_id=feature_id,
            url=request.url,
        )

        return {
            "feature_id": feature_id,
            "criterion_id": criterion_id,
            "name": name,
            "created": True,
        }

    except Exception as e:
        logger.error("create_quick_feature_failed", error=str(e), url=request.url)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{feature_id}", response_model=dict[str, Any])
async def delete_feature(feature_id: str) -> dict[str, Any]:
    """Delete a feature and all its associated data.

    This permanently removes:
    - The feature record
    - All subtasks (feature_tasks)
    - All dependencies (feature_dependencies)
    - All vision goal mappings (feature_vision_goal_mappings)

    Args:
        feature_id: Feature ID to delete (e.g., FEAT-001)

    Returns:
        Confirmation of deletion with feature_id

    Warning:
        This action is irreversible. Use with caution.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Check feature exists
            feature_check = conn.execute(
                "SELECT id, name FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()

            if not feature_check:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            feature_db_id = feature_check[0]
            feature_name = feature_check[1]

            # Delete in correct order due to FK constraints
            # 1. Delete subtasks
            conn.execute(
                "DELETE FROM feature_tasks WHERE feature_id = %s",
                (feature_db_id,),
            )

            # 2. Delete dependencies (both directions)
            conn.execute(
                "DELETE FROM feature_dependencies WHERE feature_id = %s OR depends_on_id = %s",
                (feature_db_id, feature_db_id),
            )

            # 3. Delete vision goal mappings
            conn.execute(
                "DELETE FROM feature_vision_goal_mappings WHERE feature_id = %s",
                (feature_db_id,),
            )

            # 4. Delete the feature itself
            conn.execute(
                "DELETE FROM feature_capabilities WHERE id = %s",
                (feature_db_id,),
            )

            conn.commit()

        logger.info(
            "feature_deleted",
            feature_id=feature_id,
            name=feature_name,
        )

        return {
            "status": "deleted",
            "feature_id": feature_id,
            "name": feature_name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_feature_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{feature_id}/verified", response_model=dict[str, Any])
async def mark_feature_verified(feature_id: str) -> dict[str, Any]:
    """Mark feature verification timestamp.

    This endpoint should be called by /verify_it at the end of verification.
    Updates last_verified_at to track when verification last ran.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
    """
    conn_mgr = get_connection_manager()
    scanner = FeatureScanner(conn_mgr)

    try:
        success = scanner.update_last_verified(feature_id=feature_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

        logger.info(
            "feature_marked_verified",
            feature_id=feature_id,
        )

        return {
            "status": "verified",
            "feature_id": feature_id,
            "last_verified_at": "now",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_feature_verified_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{feature_id}/layers", response_model=dict[str, Any])
async def update_feature_layers(feature_id: str, update: FeatureLayersUpdate) -> dict[str, Any]:
    """Update the verification layers for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New layers list
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            params: tuple[list[str], str] = (update.layers, feature_id)
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET layers = %s, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id
                """,
                cast(
                    tuple[
                        str
                        | int
                        | float
                        | bool
                        | datetime
                        | list[str | int | float | bool | None]
                        | None,
                        ...,
                    ],
                    params,
                ),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

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
        logger.error("update_feature_layers_failed", feature_id=feature_id, error=str(e))
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
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

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
        logger.error("update_feature_layer_result_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Spec-Driven Endpoints (priority, acceptance criteria, vision goals)
# =========================================================================


class FeaturePriorityUpdate(BaseModel):
    """Request model for updating feature priority."""

    priority: int | None  # 1-5 for user override, null to auto-calculate


@router.patch("/{feature_id}/priority", response_model=dict[str, Any])
async def update_feature_priority(feature_id: str, update: FeaturePriorityUpdate) -> dict[str, Any]:
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
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

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
        logger.error("update_feature_priority_failed", feature_id=feature_id, error=str(e))
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
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

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

    passed: bool | None = None  # true, false, or null to reset
    evidence: str | None = None  # Evidence for the pass/fail decision
    criterion_type: str | None = None  # ui, api, db, backend
    verification_url: str | None = None  # URL for verification


@router.patch("/{feature_id}/acceptance-criteria/{criterion_id}", response_model=dict[str, Any])
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
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            criteria_raw: Any = row[0] if row[0] else []
            # Ensure we have a list of dicts
            criteria: list[dict[str, Any]] = criteria_raw if isinstance(criteria_raw, list) else []

            # Find and update the specific criterion
            found = False
            for c in criteria:
                if isinstance(c, dict) and c.get("id") == criterion_id:
                    if update.passed is not None:
                        c["passed"] = update.passed
                    if update.evidence is not None:
                        c["evidence"] = update.evidence
                    if update.criterion_type is not None:
                        c["type"] = update.criterion_type
                    if update.verification_url is not None:
                        c["verification"] = update.verification_url
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
async def update_feature_vision_goals(feature_id: str, update: VisionGoalsUpdate) -> dict[str, Any]:
    """Update the vision goals for a feature.

    Args:
        feature_id: Feature ID (e.g., FEAT-001)
        update: New vision goals list
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            params: tuple[list[str], str] = (update.vision_goals, feature_id)
            result = conn.execute(
                """
                UPDATE feature_capabilities
                SET vision_goals = %s, updated_at = NOW()
                WHERE feature_id = %s
                RETURNING feature_id, vision_goals
                """,
                cast(
                    tuple[
                        str
                        | int
                        | float
                        | bool
                        | datetime
                        | list[str | int | float | bool | None]
                        | None,
                        ...,
                    ],
                    params,
                ),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

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
        logger.error("update_feature_vision_goals_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Feature Dependencies Endpoints
# =========================================================================


class DependencyCreate(BaseModel):
    """Request model for creating a dependency."""

    depends_on_feature_id: str  # The feature this one depends on
    dependency_type: str = "blocks"  # blocks, soft, related
    notes: str | None = None


class DependencyResponse(BaseModel):
    """Response model for a dependency."""

    id: int
    feature_id: str
    depends_on_feature_id: str
    depends_on_name: str
    depends_on_passes: bool | None
    dependency_type: str
    notes: str | None
    is_satisfied: bool


@router.get("/{feature_id}/dependencies", response_model=list[DependencyResponse])
async def get_feature_dependencies(feature_id: str) -> list[DependencyResponse]:
    """Get all dependencies for a feature (what it depends on)."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # First verify feature exists
            feature_check = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()

            if not feature_check:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")

            # Get dependencies via the view
            rows = conn.execute(
                """
                SELECT id, feature, depends_on, depends_on_name,
                       depends_on_passes, dependency_type, notes, is_satisfied
                FROM feature_dependency_view
                WHERE feature = %s
                """,
                (feature_id,),
            ).fetchall()

        return [
            DependencyResponse(
                id=int(row[0]) if row[0] else 0,
                feature_id=str(row[1]) if row[1] else "",
                depends_on_feature_id=str(row[2]) if row[2] else "",
                depends_on_name=str(row[3]) if row[3] else "",
                depends_on_passes=bool(row[4]) if row[4] is not None else None,
                dependency_type=str(row[5]) if row[5] else "",
                notes=str(row[6]) if row[6] else None,
                is_satisfied=bool(row[7]) if row[7] is not None else False,
            )
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_feature_dependencies_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{feature_id}/dependencies", response_model=dict[str, Any])
async def add_feature_dependency(feature_id: str, dependency: DependencyCreate) -> dict[str, Any]:
    """Add a dependency to a feature.

    dependency_type values:
    - blocks: Hard dependency - depends_on must complete first
    - soft: Nice to have completed first
    - related: Just related, no ordering requirement
    """
    valid_types = {"blocks", "soft", "related"}
    if dependency.dependency_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid dependency_type '{dependency.dependency_type}'. Must be one of: {valid_types}",
        )

    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get both feature IDs
            feature_row = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (feature_id,),
            ).fetchone()
            depends_on_row = conn.execute(
                "SELECT id FROM feature_capabilities WHERE feature_id = %s",
                (dependency.depends_on_feature_id,),
            ).fetchone()

            if not feature_row:
                raise HTTPException(status_code=404, detail=f"Feature {feature_id} not found")
            if not depends_on_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Depends-on feature {dependency.depends_on_feature_id} not found",
                )

            # Insert dependency
            conn.execute(
                """
                INSERT INTO feature_dependencies (feature_id, depends_on_id, dependency_type, notes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (feature_id, depends_on_id) DO UPDATE
                SET dependency_type = EXCLUDED.dependency_type, notes = EXCLUDED.notes
                """,
                (feature_row[0], depends_on_row[0], dependency.dependency_type, dependency.notes),
            )
            conn.commit()

        logger.info(
            "feature_dependency_added",
            feature_id=feature_id,
            depends_on=dependency.depends_on_feature_id,
            type=dependency.dependency_type,
        )

        return {
            "status": "created",
            "feature_id": feature_id,
            "depends_on": dependency.depends_on_feature_id,
            "dependency_type": dependency.dependency_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_feature_dependency_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{feature_id}/dependencies/{depends_on_feature_id}")
async def remove_feature_dependency(feature_id: str, depends_on_feature_id: str) -> dict[str, Any]:
    """Remove a dependency from a feature."""
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                DELETE FROM feature_dependencies
                WHERE feature_id = (SELECT id FROM feature_capabilities WHERE feature_id = %s)
                AND depends_on_id = (SELECT id FROM feature_capabilities WHERE feature_id = %s)
                RETURNING id
                """,
                (feature_id, depends_on_feature_id),
            ).fetchone()
            conn.commit()

            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"Dependency {feature_id} -> {depends_on_feature_id} not found",
                )

        logger.info(
            "feature_dependency_removed",
            feature_id=feature_id,
            depends_on=depends_on_feature_id,
        )

        return {"status": "deleted", "feature_id": feature_id, "depends_on": depends_on_feature_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("remove_feature_dependency_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


# =========================================================================
# Subtask Endpoints REMOVED - Use Beads CLI instead:
# =========================================================================
#
# Task management moved to Beads:
#   bd ready --json              # Find work
#   bd create "task" -t task     # Create
#   bd update <id> --status ...  # Update
#   bd close <id> --reason "..." # Complete
#
# Task mutation endpoints REMOVED - use Beads CLI instead:
# - bd create "task" -t task -p 1 --deps discovered-from:<feature-issue>
# - bd update <id> --status in_progress|closed
# - bd close <id> --reason "Done"
# - bd delete <id>
# GET /tasks endpoint kept for reading existing tasks during migration.


# =========================================================================
# Feature-Specific Verification Endpoint
# =========================================================================


@router.post("/{feature_id}/verify", response_model=dict[str, Any])
async def verify_feature(feature_id: str) -> dict[str, Any]:
    """Trigger verification of all criteria for a feature."""
    from ...tasks.verify_criteria import verify_feature_criteria  # noqa: PLC0415

    try:
        task = verify_feature_criteria.delay(feature_id)
        logger.info("feature_verification_queued", feature_id=feature_id, task_id=task.id)
        return {"status": "queued", "feature_id": feature_id, "task_id": task.id}
    except Exception as e:
        logger.error("queue_verification_failed", feature_id=feature_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
