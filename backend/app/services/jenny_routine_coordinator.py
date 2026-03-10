"""Routine lifecycle helpers for Jenny operator runs."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.services.jenny_row_parsers import row_to_routine

logger = get_logger(__name__)


class JennyRoutineCoordinator:
    """Coordinate Jenny routine execution and persistence."""

    def run_daily_operator(self, service: Any, triggered_by: str = "manual") -> Any:
        self.fail_stale_routines(service, "daily_operator")
        active_routine = self.get_active_routine(service, "daily_operator")
        if active_routine is not None:
            return service.JennyRunResponse(
                routine=active_routine,
                dashboard=service.get_dashboard(),
            )
        routine_id, workflow_id = self.create_routine(service, "daily_operator", triggered_by)
        symbol_count = 0
        notification_count = 0

        try:
            service.workflow_orchestrator.update_workflow_status(
                workflow_id,
                status="running",
                current_step="reviewing_symbols",
            )
            positions = service.portfolio_mgr.get_positions()
            live_positions = [position for position in positions if position.position_type != "paper"]
            symbols = service._select_symbols(live_positions)
            symbol_count = len(symbols)
            price_data = service.price_fetcher.fetch_price_data(symbols) if symbols else {}
            symbol_profiles = service._build_symbol_profiles(
                symbols,
                live_symbols={position.symbol for position in live_positions},
            )
            evaluations_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)

            for symbol in symbols:
                symbol_profile = symbol_profiles.get(symbol, service._default_symbol_profile(symbol))
                thesis = service._ensure_thesis(symbol, symbol_profile)
                evaluations = service._evaluate_symbol(
                    symbol,
                    thesis,
                    price_data.get(symbol),
                    routine_id=routine_id,
                    workflow_id=workflow_id,
                    symbol_profile=symbol_profile,
                )
                for evaluation in evaluations:
                    service._save_agent_evaluation(routine_id, symbol, thesis, evaluation)
                    evaluations_by_symbol[symbol].append(evaluation)

            notification_count = service._create_notifications(
                routine_id=routine_id,
                live_symbols={position.symbol for position in live_positions},
                evaluations_by_symbol=evaluations_by_symbol,
            )

            summary = service._build_routine_summary(
                symbol_count, notification_count, evaluations_by_symbol
            )
            self.complete_routine(
                service, routine_id, "completed", summary, symbol_count, notification_count
            )
            service.workflow_orchestrator.complete_workflow(
                workflow_id,
                {
                    "routine_id": routine_id,
                    "summary": summary,
                    "symbols_scanned": symbol_count,
                    "notifications_created": notification_count,
                },
            )
        except Exception as exc:
            logger.error("jenny_daily_operator_failed", error=str(exc))
            self.complete_routine(
                service,
                routine_id,
                "failed",
                f"Jenny routine failed: {exc}",
                symbol_count,
                notification_count,
            )
            service.workflow_orchestrator.fail_workflow(workflow_id, str(exc), retry=False)
            raise

        return service.JennyRunResponse(
            routine=service._get_routine(routine_id),
            dashboard=service.get_dashboard(),
        )

    def run_weekly_learning(self, service: Any, triggered_by: str = "system") -> Any:
        self.fail_stale_routines(service, "weekly_learning")
        active_routine = self.get_active_routine(service, "weekly_learning")
        if active_routine is not None:
            return service.JennyRunResponse(
                routine=active_routine,
                dashboard=service.get_dashboard(),
            )
        routine_id, workflow_id = self.create_routine(service, "weekly_learning", triggered_by)

        try:
            service.workflow_orchestrator.update_workflow_status(
                workflow_id,
                status="running",
                current_step="refreshing_learning",
            )
            reviews_created = service._refresh_trade_reviews()
            scorecards_updated = service._refresh_scorecards()
            summary = (
                f"Reviewed {reviews_created} trade outcomes and refreshed "
                f"{scorecards_updated} agent scorecards."
            )
            self.complete_routine(
                service,
                routine_id,
                "completed",
                summary,
                symbols_scanned=reviews_created,
                notifications_created=0,
            )
            service.workflow_orchestrator.complete_workflow(
                workflow_id,
                {
                    "routine_id": routine_id,
                    "summary": summary,
                    "reviews_created": reviews_created,
                    "scorecards_updated": scorecards_updated,
                },
            )
        except Exception as exc:
            logger.error("jenny_weekly_learning_failed", error=str(exc))
            self.complete_routine(
                service,
                routine_id,
                "failed",
                f"Jenny learning failed: {exc}",
                symbols_scanned=0,
                notifications_created=0,
            )
            service.workflow_orchestrator.fail_workflow(workflow_id, str(exc), retry=False)
            raise

        return service.JennyRunResponse(
            routine=service._get_routine(routine_id),
            dashboard=service.get_dashboard(),
        )

    def create_routine(
        self,
        service: Any,
        routine_type: str,
        triggered_by: str,
    ) -> tuple[str, str]:
        routine_id = str(uuid.uuid4())
        workflow = service.workflow_orchestrator.start_workflow(
            workflow_type=f"jenny_{routine_type}",
            config={"routine_type": routine_type, "routine_id": routine_id},
            agents_involved=[spec.agent_slug for spec in service.AGENT_SPECS],
            triggered_by=triggered_by,
        )
        workflow_id = str(workflow["workflow_id"])
        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_routines (
                    id, routine_type, status, triggered_by, started_at, agents_used, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                [
                    routine_id,
                    routine_type,
                    "running",
                    triggered_by,
                    now,
                    json.dumps([spec.agent_slug for spec in service.AGENT_SPECS]),
                    json.dumps({"workflow_id": workflow_id}),
                ],
            )
            conn.commit()
        return routine_id, workflow_id

    def get_active_routine(self, service: Any, routine_type: str) -> Any | None:
        active_after = datetime.now(UTC) - service.ACTIVE_ROUTINE_WINDOW
        activity_after = datetime.now(UTC) - service.ROUTINE_ACTIVITY_STALE_WINDOW
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT jr.id, jr.routine_type, jr.status, jr.triggered_by, jr.summary, jr.agents_used,
                       jr.symbols_scanned, jr.notifications_created, jr.started_at, jr.completed_at, jr.metadata
                FROM jenny_routines jr
                LEFT JOIN LATERAL (
                    SELECT MAX(created_at) AS last_activity_at
                    FROM jenny_agent_evaluations
                    WHERE routine_id = jr.id
                ) activity ON TRUE
                WHERE jr.routine_type = %s
                  AND jr.status = 'running'
                  AND jr.started_at >= %s
                  AND COALESCE(activity.last_activity_at, jr.started_at) >= %s
                ORDER BY jr.started_at DESC
                LIMIT 1
                """,
                [routine_type, active_after, activity_after],
            ).fetchone()
        return row_to_routine(row) if row else None

    def fail_stale_routines(self, service: Any, routine_type: str | None = None) -> int:
        activity_before = datetime.now(UTC) - service.ROUTINE_ACTIVITY_STALE_WINDOW
        params: list[Any] = [activity_before]
        type_filter = ""
        if routine_type is not None:
            type_filter = "AND jr.routine_type = %s"
            params.append(routine_type)

        with service.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT jr.id, jr.started_at, COALESCE(activity.last_activity_at, jr.started_at) AS last_activity_at
                FROM jenny_routines jr
                LEFT JOIN LATERAL (
                    SELECT MAX(created_at) AS last_activity_at
                    FROM jenny_agent_evaluations
                    WHERE routine_id = jr.id
                ) activity ON TRUE
                WHERE jr.status = 'running'
                  AND COALESCE(activity.last_activity_at, jr.started_at) < %s
                  {type_filter}
                ORDER BY jr.started_at ASC
                """,
                params,
            ).fetchall()
            cleared = 0
            for routine_id_value, started_at, last_activity_at in rows:
                started_iso = getattr(started_at, "isoformat", None)
                started = started_iso() if callable(started_iso) else str(started_at)
                last_activity = (
                    last_activity_iso()
                    if callable(last_activity_iso := getattr(last_activity_at, "isoformat", None))
                    else str(last_activity_at)
                )
                conn.execute(
                    """
                    UPDATE jenny_routines
                    SET status = %s,
                        summary = %s,
                        completed_at = %s
                    WHERE id = %s
                    """,
                    [
                        "failed",
                        f"Marked failed after stale running routine from {started} with no activity after {last_activity}.",
                        datetime.now(UTC).isoformat(),
                        str(routine_id_value),
                    ],
                )
                cleared += 1
            if cleared:
                conn.commit()
        return cleared

    def complete_routine(
        self,
        service: Any,
        routine_id: str,
        status: str,
        summary: str,
        symbols_scanned: int,
        notifications_created: int,
    ) -> None:
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE jenny_routines
                SET status = %s,
                    summary = %s,
                    symbols_scanned = %s,
                    notifications_created = %s,
                    completed_at = %s
                WHERE id = %s
                """,
                [
                    status,
                    summary,
                    symbols_scanned,
                    notifications_created,
                    datetime.now(UTC).isoformat(),
                    routine_id,
                ],
            )
            conn.commit()
