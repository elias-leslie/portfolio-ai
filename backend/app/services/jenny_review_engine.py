"""Review execution and notification helpers for Jenny routines."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger
from app.models.thesis import Thesis
from app.services._jenny_position_actions import build_position_action_map, get_position_action
from app.services._jenny_review_context import (
    build_symbol_context,
    fallback_evaluation,
    should_use_insufficient_evidence_fallback,
)
from app.services._jenny_review_notifications import (
    create_notifications,
    extract_invalidation_triggers,
    extract_symbol_profile,
    upsert_notification,
)
from app.services._jenny_review_parser import (
    build_agent_prompt,
    normalize_confidence,
    normalize_verdict,
    parse_agent_response,
)

logger = get_logger(__name__)


class JennyReviewEngine:
    """Run Jenny agent reviews and convert them into notifications."""

    # --- symbol evaluation ---

    def evaluate_symbol(
        self,
        service: Any,
        *,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        routine_id: str,
        workflow_id: str,
        symbol_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not AGENT_HUB_ENABLED or self.should_use_insufficient_evidence_fallback(
            thesis, symbol_profile, service
        ):
            return [self.fallback_evaluation(symbol, thesis, service=service, symbol_profile=symbol_profile)]

        payload = self.build_symbol_context(service, symbol, thesis, price_data, symbol_profile)
        payload["routine_id"] = routine_id
        payload["workflow_id"] = workflow_id
        return [self.run_agent_review(service, spec, payload) for spec in service.AGENT_SPECS]

    def should_use_insufficient_evidence_fallback(
        self,
        thesis: Thesis | None,
        symbol_profile: dict[str, Any],
        service: Any,
    ) -> bool:
        return should_use_insufficient_evidence_fallback(
            thesis, symbol_profile, service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT
        )

    def build_symbol_context(
        self,
        service: Any,
        symbol: str,
        thesis: Thesis | None,
        price_data: Any,
        symbol_profile: dict[str, Any],
    ) -> dict[str, Any]:
        invalidation_triggers = (
            service.thesis_service.check_invalidation_triggers(symbol) if thesis else []
        )
        return build_symbol_context(
            symbol,
            thesis,
            price_data,
            symbol_profile,
            service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT,
            invalidation_triggers,
        )

    # --- agent execution ---

    def run_agent_review(self, service: Any, spec: Any, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        client_cls = (
            service._agent_hub_client_class() if hasattr(service, "_agent_hub_client_class") else AgentHubAPIClient
        )
        client = client_cls(agent_slug=spec.agent_slug)
        prompt = self.build_agent_prompt(spec.prompt_mode, payload)
        service.agent_run_repo.create_run(
            run_id=run_id,
            agent_type=f"jenny_{spec.agent_slug}",
            model=client.get_model_name(),
            started_at=started_at,
            provider=client.provider,
            run_type="automated",
            workflow_id=str(payload["workflow_id"]),
        )
        service.agent_run_repo.store_message(run_id, "user", prompt)
        try:
            return self._execute_agent_call(service, client, spec, payload, prompt, run_id, started_at)
        finally:
            client.close()

    def _execute_agent_call(
        self,
        service: Any,
        client: Any,
        spec: Any,
        payload: dict[str, Any],
        prompt: str,
        run_id: str,
        started_at: datetime,
    ) -> dict[str, Any]:
        try:
            response = client.generate(prompt=prompt, system=spec.system_prompt, purpose=f"jenny:{spec.agent_slug}")
            service.agent_run_repo.store_message(run_id, "assistant", response.content)
            parsed = self.parse_agent_response(response.content, spec.agent_slug)
            parsed.setdefault("metadata", {})
            parsed["metadata"]["symbol_profile"] = {
                "security_type": payload.get("security_type"),
                "is_passive_fund": payload.get("review_mode") == "allocation",
                "data_quality_pct": payload.get("data_quality_pct"),
            }
            parsed["metadata"]["invalidation_triggers"] = list(payload.get("invalidation_triggers") or [])
            parsed["provider"] = response.provider
            parsed["model"] = response.model
            parsed["agent_run_id"] = run_id
            service.agent_run_repo.complete_run(
                run_id=run_id,
                completed_at=datetime.now(UTC),
                status="completed",
                num_ideas=0,
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                token_usage=response.usage,
            )
            return parsed
        except Exception as exc:
            service.agent_run_repo.complete_run(
                run_id=run_id,
                completed_at=datetime.now(UTC),
                status="error",
                num_ideas=0,
                error_message=str(exc),
                duration_ms=int((datetime.now(UTC) - started_at).total_seconds() * 1000),
            )
            logger.warning("jenny_agent_review_failed", agent=spec.agent_slug, error=str(exc))
            return self.fallback_evaluation(
                payload["symbol"],
                None,
                service=service,
                agent_name=spec.agent_slug,
                symbol_profile=dict(payload.get("symbol_profile") or {}),
            )

    # --- parsing and normalization (thin delegates) ---

    def build_agent_prompt(self, mode: str, payload: dict[str, Any]) -> str:
        return build_agent_prompt(mode, payload)

    def normalize_confidence(self, raw_confidence: Any) -> float | None:
        return normalize_confidence(raw_confidence)

    def normalize_verdict(self, raw_verdict: Any) -> str:
        return normalize_verdict(raw_verdict)

    def parse_agent_response(self, content: str, agent_name: str) -> dict[str, Any]:
        return parse_agent_response(content, agent_name)

    # --- fallback ---

    def fallback_evaluation(
        self,
        symbol: str,
        thesis: Thesis | None,
        *,
        service: Any,
        agent_name: str = "fallback_operator",
        symbol_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return fallback_evaluation(
            symbol,
            thesis,
            agent_name=agent_name,
            symbol_profile=symbol_profile,
            min_data_quality_pct=service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT,
        )

    # --- notifications ---

    def create_notifications(
        self,
        service: Any,
        *,
        routine_id: str,
        live_symbols: set[str],
        evaluations_by_symbol: dict[str, list[dict[str, Any]]],
    ) -> int:
        return create_notifications(
            service,
            routine_id=routine_id,
            live_symbols=live_symbols,
            evaluations_by_symbol=evaluations_by_symbol,
        )

    def extract_symbol_profile(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        return extract_symbol_profile(evaluations)

    def extract_invalidation_triggers(self, evaluations: list[dict[str, Any]]) -> list[str]:
        return extract_invalidation_triggers(evaluations)

    def upsert_notification(
        self,
        service: Any,
        routine_id: str,
        symbol: str | None,
        *,
        category: str,
        severity: str,
        title: str,
        detail: str,
        recommendation: str | None,
    ) -> None:
        upsert_notification(
            service,
            routine_id,
            symbol,
            category=category,
            severity=severity,
            title=title,
            detail=detail,
            recommendation=recommendation,
        )

    # --- position actions ---

    def build_position_action_map(
        self,
        service: Any,
        review_map: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return build_position_action_map(service, review_map)

    def get_position_action(
        self,
        service: Any,
        *,
        symbol: str,
        gain_pct: float,
        weight_pct: float,
        thesis: Thesis | None,
        invalidation_triggers: list[str],
        aggregated_review: Any,
    ) -> dict[str, Any]:
        return get_position_action(
            symbol=symbol,
            gain_pct=gain_pct,
            weight_pct=weight_pct,
            thesis=thesis,
            invalidation_triggers=invalidation_triggers,
            aggregated_review=aggregated_review,
        )
