"""Solution Map API endpoint - system architecture health overview.

This endpoint provides aggregated health and status data across all system layers
for visualization in a Solution Architecture Map. It shows the overall health of:
- Vision Goals (strategic layer)
- Features (capability layer)
- Tasks (execution layer)
- Tables (data layer)
- Endpoints (API layer)
- Data Sources (integration layer)

Plus critical blockers and warnings across all layers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager
from .sources import _load_sources_config

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["solution-map"])


class LayerSummary(BaseModel):
    """Summary statistics for a single system layer."""

    name: str
    count: int
    healthy: int
    warning: int
    critical: int
    items: list[dict[str, Any]] = []  # Top items for display


class Blocker(BaseModel):
    """A critical issue or warning in the system."""

    layer: str  # 'vision_goals', 'features', 'tasks', 'tables', 'endpoints', 'sources'
    item_id: str
    item_name: str
    issue: str
    severity: str  # 'critical', 'warning'


class SolutionMapResponse(BaseModel):
    """Complete solution architecture map data."""

    vision_goals: LayerSummary
    features: LayerSummary
    tasks: LayerSummary
    tables: LayerSummary
    endpoints: LayerSummary
    sources: LayerSummary
    blockers: list[Blocker]
    warnings: list[Blocker]
    overall_health: float  # 0-100
    last_updated: str


@router.get("/solution-map", response_model=SolutionMapResponse)
async def get_solution_map() -> SolutionMapResponse:
    """Get comprehensive system architecture health map.

    Aggregates health status across all system layers:
    - Vision Goals: Strategic objectives with feature/criteria tracking
    - Features: Capabilities with pass/fail status
    - Tasks: Celery tasks with execution health
    - Tables: Database tables with freshness and completeness
    - Endpoints: API endpoints with performance metrics
    - Data Sources: External API providers with availability

    Returns:
        SolutionMapResponse with layer summaries, blockers, warnings, and overall health
    """
    conn_mgr = get_connection_manager()
    blockers: list[Blocker] = []
    warnings: list[Blocker] = []

    try:
        with conn_mgr.connection() as conn:
            # ==================================================================
            # VISION GOALS LAYER
            # ==================================================================
            vision_goals_data = conn.execute(
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

            total_goals = len(vision_goals_data)
            healthy_goals = 0
            warning_goals = 0
            critical_goals = 0
            goal_items = []

            for row in vision_goals_data:
                code_raw, name_raw, feature_count, criteria_total_raw, criteria_passed_raw = row
                # Type cast for safety
                code = str(code_raw)
                name = str(name_raw)
                criteria_total = int(criteria_total_raw) if criteria_total_raw else 0
                criteria_passed = int(criteria_passed_raw) if criteria_passed_raw else 0
                pass_rate = criteria_passed / criteria_total if criteria_total > 0 else 0.0

                goal_items.append(
                    {
                        "code": code,
                        "name": name,
                        "feature_count": feature_count,
                        "pass_rate": round(pass_rate, 3),
                    }
                )

                # Health classification
                if pass_rate >= 0.8:
                    healthy_goals += 1
                elif pass_rate >= 0.5:
                    warning_goals += 1
                else:
                    critical_goals += 1
                    if criteria_total > 0:
                        blockers.append(
                            Blocker(
                                layer="vision_goals",
                                item_id=code,
                                item_name=name,
                                issue=f"Low pass rate: {pass_rate:.1%} ({criteria_passed}/{criteria_total})",
                                severity="critical",
                            )
                        )

            vision_goals_layer = LayerSummary(
                name="Vision Goals",
                count=total_goals,
                healthy=healthy_goals,
                warning=warning_goals,
                critical=critical_goals,
                items=goal_items,
            )

            # ==================================================================
            # FEATURES LAYER
            # ==================================================================
            # Health status is now calculated dynamically (column was dropped from feature_capabilities)
            features_data = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE passes = true) as passed,
                    COUNT(*) FILTER (WHERE passes = false) as failed,
                    COUNT(*) FILTER (WHERE passes IS NULL) as unreviewed
                FROM feature_capabilities
                """
            ).fetchone()

            (
                total_features,
                passed,
                failed,
                unreviewed,
            ) = features_data or (0, 0, 0, 0)

            # Type cast to int
            total_features = int(total_features) if total_features else 0
            passed = int(passed) if passed else 0
            failed = int(failed) if failed else 0
            unreviewed = int(unreviewed) if unreviewed else 0

            # Get failed features for blockers
            failed_features = conn.execute(
                """
                SELECT feature_id, name
                FROM feature_capabilities
                WHERE passes = false
                ORDER BY feature_id
                LIMIT 10
                """
            ).fetchall()

            for feat_id_raw, feat_name_raw in failed_features:
                blockers.append(
                    Blocker(
                        layer="features",
                        item_id=str(feat_id_raw),
                        item_name=str(feat_name_raw),
                        issue="Feature marked as failing (passes=false)",
                        severity="critical",
                    )
                )

            # Unreviewed features as warnings
            if unreviewed > 0:
                warnings.append(
                    Blocker(
                        layer="features",
                        item_id="features-unreviewed",
                        item_name=f"{unreviewed} unreviewed features",
                        issue=f"{unreviewed} features with passes=null need verification",
                        severity="warning",
                    )
                )

            features_layer = LayerSummary(
                name="Features",
                count=total_features,
                healthy=passed,
                warning=unreviewed,
                critical=failed,
                items=[
                    {"status": "passed", "count": passed},
                    {"status": "failed", "count": failed},
                    {"status": "unreviewed", "count": unreviewed},
                ],
            )

            # ==================================================================
            # TASKS LAYER (Celery)
            # ==================================================================
            tasks_data = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE health_status = 'active') as active,
                    COUNT(*) FILTER (WHERE health_status = 'suspect') as suspect,
                    COUNT(*) FILTER (WHERE health_status = 'orphaned') as orphaned,
                    COUNT(*) FILTER (WHERE health_status = 'legacy') as legacy,
                    AVG(success_rate_pct) FILTER (WHERE success_rate_pct IS NOT NULL) as avg_success_rate
                FROM celery_capabilities
                """
            ).fetchone()

            (
                total_tasks,
                active_tasks,
                suspect_tasks,
                orphaned_tasks,
                legacy_tasks,
                _avg_success_rate,
            ) = tasks_data or (0, 0, 0, 0, 0, None)

            # Type cast to int
            total_tasks = int(total_tasks) if total_tasks else 0
            active_tasks = int(active_tasks) if active_tasks else 0
            suspect_tasks = int(suspect_tasks) if suspect_tasks else 0
            orphaned_tasks = int(orphaned_tasks) if orphaned_tasks else 0
            legacy_tasks = int(legacy_tasks) if legacy_tasks else 0

            # Get legacy/orphaned tasks as blockers
            critical_tasks = conn.execute(
                """
                SELECT task_name, health_status, success_rate_pct
                FROM celery_capabilities
                WHERE health_status IN ('legacy', 'orphaned')
                    OR (success_rate_pct IS NOT NULL AND success_rate_pct < 50)
                ORDER BY health_status, task_name
                LIMIT 10
                """
            ).fetchall()

            for task_name_raw, health_status_raw, success_rate in critical_tasks:
                task_name = str(task_name_raw)
                health_status = str(health_status_raw) if health_status_raw else ""
                if health_status == "legacy":
                    issue = "Task marked as legacy (outdated/inactive)"
                elif health_status == "orphaned":
                    issue = "Task marked as orphaned (no active usage)"
                else:
                    issue = f"Low success rate: {success_rate}%"

                blockers.append(
                    Blocker(
                        layer="tasks",
                        item_id=task_name,
                        item_name=task_name,
                        issue=issue,
                        severity="critical",
                    )
                )

            # Suspect tasks as warnings
            if suspect_tasks > 0:
                warnings.append(
                    Blocker(
                        layer="tasks",
                        item_id="tasks-suspect",
                        item_name=f"{suspect_tasks} suspect tasks",
                        issue=f"{suspect_tasks} tasks marked as suspect need review",
                        severity="warning",
                    )
                )

            tasks_layer = LayerSummary(
                name="Tasks",
                count=total_tasks,
                healthy=active_tasks,
                warning=suspect_tasks,
                critical=legacy_tasks + orphaned_tasks,
                items=[
                    {"status": "active", "count": active_tasks},
                    {"status": "suspect", "count": suspect_tasks},
                    {"status": "orphaned", "count": orphaned_tasks},
                    {"status": "legacy", "count": legacy_tasks},
                ],
            )

            # ==================================================================
            # TABLES LAYER (Database)
            # ==================================================================
            tables_data = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE health_status = 'active') as active,
                    COUNT(*) FILTER (WHERE health_status = 'orphaned') as orphaned,
                    COUNT(*) FILTER (WHERE health_status = 'legacy') as legacy,
                    COUNT(*) FILTER (WHERE freshness_status = 'stale') as stale,
                    AVG(completeness_pct) FILTER (WHERE completeness_pct IS NOT NULL) as avg_completeness
                FROM db_capabilities
                """
            ).fetchone()

            (
                total_tables,
                active_tables,
                orphaned_tables,
                legacy_tables,
                stale_tables,
                _avg_completeness,
            ) = tables_data or (0, 0, 0, 0, 0, None)

            # Type cast to int
            total_tables = int(total_tables) if total_tables else 0
            active_tables = int(active_tables) if active_tables else 0
            orphaned_tables = int(orphaned_tables) if orphaned_tables else 0
            legacy_tables = int(legacy_tables) if legacy_tables else 0
            stale_tables = int(stale_tables) if stale_tables else 0

            # Get orphaned/legacy/stale tables as blockers
            critical_tables = conn.execute(
                """
                SELECT table_name, health_status, freshness_status, days_since_update
                FROM db_capabilities
                WHERE health_status IN ('legacy', 'orphaned')
                    OR freshness_status = 'stale'
                ORDER BY health_status, table_name
                LIMIT 10
                """
            ).fetchall()

            for table_name_raw, health_status_raw, freshness_status, days_since_update in critical_tables:
                table_name = str(table_name_raw)
                health_status = str(health_status_raw) if health_status_raw else ""
                if health_status == "legacy":
                    issue = "Table marked as legacy"
                elif health_status == "orphaned":
                    issue = "Table marked as orphaned"
                elif freshness_status == "stale":
                    issue = f"Stale data ({days_since_update} days since update)"
                else:
                    issue = "Unknown issue"

                blockers.append(
                    Blocker(
                        layer="tables",
                        item_id=table_name,
                        item_name=table_name,
                        issue=issue,
                        severity="critical",
                    )
                )

            tables_layer = LayerSummary(
                name="Tables",
                count=total_tables,
                healthy=active_tables,
                warning=stale_tables,
                critical=legacy_tables + orphaned_tables,
                items=[
                    {"status": "active", "count": active_tables},
                    {"status": "orphaned", "count": orphaned_tables},
                    {"status": "legacy", "count": legacy_tables},
                    {"status": "stale", "count": stale_tables},
                ],
            )

            # ==================================================================
            # ENDPOINTS LAYER (API)
            # ==================================================================
            endpoints_data = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE health_status = 'active') as active,
                    COUNT(*) FILTER (WHERE health_status = 'orphaned') as orphaned,
                    COUNT(*) FILTER (WHERE health_status = 'legacy') as legacy,
                    AVG(error_rate_pct) FILTER (WHERE error_rate_pct IS NOT NULL) as avg_error_rate
                FROM api_capabilities
                """
            ).fetchone()

            (
                total_endpoints,
                active_endpoints,
                orphaned_endpoints,
                legacy_endpoints,
                _avg_error_rate,
            ) = endpoints_data or (0, 0, 0, 0, None)

            # Type cast to int
            total_endpoints = int(total_endpoints) if total_endpoints else 0
            active_endpoints = int(active_endpoints) if active_endpoints else 0
            orphaned_endpoints = int(orphaned_endpoints) if orphaned_endpoints else 0
            legacy_endpoints = int(legacy_endpoints) if legacy_endpoints else 0

            # Get orphaned/legacy endpoints as blockers
            critical_endpoints = conn.execute(
                """
                SELECT endpoint_path, http_method, health_status, error_rate_pct
                FROM api_capabilities
                WHERE health_status IN ('legacy', 'orphaned')
                ORDER BY health_status, endpoint_path
                LIMIT 10
                """
            ).fetchall()

            for endpoint_path_raw, http_method_raw, health_status_raw, _error_rate in critical_endpoints:
                endpoint_path = str(endpoint_path_raw)
                http_method = str(http_method_raw)
                health_status = str(health_status_raw) if health_status_raw else ""
                if health_status == "legacy":
                    issue = "Endpoint marked as legacy"
                elif health_status == "orphaned":
                    issue = "Endpoint marked as orphaned"
                else:
                    issue = "Unknown issue"

                blockers.append(
                    Blocker(
                        layer="endpoints",
                        item_id=f"{http_method}:{endpoint_path}",
                        item_name=f"{http_method} {endpoint_path}",
                        issue=issue,
                        severity="critical",
                    )
                )

            endpoints_layer = LayerSummary(
                name="Endpoints",
                count=total_endpoints,
                healthy=active_endpoints,
                warning=0,
                critical=legacy_endpoints + orphaned_endpoints,
                items=[
                    {"status": "active", "count": active_endpoints},
                    {"status": "orphaned", "count": orphaned_endpoints},
                    {"status": "legacy", "count": legacy_endpoints},
                ],
            )

            # ==================================================================
            # DATA SOURCES LAYER
            # ==================================================================
            try:
                sources_config = _load_sources_config()
                providers = sources_config.get("providers", {})
                total_sources = len(providers)

                # Count sources by tier
                free_sources = sum(1 for p in providers.values() if p.get("tier") == "FREE")
                premium_sources = total_sources - free_sources

                sources_layer = LayerSummary(
                    name="Data Sources",
                    count=total_sources,
                    healthy=free_sources,  # Free sources are "healthy" (available)
                    warning=0,
                    critical=0,  # Premium sources not counted as critical
                    items=[
                        {"tier": "FREE", "count": free_sources},
                        {"tier": "PREMIUM", "count": premium_sources},
                    ],
                )
            except Exception as e:
                logger.error("sources_layer_error", error=str(e))
                sources_layer = LayerSummary(
                    name="Data Sources",
                    count=0,
                    healthy=0,
                    warning=0,
                    critical=0,
                    items=[],
                )

            # ==================================================================
            # CALCULATE OVERALL HEALTH (with severity weighting)
            # ==================================================================
            # Weights reflect business impact:
            # - Vision Goals: Strategic alignment (weight 3)
            # - Features: User-facing functionality (weight 4) - highest priority
            # - Tasks: Execution infrastructure (weight 2)
            # - Tables: Data layer (weight 2)
            # - Endpoints: API layer (weight 2)
            # - Sources: External integrations (weight 1) - lowest priority
            weights = {
                "vision_goals": 3,
                "features": 4,
                "tasks": 2,
                "tables": 2,
                "endpoints": 2,
                "sources": 1,
            }

            # Calculate weighted health score
            weighted_healthy = 0.0
            weighted_total = 0.0

            if total_goals > 0:
                weighted_healthy += (healthy_goals / total_goals) * weights["vision_goals"]
                weighted_total += weights["vision_goals"]

            if total_features > 0:
                weighted_healthy += (passed / total_features) * weights["features"]
                weighted_total += weights["features"]

            if total_tasks > 0:
                weighted_healthy += (active_tasks / total_tasks) * weights["tasks"]
                weighted_total += weights["tasks"]

            if total_tables > 0:
                weighted_healthy += (active_tables / total_tables) * weights["tables"]
                weighted_total += weights["tables"]

            if total_endpoints > 0:
                weighted_healthy += (active_endpoints / total_endpoints) * weights["endpoints"]
                weighted_total += weights["endpoints"]

            if total_sources > 0:
                weighted_healthy += (free_sources / total_sources) * weights["sources"]
                weighted_total += weights["sources"]

            overall_health = (weighted_healthy / weighted_total * 100) if weighted_total > 0 else 0.0

            logger.info(
                "solution_map_generated",
                total_goals=total_goals,
                total_features=total_features,
                total_tasks=total_tasks,
                total_tables=total_tables,
                total_endpoints=total_endpoints,
                total_sources=total_sources,
                overall_health=round(overall_health, 1),
                blockers_count=len(blockers),
                warnings_count=len(warnings),
            )

            return SolutionMapResponse(
                vision_goals=vision_goals_layer,
                features=features_layer,
                tasks=tasks_layer,
                tables=tables_layer,
                endpoints=endpoints_layer,
                sources=sources_layer,
                blockers=blockers,
                warnings=warnings,
                overall_health=round(overall_health, 1),
                last_updated=datetime.utcnow().isoformat(),
            )

    except Exception as e:
        logger.error("solution_map_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate solution map: {e}") from e
