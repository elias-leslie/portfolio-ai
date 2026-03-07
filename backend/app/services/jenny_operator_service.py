"""Jenny operator service.

Runs AI-assisted portfolio routines, stores multi-agent evaluations,
and surfaces plain-language notifications for the solo investor workflow.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.models.jenny import (
    JennyAgentEvaluation,
    JennyAgentScorecard,
    JennyDashboard,
    JennyNotification,
    JennyRoutine,
    JennyRunResponse,
    JennySymbolReview,
    JennyTradeReview,
)
from app.models.thesis import Thesis
from app.portfolio.analytics_returns import calculate_position_performances
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.portfolio.sector_labels import FUND_CATEGORY_LABELS
from app.repositories.agent_repository import AgentRunRepository
from app.services.thesis_service import ThesisService
from app.storage import get_storage
from app.watchlist.data_quality import calculate_data_quality, get_security_type
from app.watchlist.trading_style import INDEX_ETFS
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

FINAL_VERDICT_PRIORITY = {
    "exit": 5,
    "trim": 4,
    "review": 3,
    "buy": 2,
    "avoid": 1,
    "hold": 0,
}
POSITIVE_VERDICTS = {"buy", "hold"}
JENNY_AGENT_TIMEOUT_SECONDS = 90.0
MIN_AGENT_REVIEW_DATA_QUALITY_PCT = 55.0
PASSIVE_FUND_SYMBOLS = frozenset(INDEX_ETFS) | frozenset(FUND_CATEGORY_LABELS)
ACTIVE_ROUTINE_WINDOW = timedelta(minutes=15)
ROUTINE_ACTIVITY_STALE_WINDOW = timedelta(minutes=2)


@dataclass(frozen=True)
class JennyAgentSpec:
    agent_slug: str
    system_prompt: str
    prompt_mode: str


AGENT_SPECS: tuple[JennyAgentSpec, ...] = (
    JennyAgentSpec(
        agent_slug="equity-analyst",
        prompt_mode="thesis",
        system_prompt=(
            "You are Jenny's thesis guardian. Return strict JSON only. "
            "Focus on whether the thesis still holds for a solo long-only investor."
        ),
    ),
    JennyAgentSpec(
        agent_slug="risk-manager",
        prompt_mode="risk",
        system_prompt=(
            "You are Jenny's risk manager. Return strict JSON only. "
            "Focus on concentration, downside, and position-sizing discipline."
        ),
    ),
    JennyAgentSpec(
        agent_slug="trade-manager",
        prompt_mode="exit",
        system_prompt=(
            "You are Jenny. Return strict JSON only. "
            "Focus on whether to hold, trim, review, or exit based on the current facts."
        ),
    ),
    JennyAgentSpec(
        agent_slug="investment-committee",
        prompt_mode="synthesis",
        system_prompt=(
            "You are Jenny's decision synthesizer. Return strict JSON only. "
            "Weigh the thesis, risks, and catalysts to produce the clearest next action."
        ),
    ),
)


class JennyOperatorService:
    """Portfolio operator service for Jenny routines."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.watchlist_service = WatchlistService(self.storage)
        self.thesis_service = ThesisService()
        self.agent_run_repo = AgentRunRepository(self.storage)
        self.workflow_orchestrator = WorkflowOrchestrator(self.storage)

    def get_dashboard(self) -> JennyDashboard:
        """Return Jenny dashboard data."""
        self._fail_stale_routines()
        return JennyDashboard(
            routines=self._get_recent_routines(),
            notifications=self._get_open_notifications(),
            symbol_reviews=self._get_latest_symbol_reviews(),
            trade_reviews=self._get_recent_trade_reviews(),
            scorecards=self._get_scorecards(),
        )

    def acknowledge_notification(self, notification_id: str) -> JennyNotification | None:
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE jenny_notifications
                SET status = %s, acknowledged_at = %s
                WHERE id = %s
                """,
                ["acknowledged", now, notification_id],
            )
            conn.commit()

        return self._get_notification(notification_id)

    def run_daily_operator(self, triggered_by: str = "manual") -> JennyRunResponse:
        """Run the daily Jenny operator routine."""
        self._fail_stale_routines("daily_operator")
        active_routine = self._get_active_routine("daily_operator")
        if active_routine is not None:
            return JennyRunResponse(
                routine=active_routine,
                dashboard=self.get_dashboard(),
            )
        routine_id, workflow_id = self._create_routine("daily_operator", triggered_by)
        symbol_count = 0
        notification_count = 0

        try:
            self.workflow_orchestrator.update_workflow_status(
                workflow_id,
                status="running",
                current_step="reviewing_symbols",
            )
            positions = self.portfolio_mgr.get_positions()
            live_positions = [position for position in positions if position.position_type != "paper"]
            symbols = self._select_symbols(live_positions)
            symbol_count = len(symbols)
            price_data = self.price_fetcher.fetch_price_data(symbols) if symbols else {}
            symbol_profiles = self._build_symbol_profiles(symbols)
            evaluations_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)

            for symbol in symbols:
                symbol_profile = symbol_profiles.get(symbol, self._default_symbol_profile(symbol))
                thesis = self._ensure_thesis(symbol, symbol_profile)
                evaluations = self._evaluate_symbol(
                    symbol,
                    thesis,
                    price_data.get(symbol),
                    routine_id=routine_id,
                    workflow_id=workflow_id,
                    symbol_profile=symbol_profile,
                )
                for evaluation in evaluations:
                    self._save_agent_evaluation(routine_id, symbol, thesis, evaluation)
                    evaluations_by_symbol[symbol].append(evaluation)

            notification_count = self._create_notifications(
                routine_id=routine_id,
                live_symbols={position.symbol for position in live_positions},
                evaluations_by_symbol=evaluations_by_symbol,
            )

            summary = self._build_routine_summary(symbol_count, notification_count, evaluations_by_symbol)
            self._complete_routine(routine_id, "completed", summary, symbol_count, notification_count)
            self.workflow_orchestrator.complete_workflow(
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
            self._complete_routine(
                routine_id,
                "failed",
                f"Jenny routine failed: {exc}",
                symbol_count,
                notification_count,
            )
            self.workflow_orchestrator.fail_workflow(workflow_id, str(exc), retry=False)
            raise

        return JennyRunResponse(
            routine=self._get_routine(routine_id),
            dashboard=self.get_dashboard(),
        )

    def run_weekly_learning(self, triggered_by: str = "system") -> JennyRunResponse:
        """Run Jenny's weekly trade review and scorecard update."""
        self._fail_stale_routines("weekly_learning")
        active_routine = self._get_active_routine("weekly_learning")
        if active_routine is not None:
            return JennyRunResponse(
                routine=active_routine,
                dashboard=self.get_dashboard(),
            )
        routine_id, workflow_id = self._create_routine("weekly_learning", triggered_by)

        try:
            self.workflow_orchestrator.update_workflow_status(
                workflow_id,
                status="running",
                current_step="refreshing_learning",
            )
            reviews_created = self._refresh_trade_reviews()
            scorecards_updated = self._refresh_scorecards()
            summary = (
                f"Reviewed {reviews_created} trade outcomes and refreshed "
                f"{scorecards_updated} agent scorecards."
            )
            self._complete_routine(
                routine_id,
                "completed",
                summary,
                symbols_scanned=reviews_created,
                notifications_created=0,
            )
            self.workflow_orchestrator.complete_workflow(
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
            self._complete_routine(
                routine_id,
                "failed",
                f"Jenny learning failed: {exc}",
                symbols_scanned=0,
                notifications_created=0,
            )
            self.workflow_orchestrator.fail_workflow(workflow_id, str(exc), retry=False)
            raise

        return JennyRunResponse(
            routine=self._get_routine(routine_id),
            dashboard=self.get_dashboard(),
        )

    def _create_routine(self, routine_type: str, triggered_by: str) -> tuple[str, str]:
        routine_id = str(uuid.uuid4())
        workflow = self.workflow_orchestrator.start_workflow(
            workflow_type=f"jenny_{routine_type}",
            config={"routine_type": routine_type, "routine_id": routine_id},
            agents_involved=[spec.agent_slug for spec in AGENT_SPECS],
            triggered_by=triggered_by,
        )
        workflow_id = str(workflow["workflow_id"])
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
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
                    json.dumps([spec.agent_slug for spec in AGENT_SPECS]),
                    json.dumps({"workflow_id": workflow_id}),
                ],
            )
            conn.commit()
        return routine_id, workflow_id

    def _get_active_routine(self, routine_type: str) -> JennyRoutine | None:
        active_after = datetime.now(UTC) - ACTIVE_ROUTINE_WINDOW
        activity_after = datetime.now(UTC) - ROUTINE_ACTIVITY_STALE_WINDOW
        with self.storage.connection() as conn:
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
        return self._row_to_routine(row) if row else None

    def _fail_stale_routines(self, routine_type: str | None = None) -> int:
        activity_before = datetime.now(UTC) - ROUTINE_ACTIVITY_STALE_WINDOW
        params: list[Any] = [activity_before]
        type_filter = ""
        if routine_type is not None:
            type_filter = "AND jr.routine_type = %s"
            params.append(routine_type)

        with self.storage.connection() as conn:
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
            for routine_id, started_at, last_activity_at in rows:
                started = started_at.isoformat() if hasattr(started_at, "isoformat") else str(started_at)
                last_activity = (
                    last_activity_at.isoformat() if hasattr(last_activity_at, "isoformat") else str(last_activity_at)
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
                        str(routine_id),
                    ],
                )
                cleared += 1
            if cleared:
                conn.commit()
        return cleared

    def _complete_routine(
        self,
        routine_id: str,
        status: str,
        summary: str,
        symbols_scanned: int,
        notifications_created: int,
    ) -> None:
        with self.storage.connection() as conn:
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

    def _select_symbols(self, live_positions: list[Any]) -> list[str]:
        symbols = [position.symbol for position in live_positions]
        candidates = self.watchlist_service.get_items_with_scores()
        candidate_symbols = [
            item["symbol"]
            for item in sorted(
                candidates,
                key=lambda item: float((item.get("current_score") or {}).get("overall") or 0.0),
                reverse=True,
            )
            if item["symbol"] not in symbols
        ][:3]
        return list(dict.fromkeys(symbols + candidate_symbols))

    def _default_symbol_profile(self, symbol: str) -> dict[str, Any]:
        security_type = self._normalize_security_type(symbol, None)
        return {
            "security_type": security_type,
            "is_passive_fund": security_type == "etf",
            "data_quality_pct": None,
        }

    def _normalize_security_type(self, symbol: str, stored_security_type: str | None) -> str:
        normalized_symbol = symbol.upper()
        normalized_type = (stored_security_type or "").strip().lower()
        if normalized_type == "etf" or normalized_symbol in PASSIVE_FUND_SYMBOLS:
            return "etf"
        if normalized_type in {"equity", "index", "other"}:
            return normalized_type
        return "equity"

    def _build_symbol_profiles(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        quality_map = calculate_data_quality(self.storage, symbols)
        profiles: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            security_type = self._normalize_security_type(symbol, get_security_type(self.storage, symbol))
            quality = quality_map.get(symbol)
            profiles[symbol] = {
                "security_type": security_type,
                "is_passive_fund": security_type == "etf",
                "data_quality_pct": quality.overall_pct if quality else None,
            }
        return profiles

    def _ensure_thesis(self, symbol: str, symbol_profile: dict[str, Any]) -> Thesis | None:
        thesis = self.thesis_service.get_thesis(symbol)
        if thesis is not None:
            return thesis
        if symbol_profile.get("is_passive_fund"):
            return None
        data_quality_pct = symbol_profile.get("data_quality_pct")
        if data_quality_pct is not None and data_quality_pct < MIN_AGENT_REVIEW_DATA_QUALITY_PCT:
            return None
        if not AGENT_HUB_ENABLED:
            return None
        try:
            return self.thesis_service.generate_thesis(symbol, force=False)
        except Exception as exc:
            logger.warning("jenny_thesis_generation_skipped", symbol=symbol, error=str(exc))
            return None

    def _evaluate_symbol(
        self,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        routine_id: str,
        workflow_id: str,
        symbol_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not AGENT_HUB_ENABLED or self._should_use_insufficient_evidence_fallback(thesis, symbol_profile):
            return [self._fallback_evaluation(symbol, thesis, symbol_profile=symbol_profile)]

        payload = self._build_symbol_context(symbol, thesis, price_data, symbol_profile)
        payload["routine_id"] = routine_id
        payload["workflow_id"] = workflow_id
        evaluations = []
        for spec in AGENT_SPECS:
            evaluations.append(self._run_agent_review(spec, payload))
        return evaluations

    def _should_use_insufficient_evidence_fallback(
        self,
        thesis: Thesis | None,
        symbol_profile: dict[str, Any],
    ) -> bool:
        if thesis is not None:
            return False
        data_quality_pct = symbol_profile.get("data_quality_pct")
        return data_quality_pct is not None and data_quality_pct < MIN_AGENT_REVIEW_DATA_QUALITY_PCT

    def _build_symbol_context(
        self,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        symbol_profile: dict[str, Any],
    ) -> dict[str, Any]:
        price = getattr(price_data, "price", None) if price_data else None
        is_passive_fund = bool(symbol_profile.get("is_passive_fund"))
        data_quality_pct = symbol_profile.get("data_quality_pct")
        return {
            "symbol": symbol,
            "current_price": price,
            "security_type": symbol_profile.get("security_type"),
            "review_mode": "allocation" if is_passive_fund else "thesis",
            "data_quality_pct": data_quality_pct,
            "evidence_status": (
                "thin"
                if data_quality_pct is not None and data_quality_pct < MIN_AGENT_REVIEW_DATA_QUALITY_PCT
                else "usable"
            ),
            "thesis_status": (
                thesis.status.value
                if thesis
                else "not_required_for_fund"
                if is_passive_fund
                else "missing"
            ),
            "thesis_action": thesis.action.value if thesis else None,
            "expected_return_pct": thesis.expected_return_pct if thesis else None,
            "expected_timeframe_days": thesis.expected_timeframe_days if thesis else None,
            "cross_validation_score": thesis.cross_validation_score if thesis else None,
            "core_reasons": [reason.reason for reason in thesis.core_reasons] if thesis else [],
            "risks": [risk.risk for risk in thesis.risks] if thesis else [],
            "key_catalysts": [catalyst.catalyst for catalyst in thesis.key_catalysts] if thesis else [],
            "invalidation_triggers": self.thesis_service.check_invalidation_triggers(symbol) if thesis else [],
        }

    def _run_agent_review(self, spec: JennyAgentSpec, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        client = AgentHubAPIClient(
            agent_slug=spec.agent_slug,
            timeout=JENNY_AGENT_TIMEOUT_SECONDS,
        )
        prompt = self._build_agent_prompt(spec.prompt_mode, payload)
        self.agent_run_repo.create_run(
            run_id=run_id,
            agent_type=f"jenny_{spec.agent_slug}",
            model=client.get_model_name(),
            started_at=started_at,
            provider=client.provider,
            run_type="automated",
            workflow_id=str(payload["workflow_id"]),
        )
        self.agent_run_repo.store_message(run_id, "user", prompt)

        try:
            response = client.generate(
                prompt=prompt,
                system=spec.system_prompt,
                purpose=f"jenny:{spec.agent_slug}",
            )
            self.agent_run_repo.store_message(run_id, "assistant", response.content)
            parsed = self._parse_agent_response(response.content, spec.agent_slug)
            parsed["provider"] = response.provider
            parsed["model"] = response.model
            parsed["agent_run_id"] = run_id
            self.agent_run_repo.complete_run(
                run_id=run_id,
                completed_at=datetime.now(UTC),
                status="completed",
                num_ideas=0,
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                token_usage=response.usage,
            )
            return parsed
        except Exception as exc:
            self.agent_run_repo.complete_run(
                run_id=run_id,
                completed_at=datetime.now(UTC),
                status="error",
                num_ideas=0,
                error_message=str(exc),
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
            )
            logger.warning("jenny_agent_review_failed", agent=spec.agent_slug, error=str(exc))
            return self._fallback_evaluation(
                payload["symbol"],
                None,
                agent_name=spec.agent_slug,
            )
        finally:
            client.close()

    def _build_agent_prompt(self, mode: str, payload: dict[str, Any]) -> str:
        mode_instruction = {
            "thesis": "Decide whether the thesis still supports owning or buying the symbol.",
            "risk": "Decide whether current risk justifies trimming, reviewing, or holding.",
            "exit": "Focus on the next action for the position: hold, trim, review, exit, or avoid.",
            "synthesis": "Combine the prior evidence into the clearest plain-English next step.",
        }[mode]
        review_instruction = ""
        if payload.get("review_mode") == "allocation":
            review_instruction = (
                " This symbol is a passive fund or index-style holding. "
                "Do not complain about a missing single-company thesis. "
                "Focus on allocation fit, concentration, market regime, and whether to hold, trim, or avoid adding."
            )
        elif payload.get("evidence_status") == "thin":
            review_instruction = (
                " Fresh evidence is limited. "
                "Do not invent precision or hidden conviction. "
                "If the facts are too thin, prefer review or avoid and explain the missing evidence plainly."
            )
        return (
            f"{mode_instruction}{review_instruction}\n"
            "Return JSON with keys: verdict, confidence, rationale, recommendation, strengths, weaknesses.\n"
            "Set confidence as a number from 0.0 to 1.0.\n"
            f"Context:\n{json.dumps(payload, default=str)}"
        )

    def _normalize_confidence(self, raw_confidence: Any) -> float | None:
        if raw_confidence is None:
            return None
        if isinstance(raw_confidence, bool):
            return 1.0 if raw_confidence else 0.0
        if isinstance(raw_confidence, int | float):
            value = float(raw_confidence)
            return value / 100.0 if value > 1.0 else value
        if isinstance(raw_confidence, str):
            normalized = raw_confidence.strip().lower()
            qualitative_map = {
                "low": 0.35,
                "medium": 0.6,
                "med": 0.6,
                "high": 0.8,
            }
            if normalized in qualitative_map:
                return qualitative_map[normalized]
            if normalized.endswith("%"):
                normalized = normalized[:-1].strip()
            value = float(normalized)
            return value / 100.0 if value > 1.0 else value
        raise ValueError(f"Unsupported confidence value: {raw_confidence!r}")

    def _normalize_verdict(self, raw_verdict: Any) -> str:
        verdict = str(raw_verdict or "review").strip().lower()
        compact = verdict.split("—", 1)[0].split("-", 1)[0].strip()
        prefix_map = (
            (("buy",), "buy"),
            (("hold",), "hold"),
            (("trim",), "trim"),
            (("exit", "sell"), "exit"),
            (("avoid", "pass", "skip"), "avoid"),
        )
        for prefixes, normalized in prefix_map:
            if compact.startswith(prefixes):
                return normalized
        if compact in {"wait", "watch", "review", "reassess"}:
            return "review"
        return "review"

    def _parse_agent_response(self, content: str, agent_name: str) -> dict[str, Any]:
        try:
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            elif "{" in content and "}" in content:
                content = content[content.index("{"): content.rindex("}") + 1]
            parsed = json.loads(content)
        except Exception:
            parsed = {
                "verdict": "review",
                "confidence": 0.45,
                "rationale": content.strip(),
                "recommendation": "Manual review required.",
                "strengths": [],
                "weaknesses": ["Response was not valid JSON."],
            }

        strengths = parsed.get("strengths", [])
        if not isinstance(strengths, list):
            strengths = []
        weaknesses = parsed.get("weaknesses", [])
        if not isinstance(weaknesses, list):
            weaknesses = []

        return {
            "agent_name": agent_name,
            "verdict": self._normalize_verdict(parsed.get("verdict", "review")),
            "confidence": self._normalize_confidence(parsed.get("confidence", 0.5)),
            "rationale": str(parsed.get("rationale") or "No rationale provided."),
            "recommendation": str(parsed.get("recommendation")) if parsed.get("recommendation") else None,
            "strengths": [str(item) for item in strengths][:5],
            "weaknesses": [str(item) for item in weaknesses][:5],
            "metadata": {"raw_response": parsed},
        }

    def _fallback_evaluation(
        self,
        symbol: str,
        thesis: Thesis | None,
        agent_name: str = "fallback_operator",
        symbol_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        verdict = "review"
        rationale = "Jenny could not reach Agent Hub, so this symbol needs manual review."
        recommendation = "Check the thesis and current price action before taking action."
        strengths = ["Existing thesis is still stored." if thesis else "Keeps the workflow running without fake certainty."]
        weaknesses = ["Agent Hub unavailable, so confidence is limited."]
        profile = symbol_profile or {}
        data_quality_pct = profile.get("data_quality_pct")
        if data_quality_pct is not None and data_quality_pct < MIN_AGENT_REVIEW_DATA_QUALITY_PCT and thesis is None:
            rationale = "There is not enough fresh evidence to form a trustworthy review yet."
            recommendation = "Wait for fresher price, signal, and catalyst data before acting."
            strengths = ["Jenny avoided pretending the evidence was stronger than it is."]
            weaknesses = ["Fresh data is too thin for a trustworthy review right now."]
        elif profile.get("is_passive_fund") and thesis is None:
            rationale = "This is a passive fund holding, so Jenny is treating it as an allocation review instead of a missing company thesis."
            recommendation = "Review concentration, portfolio role, and whether you still want more exposure here."
            strengths = ["Passive fund holdings do not require a single-company thesis to stay actionable."]
            weaknesses = ["Fund reviews rely more on allocation and concentration than company-specific catalysts."]
        if thesis and thesis.status.value == "active" and thesis.action.value == "BUY":
            verdict = "hold"
            rationale = "Active thesis exists, but Jenny could not refresh the agent review."
        return {
            "agent_name": agent_name,
            "provider": None,
            "model": None,
            "verdict": verdict,
            "confidence": 0.35,
            "rationale": rationale,
            "recommendation": recommendation,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "metadata": {"fallback": True, "symbol": symbol, "symbol_profile": profile},
            "agent_run_id": None,
        }

    def _save_agent_evaluation(
        self,
        routine_id: str,
        symbol: str,
        thesis: Thesis | None,
        evaluation: dict[str, Any],
    ) -> None:
        evaluation_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_agent_evaluations (
                    id, routine_id, symbol, agent_name, provider, model, verdict, confidence,
                    rationale, recommendation, strengths, weaknesses, metadata, thesis_id, agent_run_id, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s
                )
                """,
                [
                    evaluation_id,
                    routine_id,
                    symbol,
                    evaluation["agent_name"],
                    evaluation.get("provider"),
                    evaluation.get("model"),
                    evaluation["verdict"],
                    evaluation.get("confidence"),
                    evaluation["rationale"],
                    evaluation.get("recommendation"),
                    json.dumps(evaluation.get("strengths", [])),
                    json.dumps(evaluation.get("weaknesses", [])),
                    json.dumps(evaluation.get("metadata", {})),
                    thesis.id if thesis else None,
                    evaluation.get("agent_run_id"),
                    now,
                ],
            )
            conn.commit()

    def _create_notifications(
        self,
        routine_id: str,
        live_symbols: set[str],
        evaluations_by_symbol: dict[str, list[dict[str, Any]]],
    ) -> int:
        count = 0
        review_map = {
            symbol: self._aggregate_symbol_review(symbol, evaluations, self.thesis_service.get_thesis(symbol))
            for symbol, evaluations in evaluations_by_symbol.items()
        }
        position_actions = self._build_position_action_map(
            {symbol: review for symbol, review in review_map.items() if symbol in live_symbols}
        )
        for symbol, review in review_map.items():
            position_action = position_actions.get(symbol)
            evaluations = evaluations_by_symbol.get(symbol, [])
            if symbol in live_symbols and position_action and position_action["action"] != "hold":
                self._upsert_notification(
                    routine_id,
                    symbol,
                    category=f"position_{position_action['action']}",
                    severity=position_action["severity"],
                    title=position_action["title"],
                    detail=position_action["detail"],
                    recommendation=position_action["recommendation"],
                )
                count += 1
            elif symbol in live_symbols and review.final_verdict in {"exit", "trim", "review"}:
                self._upsert_notification(
                    routine_id,
                    symbol,
                    category=f"position_{review.final_verdict}",
                    severity="critical" if review.final_verdict == "exit" else "warning",
                    title=f"{symbol}: {review.final_verdict.title()} this position",
                    detail=" ".join(review.reasons) or f"Jenny wants you to {review.final_verdict} {symbol}.",
                    recommendation=review.evaluations[0].recommendation if review.evaluations else None,
                )
                count += 1
            if symbol not in live_symbols and review.final_verdict == "buy" and (review.average_confidence or 0) >= 0.7:
                self._upsert_notification(
                    routine_id,
                    symbol,
                    category="watchlist_buy_candidate",
                    severity="info",
                    title=f"{symbol}: high-conviction setup",
                    detail=" ".join(review.reasons) or f"Jenny flagged {symbol} as a vetted setup.",
                    recommendation=review.evaluations[0].recommendation if review.evaluations else None,
                )
                count += 1

            thesis = self.thesis_service.get_thesis(symbol)
            invalidation_triggers = self.thesis_service.check_invalidation_triggers(symbol) if thesis else []
            profile = self._extract_symbol_profile(evaluations)
            if invalidation_triggers and not (
                position_action and position_action["action"] == "exit"
            ):
                self._upsert_notification(
                    routine_id,
                    symbol,
                    category="thesis_invalidation",
                    severity="critical" if symbol in live_symbols else "warning",
                    title=f"{symbol}: thesis invalidation triggered",
                    detail=" ".join(invalidation_triggers),
                    recommendation="Review the thesis and current price action before holding or adding.",
                )
                count += 1
            if thesis is None and not profile.get("is_passive_fund"):
                self._upsert_notification(
                    routine_id,
                    symbol,
                    category="missing_thesis",
                    severity="warning",
                    title=f"{symbol}: thesis missing",
                    detail="Jenny could not find an active thesis for this symbol yet.",
                    recommendation="Review the symbol and let Jenny regenerate the thesis before acting.",
                )
                count += 1
        return count

    def _extract_symbol_profile(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        for evaluation in evaluations:
            profile = (evaluation.get("metadata") or {}).get("symbol_profile")
            if isinstance(profile, dict):
                return profile
        return {}

    def _upsert_notification(
        self,
        routine_id: str,
        symbol: str | None,
        category: str,
        severity: str,
        title: str,
        detail: str,
        recommendation: str | None,
    ) -> None:
        with self.storage.connection() as conn:
            existing = conn.execute(
                """
                SELECT id
                FROM jenny_notifications
                WHERE status = 'open'
                  AND category = %s
                  AND COALESCE(symbol, '') = COALESCE(%s, '')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [category, symbol],
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE jenny_notifications
                    SET routine_id = %s,
                        severity = %s,
                        title = %s,
                        detail = %s,
                        recommendation = %s,
                        created_at = %s
                    WHERE id = %s
                    """,
                    [routine_id, severity, title, detail, recommendation, datetime.now(UTC).isoformat(), str(existing[0])],
                )
            else:
                conn.execute(
                    """
                    INSERT INTO jenny_notifications (
                        id, routine_id, symbol, category, severity, status, title, detail, recommendation, created_at
                    ) VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s, %s)
                    """,
                    [
                        str(uuid.uuid4()),
                        routine_id,
                        symbol,
                        category,
                        severity,
                        title,
                        detail,
                        recommendation,
                        datetime.now(UTC).isoformat(),
                    ],
                )
            conn.commit()

    def _build_routine_summary(
        self,
        symbol_count: int,
        notification_count: int,
        evaluations_by_symbol: dict[str, list[dict[str, Any]]],
    ) -> str:
        opportunities = sum(
            1
            for symbol, evaluations in evaluations_by_symbol.items()
            if self._aggregate_symbol_review(symbol, evaluations, self.thesis_service.get_thesis(symbol)).final_verdict == "buy"
        )
        return (
            f"Jenny reviewed {symbol_count} symbols, found {opportunities} buy-ready setups, "
            f"and opened {notification_count} alerts."
        )

    def _refresh_trade_reviews(self) -> int:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT io.idea_id, io.symbol, io.realized_return_pct, io.exit_reason, wt.id
                FROM idea_outcomes io
                LEFT JOIN watchlist_thesis wt ON wt.symbol = io.symbol
                WHERE io.status IN ('closed', 'target_hit', 'stop_hit', 'expired')
                  AND NOT EXISTS (
                      SELECT 1 FROM jenny_trade_reviews jtr WHERE jtr.idea_id = io.idea_id
                  )
                ORDER BY io.updated_at DESC
                LIMIT 50
                """
            ).fetchall()

        count = 0
        for row in rows:
            idea_id, symbol, realized_return_pct, exit_reason, thesis_id = row
            return_pct = float(realized_return_pct) if realized_return_pct is not None else None
            outcome_label = "win" if (return_pct or 0.0) > 0 else "loss" if (return_pct or 0.0) < 0 else "flat"
            lesson = self._build_trade_lesson(return_pct, str(exit_reason) if exit_reason else None)
            what_worked, what_failed, next_time = self._build_trade_review_details(return_pct, exit_reason)
            self._save_trade_review(
                symbol=str(symbol),
                thesis_id=str(thesis_id) if thesis_id else None,
                idea_id=str(idea_id),
                outcome_label=outcome_label,
                return_pct=return_pct,
                lesson=lesson,
                what_worked=what_worked,
                what_failed=what_failed,
                next_time=next_time,
                agent_consensus=self._build_review_consensus(str(symbol)),
            )
            count += 1
        return count

    def _refresh_scorecards(self) -> int:
        evaluations = self._fetch_all_evaluations()
        reviews = self._get_recent_trade_reviews(limit=200)
        reviews_by_symbol = defaultdict(list)
        for review in reviews:
            reviews_by_symbol[review.symbol].append(review)

        grouped: dict[str, list[JennyAgentEvaluation]] = defaultdict(list)
        for evaluation in evaluations:
            grouped[evaluation.agent_name].append(evaluation)

        updated = 0
        for agent_name, agent_evaluations in grouped.items():
            scorecard = self._build_scorecard(agent_name, agent_evaluations, reviews_by_symbol)
            self._save_scorecard(scorecard)
            updated += 1
        return updated

    def _build_trade_lesson(self, return_pct: float | None, exit_reason: str | None) -> str:
        if return_pct is None:
            return "The trade closed without a usable return record, so Jenny could not learn much from it."
        if return_pct >= 10:
            return "Winning trades tend to come from theses that stayed intact long enough for the move to play out."
        if return_pct > 0:
            return "The trade worked, but the edge was modest. Sizing and timing mattered more than raw conviction."
        if return_pct <= -10:
            return "Large losses usually mean the thesis broke faster than expected or the position stayed too large after weakness appeared."
        return "Small losses are acceptable when they confirm the invalidation process is working early."

    def _build_trade_review_details(
        self,
        return_pct: float | None,
        exit_reason: str | None,
    ) -> tuple[str, str, str]:
        if return_pct is None:
            return (
                "The outcome data was incomplete.",
                "Jenny cannot score the decision quality without a realized return.",
                "Improve fill and exit tracking.",
            )
        what_worked = "The trade respected the thesis and risk plan." if return_pct > 0 else "The invalidation process likely prevented a larger loss."
        what_failed = (
            "The exit was late or the thesis was weaker than expected."
            if return_pct <= 0
            else "Profit capture could still improve if the exit reason was vague."
        )
        next_time = (
            "Favor similar setups when the same catalysts and risk profile show up again."
            if return_pct > 0
            else f"Cut sooner when the same warning signs appear ({exit_reason or 'invalid thesis'})."
        )
        return what_worked, what_failed, next_time

    def _save_trade_review(
        self,
        symbol: str,
        thesis_id: str | None,
        idea_id: str | None,
        outcome_label: str,
        return_pct: float | None,
        lesson: str,
        what_worked: str,
        what_failed: str,
        next_time: str,
        agent_consensus: dict[str, Any],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_trade_reviews (
                    id, symbol, thesis_id, idea_id, review_source, outcome_label, return_pct,
                    lesson, what_worked, what_failed, next_time, agent_consensus, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                [
                    str(uuid.uuid4()),
                    symbol,
                    thesis_id,
                    idea_id,
                    "paper_trade",
                    outcome_label,
                    return_pct,
                    lesson,
                    what_worked,
                    what_failed,
                    next_time,
                    json.dumps(agent_consensus),
                    now,
                    now,
                ],
            )
            conn.commit()

    def _build_review_consensus(self, symbol: str) -> dict[str, Any]:
        latest_review = next(
            (
                review
                for review in self._get_latest_symbol_reviews(limit=20)
                if review.symbol == symbol
            ),
            None,
        )
        if latest_review is None:
            return {}
        return {
            "final_verdict": latest_review.final_verdict,
            "average_confidence": latest_review.average_confidence,
            "agents": [evaluation.agent_name for evaluation in latest_review.evaluations],
            "agent_verdicts": {
                evaluation.agent_name: evaluation.verdict
                for evaluation in latest_review.evaluations
            },
            "agent_confidences": {
                evaluation.agent_name: evaluation.confidence
                for evaluation in latest_review.evaluations
                if evaluation.confidence is not None
            },
        }

    def _build_scorecard(
        self,
        agent_name: str,
        evaluations: list[JennyAgentEvaluation],
        reviews_by_symbol: dict[str, list[JennyTradeReview]],
    ) -> JennyAgentScorecard:
        total_evaluations = len(evaluations)
        positive_verdicts = sum(1 for evaluation in evaluations if evaluation.verdict in POSITIVE_VERDICTS)
        linked_pairs = self._link_evaluations_to_reviews(evaluations, reviews_by_symbol)
        unique_reviews = {review.id: review for _, review in linked_pairs}.values()
        completed_reviews = len(unique_reviews)
        positive_reviews = [review for review in unique_reviews if (review.return_pct or 0.0) > 0]
        avg_return = (
            sum((review.return_pct or 0.0) for review in unique_reviews) / completed_reviews
            if completed_reviews
            else None
        )
        win_rate = len(positive_reviews) / completed_reviews if completed_reviews else None

        grouped_by_symbol = defaultdict(list)
        for evaluation in evaluations:
            grouped_by_symbol[evaluation.symbol].append(evaluation)
        agreement_hits = 0
        calibration_scores: list[float] = []
        for symbol_evaluations in grouped_by_symbol.values():
            counts = Counter(evaluation.verdict for evaluation in symbol_evaluations)
            final_verdict = sorted(
                counts,
                key=lambda verdict: (counts[verdict], FINAL_VERDICT_PRIORITY.get(verdict, 0)),
                reverse=True,
            )[0]
            for evaluation in symbol_evaluations:
                if evaluation.verdict == final_verdict:
                    agreement_hits += 1
                linked_review = next(
                    (review for candidate, review in linked_pairs if candidate.id == evaluation.id),
                    None,
                )
                if linked_review and evaluation.confidence is not None:
                    realized = 100.0 if (linked_review.return_pct or 0.0) > 0 else 0.0
                    calibration_scores.append(max(0.0, 100.0 - abs(evaluation.confidence * 100.0 - realized)))

        agreement_rate = agreement_hits / total_evaluations if total_evaluations else None
        calibration_score = (
            sum(calibration_scores) / len(calibration_scores) if calibration_scores else None
        )
        entry_quality_score = self._score_entry_quality(linked_pairs)
        risk_judgment_score = self._score_risk_judgment(linked_pairs)
        exit_timing_score = self._score_exit_timing(agent_name, linked_pairs)
        alert_discipline_score = self._score_alert_discipline(linked_pairs)
        strengths, weaknesses = self._summarize_scorecard(
            win_rate,
            avg_return,
            agreement_rate,
            calibration_score,
            entry_quality_score,
            risk_judgment_score,
            exit_timing_score,
            alert_discipline_score,
        )

        last_evaluation_at = max((evaluation.created_at for evaluation in evaluations), default=None)
        return JennyAgentScorecard(
            agent_name=agent_name,
            total_evaluations=total_evaluations,
            completed_reviews=completed_reviews,
            positive_verdicts=positive_verdicts,
            win_rate=win_rate,
            avg_return_pct=avg_return,
            agreement_rate=agreement_rate,
            calibration_score=calibration_score,
            entry_quality_score=entry_quality_score,
            risk_judgment_score=risk_judgment_score,
            exit_timing_score=exit_timing_score,
            alert_discipline_score=alert_discipline_score,
            strengths=strengths,
            weaknesses=weaknesses,
            last_evaluation_at=last_evaluation_at,
            updated_at=datetime.now(UTC).isoformat(),
        )

    def _summarize_scorecard(
        self,
        win_rate: float | None,
        avg_return: float | None,
        agreement_rate: float | None,
        calibration_score: float | None,
        entry_quality_score: float | None,
        risk_judgment_score: float | None,
        exit_timing_score: float | None,
        alert_discipline_score: float | None,
    ) -> tuple[list[str], list[str]]:
        strengths: list[str] = []
        weaknesses: list[str] = []

        if win_rate is not None and win_rate >= 0.55:
            strengths.append("Its reviewed symbols have produced more winners than losers.")
        elif win_rate is not None:
            weaknesses.append("Its reviewed symbols have not cleared a strong win rate yet.")

        if avg_return is not None and avg_return > 5:
            strengths.append("The average reviewed outcome has produced meaningful upside.")
        elif avg_return is not None and avg_return < 0:
            weaknesses.append("Average reviewed outcomes are still negative.")

        if agreement_rate is not None and agreement_rate >= 0.6:
            strengths.append("It usually aligns with the final multi-agent verdict.")
        elif agreement_rate is not None:
            weaknesses.append("It frequently disagrees with the rest of the Jenny stack.")

        if calibration_score is not None and calibration_score >= 70:
            strengths.append("Its confidence has been reasonably calibrated to outcomes.")
        elif calibration_score is not None:
            weaknesses.append("Its confidence has been poorly calibrated to outcomes.")

        if entry_quality_score is not None and entry_quality_score >= 65:
            strengths.append("Its entry calls have lined up well with later trade outcomes.")
        elif entry_quality_score is not None and entry_quality_score < 45:
            weaknesses.append("Its entry calls have been too noisy versus realized outcomes.")

        if risk_judgment_score is not None and risk_judgment_score >= 70:
            strengths.append("It has done a good job flagging when risk should matter more than conviction.")
        elif risk_judgment_score is not None and risk_judgment_score < 50:
            weaknesses.append("It has been late to respect downside risk when trades weaken.")

        if exit_timing_score is not None and exit_timing_score >= 70:
            strengths.append("Its exit and trim instincts have been timely enough to trust more.")
        elif exit_timing_score is not None and exit_timing_score < 50:
            weaknesses.append("Its exit timing still needs work before it should drive sells.")

        if alert_discipline_score is not None and alert_discipline_score >= 65:
            strengths.append("Its alerts have usually been selective instead of noisy.")
        elif alert_discipline_score is not None and alert_discipline_score < 45:
            weaknesses.append("It still throws too many confident alerts that do not age well.")

        if not strengths:
            strengths.append("Jenny is still gathering enough history to judge this agent fairly.")
        if not weaknesses:
            weaknesses.append("No persistent weakness stands out from the current sample.")

        return strengths[:3], weaknesses[:3]

    def _save_scorecard(self, scorecard: JennyAgentScorecard) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO jenny_agent_scorecards (
                    agent_name, total_evaluations, completed_reviews, positive_verdicts,
                    win_rate, avg_return_pct, agreement_rate, calibration_score,
                    entry_quality_score, risk_judgment_score, exit_timing_score, alert_discipline_score,
                    strengths, weaknesses, last_evaluation_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s
                )
                ON CONFLICT (agent_name) DO UPDATE SET
                    total_evaluations = EXCLUDED.total_evaluations,
                    completed_reviews = EXCLUDED.completed_reviews,
                    positive_verdicts = EXCLUDED.positive_verdicts,
                    win_rate = EXCLUDED.win_rate,
                    avg_return_pct = EXCLUDED.avg_return_pct,
                    agreement_rate = EXCLUDED.agreement_rate,
                    calibration_score = EXCLUDED.calibration_score,
                    entry_quality_score = EXCLUDED.entry_quality_score,
                    risk_judgment_score = EXCLUDED.risk_judgment_score,
                    exit_timing_score = EXCLUDED.exit_timing_score,
                    alert_discipline_score = EXCLUDED.alert_discipline_score,
                    strengths = EXCLUDED.strengths,
                    weaknesses = EXCLUDED.weaknesses,
                    last_evaluation_at = EXCLUDED.last_evaluation_at,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    scorecard.agent_name,
                    scorecard.total_evaluations,
                    scorecard.completed_reviews,
                    scorecard.positive_verdicts,
                    scorecard.win_rate,
                    scorecard.avg_return_pct,
                    scorecard.agreement_rate,
                    scorecard.calibration_score,
                    scorecard.entry_quality_score,
                    scorecard.risk_judgment_score,
                    scorecard.exit_timing_score,
                    scorecard.alert_discipline_score,
                    json.dumps(scorecard.strengths),
                    json.dumps(scorecard.weaknesses),
                    scorecard.last_evaluation_at,
                    scorecard.updated_at,
                ],
            )
            conn.commit()

    def _get_recent_routines(self, limit: int = 6) -> list[JennyRoutine]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_type, status, triggered_by, summary, agents_used, symbols_scanned,
                       notifications_created, started_at, completed_at, metadata
                FROM jenny_routines
                ORDER BY started_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [self._row_to_routine(row) for row in rows]

    def _get_routine(self, routine_id: str) -> JennyRoutine:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, routine_type, status, triggered_by, summary, agents_used, symbols_scanned,
                       notifications_created, started_at, completed_at, metadata
                FROM jenny_routines
                WHERE id = %s
                """,
                [routine_id],
            ).fetchone()
        if row is None:
            raise RuntimeError(f"Jenny routine {routine_id} not found")
        return self._row_to_routine(row)

    def _get_open_notifications(self, limit: int = 12) -> list[JennyNotification]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_id, symbol, category, severity, status, title, detail,
                       recommendation, created_at, acknowledged_at, metadata
                FROM jenny_notifications
                WHERE status = 'open'
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'warning' THEN 1
                        ELSE 2
                    END,
                    created_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def _get_notification(self, notification_id: str) -> JennyNotification | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id, routine_id, symbol, category, severity, status, title, detail,
                       recommendation, created_at, acknowledged_at, metadata
                FROM jenny_notifications
                WHERE id = %s
                """,
                [notification_id],
            ).fetchone()
        return self._row_to_notification(row) if row else None

    def _get_latest_symbol_reviews(self, limit: int = 8) -> list[JennySymbolReview]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                WITH latest_symbol_routines AS (
                    SELECT DISTINCT ON (symbol)
                        symbol,
                        routine_id,
                        created_at
                    FROM jenny_agent_evaluations
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                    ORDER BY symbol, created_at DESC
                )
                SELECT e.id, e.routine_id, e.symbol, e.agent_name, e.provider, e.model, e.verdict, e.confidence,
                       e.rationale, e.recommendation, e.strengths, e.weaknesses, e.metadata, e.thesis_id,
                       e.agent_run_id, e.created_at
                FROM jenny_agent_evaluations e
                JOIN latest_symbol_routines lsr
                  ON lsr.symbol = e.symbol
                 AND lsr.routine_id = e.routine_id
                ORDER BY lsr.created_at DESC, e.created_at DESC
                LIMIT %s
                """,
                [limit * len(AGENT_SPECS) * 2],
            ).fetchall()
        evaluations = [self._row_to_evaluation(row) for row in rows]
        latest_routine_by_symbol: dict[str, str] = {}
        for evaluation in evaluations:
            latest_routine_by_symbol.setdefault(evaluation.symbol, evaluation.routine_id)

        grouped: dict[str, list[JennyAgentEvaluation]] = defaultdict(list)
        for evaluation in evaluations:
            if latest_routine_by_symbol.get(evaluation.symbol) != evaluation.routine_id:
                continue
            grouped[evaluation.symbol].append(evaluation)
        reviews = [
            self._aggregate_symbol_review(symbol, symbol_evaluations, self.thesis_service.get_thesis(symbol))
            for symbol, symbol_evaluations in grouped.items()
        ]
        action_map = self._build_position_action_map({review.symbol: review for review in reviews})
        for review in reviews:
            action = action_map.get(review.symbol)
            if action:
                review.management_action = action["action"]
                review.management_detail = action["detail"]
                review.position_gain_pct = action.get("gain_pct")
                review.position_weight_pct = action.get("weight_pct")
        return reviews[:limit]

    def _aggregate_symbol_review(
        self,
        symbol: str,
        evaluations: list[dict[str, Any]] | list[JennyAgentEvaluation],
        thesis: Thesis | None,
    ) -> JennySymbolReview:
        normalized: list[JennyAgentEvaluation] = []
        for evaluation in evaluations:
            if isinstance(evaluation, JennyAgentEvaluation):
                normalized.append(evaluation)
            else:
                normalized.append(
                    JennyAgentEvaluation(
                        id=str(uuid.uuid4()),
                        routine_id="transient",
                        symbol=symbol,
                        agent_name=str(evaluation["agent_name"]),
                        provider=evaluation.get("provider"),
                        model=evaluation.get("model"),
                        verdict=str(evaluation["verdict"]),
                        confidence=evaluation.get("confidence"),
                        rationale=str(evaluation["rationale"]),
                        recommendation=evaluation.get("recommendation"),
                        strengths=list(evaluation.get("strengths", [])),
                        weaknesses=list(evaluation.get("weaknesses", [])),
                        thesis_id=thesis.id if thesis else None,
                        agent_run_id=evaluation.get("agent_run_id"),
                        created_at=datetime.now(UTC).isoformat(),
                        metadata=evaluation.get("metadata", {}),
                    )
                )

        verdict_counts = Counter(evaluation.verdict for evaluation in normalized)
        final_verdict = sorted(
            verdict_counts,
            key=lambda verdict: (verdict_counts[verdict], FINAL_VERDICT_PRIORITY.get(verdict, 0)),
            reverse=True,
        )[0] if verdict_counts else "review"
        confidences = [evaluation.confidence for evaluation in normalized if evaluation.confidence is not None]
        reasons = [evaluation.rationale for evaluation in normalized[:3]]

        return JennySymbolReview(
            symbol=symbol,
            final_verdict=final_verdict,
            average_confidence=(sum(confidences) / len(confidences)) if confidences else None,
            thesis_status=thesis.status.value if thesis else None,
            thesis_action=thesis.action.value if thesis else None,
            management_action=None,
            management_detail=None,
            position_gain_pct=None,
            position_weight_pct=None,
            reasons=reasons,
            evaluations=normalized,
        )

    def _get_recent_trade_reviews(self, limit: int = 12) -> list[JennyTradeReview]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, symbol, thesis_id, idea_id, review_source, outcome_label,
                       return_pct, lesson, what_worked, what_failed, next_time,
                       created_at, updated_at, agent_consensus, metadata
                FROM jenny_trade_reviews
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()
        return [self._row_to_trade_review(row) for row in rows]

    def _get_scorecards(self) -> list[JennyAgentScorecard]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT agent_name, total_evaluations, completed_reviews, positive_verdicts,
                       win_rate, avg_return_pct, agreement_rate, calibration_score,
                       entry_quality_score, risk_judgment_score, exit_timing_score, alert_discipline_score,
                       strengths, weaknesses, last_evaluation_at, updated_at
                FROM jenny_agent_scorecards
                ORDER BY
                    COALESCE(entry_quality_score, win_rate * 100, 0) DESC,
                    COALESCE(avg_return_pct, 0) DESC
                """
            ).fetchall()
        return [self._row_to_scorecard(row) for row in rows]

    def _fetch_all_evaluations(self) -> list[JennyAgentEvaluation]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, routine_id, symbol, agent_name, provider, model, verdict, confidence,
                       rationale, recommendation, strengths, weaknesses, metadata, thesis_id,
                       agent_run_id, created_at
                FROM jenny_agent_evaluations
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._row_to_evaluation(row) for row in rows]

    def _row_to_routine(self, row: tuple[Any, ...]) -> JennyRoutine:
        return JennyRoutine(
            id=str(row[0]),
            routine_type=str(row[1]),
            status=str(row[2]),
            triggered_by=str(row[3]),
            summary=str(row[4]) if row[4] else None,
            agents_used=self._decode_json_value(row[5], []),
            symbols_scanned=int(row[6] or 0),
            notifications_created=int(row[7] or 0),
            started_at=self._iso(row[8]),
            completed_at=self._iso(row[9]) if row[9] else None,
            metadata=self._decode_json_value(row[10], {}),
        )

    def _row_to_evaluation(self, row: tuple[Any, ...]) -> JennyAgentEvaluation:
        return JennyAgentEvaluation(
            id=str(row[0]),
            routine_id=str(row[1]),
            symbol=str(row[2]),
            agent_name=str(row[3]),
            provider=str(row[4]) if row[4] else None,
            model=str(row[5]) if row[5] else None,
            verdict=str(row[6]),
            confidence=float(row[7]) if row[7] is not None else None,
            rationale=str(row[8]),
            recommendation=str(row[9]) if row[9] else None,
            strengths=self._decode_json_value(row[10], []),
            weaknesses=self._decode_json_value(row[11], []),
            metadata=self._decode_json_value(row[12], {}),
            thesis_id=str(row[13]) if row[13] else None,
            agent_run_id=str(row[14]) if row[14] else None,
            created_at=self._iso(row[15]),
        )

    def _row_to_notification(self, row: tuple[Any, ...]) -> JennyNotification:
        return JennyNotification(
            id=str(row[0]),
            routine_id=str(row[1]) if row[1] else None,
            symbol=str(row[2]) if row[2] else None,
            category=str(row[3]),
            severity=str(row[4]),
            status=str(row[5]),
            title=str(row[6]),
            detail=str(row[7]),
            recommendation=str(row[8]) if row[8] else None,
            created_at=self._iso(row[9]),
            acknowledged_at=self._iso(row[10]) if row[10] else None,
            metadata=self._decode_json_value(row[11], {}),
        )

    def _row_to_trade_review(self, row: tuple[Any, ...]) -> JennyTradeReview:
        return JennyTradeReview(
            id=str(row[0]),
            symbol=str(row[1]),
            thesis_id=str(row[2]) if row[2] else None,
            idea_id=str(row[3]) if row[3] else None,
            review_source=str(row[4]),
            outcome_label=str(row[5]),
            return_pct=float(row[6]) if row[6] is not None else None,
            lesson=str(row[7]),
            what_worked=str(row[8]) if row[8] else None,
            what_failed=str(row[9]) if row[9] else None,
            next_time=str(row[10]) if row[10] else None,
            created_at=self._iso(row[11]),
            updated_at=self._iso(row[12]),
            agent_consensus=self._decode_json_value(row[13], {}),
            metadata=self._decode_json_value(row[14], {}),
        )

    def _row_to_scorecard(self, row: tuple[Any, ...]) -> JennyAgentScorecard:
        return JennyAgentScorecard(
            agent_name=str(row[0]),
            total_evaluations=int(row[1] or 0),
            completed_reviews=int(row[2] or 0),
            positive_verdicts=int(row[3] or 0),
            win_rate=float(row[4]) if row[4] is not None else None,
            avg_return_pct=float(row[5]) if row[5] is not None else None,
            agreement_rate=float(row[6]) if row[6] is not None else None,
            calibration_score=float(row[7]) if row[7] is not None else None,
            entry_quality_score=float(row[8]) if row[8] is not None else None,
            risk_judgment_score=float(row[9]) if row[9] is not None else None,
            exit_timing_score=float(row[10]) if row[10] is not None else None,
            alert_discipline_score=float(row[11]) if row[11] is not None else None,
            strengths=self._decode_json_value(row[12], []),
            weaknesses=self._decode_json_value(row[13], []),
            last_evaluation_at=self._iso(row[14]) if row[14] else None,
            updated_at=self._iso(row[15]),
        )

    def _build_position_action_map(
        self,
        review_map: dict[str, JennySymbolReview],
    ) -> dict[str, dict[str, Any]]:
        if not review_map or not hasattr(self, "portfolio_mgr") or not hasattr(self, "price_fetcher"):
            return {}

        positions = [
            position
            for position in self.portfolio_mgr.get_positions()
            if position.position_type != "paper" and position.symbol in review_map
        ]
        if not positions:
            return {}

        price_data = self.price_fetcher.fetch_price_data([position.symbol for position in positions])
        performances = {
            performance.symbol: performance
            for performance in calculate_position_performances(positions, price_data)
        }
        action_map: dict[str, dict[str, Any]] = {}
        for position in positions:
            performance = performances.get(position.symbol)
            if performance is None:
                continue
            thesis = self.thesis_service.get_thesis(position.symbol)
            invalidation_triggers = self.thesis_service.check_invalidation_triggers(position.symbol) if thesis else []
            action_map[position.symbol] = self._get_position_action(
                symbol=position.symbol,
                gain_pct=performance.gain_pct,
                weight_pct=performance.weight_pct,
                thesis=thesis,
                invalidation_triggers=invalidation_triggers,
                aggregated_review=review_map[position.symbol],
            )
        return action_map

    def _get_position_action(
        self,
        symbol: str,
        gain_pct: float,
        weight_pct: float,
        thesis: Thesis | None,
        invalidation_triggers: list[str],
        aggregated_review: Any,
    ) -> dict[str, Any]:
        if invalidation_triggers:
            return {
                "action": "exit",
                "severity": "critical",
                "title": f"{symbol}: Exit this position",
                "detail": " ".join(invalidation_triggers),
                "recommendation": "Sell or reduce immediately unless you have a very specific reason to ignore the break.",
                "gain_pct": gain_pct,
                "weight_pct": weight_pct,
            }
        if aggregated_review.final_verdict == "exit":
            return {
                "action": "exit",
                "severity": "critical",
                "title": f"{symbol}: Exit this position",
                "detail": " ".join(aggregated_review.reasons) or f"Jenny thinks {symbol} should come out of the portfolio.",
                "recommendation": aggregated_review.evaluations[0].recommendation if aggregated_review.evaluations else "Review why the trade no longer belongs in the portfolio.",
                "gain_pct": gain_pct,
                "weight_pct": weight_pct,
            }
        if gain_pct >= 20 and weight_pct >= 15:
            return {
                "action": "trim",
                "severity": "warning",
                "title": f"{symbol}: Trim this position",
                "detail": f"{symbol} is up {gain_pct:.1f}% and now makes up {weight_pct:.1f}% of the portfolio.",
                "recommendation": "Take partial profits so one winner does not become oversized.",
                "gain_pct": gain_pct,
                "weight_pct": weight_pct,
            }
        if weight_pct >= 18:
            return {
                "action": "de_risk",
                "severity": "warning",
                "title": f"{symbol}: De-risk this position",
                "detail": f"{symbol} now represents {weight_pct:.1f}% of the portfolio, which is more concentration than Jenny wants for one idea.",
                "recommendation": "Scale it back to a size you can tolerate.",
                "gain_pct": gain_pct,
                "weight_pct": weight_pct,
            }
        if gain_pct <= -8 or aggregated_review.final_verdict == "review":
            thesis_hint = "The thesis is missing." if thesis is None else "The thesis needs a fresh check."
            return {
                "action": "review",
                "severity": "warning",
                "title": f"{symbol}: Recheck this position",
                "detail": f"{symbol} is down {abs(gain_pct):.1f}% from cost basis. {thesis_hint}",
                "recommendation": "Review the thesis before adding or deciding to hold through more weakness.",
                "gain_pct": gain_pct,
                "weight_pct": weight_pct,
            }
        return {
            "action": "hold",
            "severity": "info",
            "title": f"{symbol}: Hold steady",
            "detail": "Nothing in the current position data or thesis says you need to act right now.",
            "recommendation": "Do nothing unless new facts change the thesis.",
            "gain_pct": gain_pct,
            "weight_pct": weight_pct,
        }

    def _link_evaluations_to_reviews(
        self,
        evaluations: list[JennyAgentEvaluation],
        reviews_by_symbol: dict[str, list[JennyTradeReview]],
    ) -> list[tuple[JennyAgentEvaluation, JennyTradeReview]]:
        linked: list[tuple[JennyAgentEvaluation, JennyTradeReview]] = []
        for evaluation in evaluations:
            reviews = reviews_by_symbol.get(evaluation.symbol, [])
            if not reviews:
                continue
            evaluation_at = self._parse_timestamp(evaluation.created_at)
            sorted_reviews = sorted(reviews, key=lambda review: self._parse_timestamp(review.created_at))
            review = next(
                (
                    candidate
                    for candidate in sorted_reviews
                    if self._parse_timestamp(candidate.created_at) >= evaluation_at
                ),
                sorted_reviews[-1],
            )
            linked.append((evaluation, review))
        return linked

    def _score_entry_quality(
        self,
        linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    ) -> float | None:
        scores: list[float] = []
        for evaluation, review in linked_pairs:
            return_pct = review.return_pct
            if return_pct is None:
                continue
            if return_pct == 0:
                scores.append(50.0)
                continue
            directional_positive = return_pct > 0
            verdict_positive = evaluation.verdict in POSITIVE_VERDICTS
            scores.append(100.0 if directional_positive == verdict_positive else 0.0)
        return sum(scores) / len(scores) if scores else None

    def _score_risk_judgment(
        self,
        linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    ) -> float | None:
        risk_scores = {
            "buy": {True: 100.0, False: 0.0},
            "hold": {True: 85.0, False: 20.0},
            "review": {True: 55.0, False: 80.0},
            "trim": {True: 75.0, False: 90.0},
            "exit": {True: 45.0, False: 100.0},
            "avoid": {True: 20.0, False: 90.0},
        }
        scores = [
            risk_scores.get(evaluation.verdict, {True: 50.0, False: 50.0})[(review.return_pct or 0.0) > 0]
            for evaluation, review in linked_pairs
            if review.return_pct is not None
        ]
        return sum(scores) / len(scores) if scores else None

    def _score_exit_timing(
        self,
        agent_name: str,
        linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    ) -> float | None:
        exit_scores = {
            "buy": {True: 100.0, False: 0.0},
            "hold": {True: 100.0, False: 20.0},
            "review": {True: 70.0, False: 80.0},
            "trim": {True: 95.0, False: 90.0},
            "exit": {True: 90.0, False: 100.0},
            "avoid": {True: 35.0, False: 85.0},
        }
        scores: list[float] = []
        for evaluation, review in linked_pairs:
            if review.return_pct is None:
                continue
            consensus_verdicts = review.agent_consensus.get("agent_verdicts", {})
            verdict = str(consensus_verdicts.get(agent_name, evaluation.verdict))
            scores.append(exit_scores.get(verdict, {True: 50.0, False: 50.0})[(review.return_pct or 0.0) > 0])
        return sum(scores) / len(scores) if scores else None

    def _score_alert_discipline(
        self,
        linked_pairs: list[tuple[JennyAgentEvaluation, JennyTradeReview]],
    ) -> float | None:
        scores: list[float] = []
        for evaluation, review in linked_pairs:
            if review.return_pct is None:
                continue
            confidence = evaluation.confidence if evaluation.confidence is not None else 0.5
            directional_positive = (review.return_pct or 0.0) > 0
            verdict_positive = evaluation.verdict in POSITIVE_VERDICTS
            if directional_positive == verdict_positive:
                scores.append(100.0)
            else:
                scores.append(max(0.0, 75.0 - confidence * 100.0))
        return sum(scores) / len(scores) if scores else None

    def _parse_timestamp(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _decode_json_value(self, value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return default

    def _iso(self, value: Any) -> str:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
