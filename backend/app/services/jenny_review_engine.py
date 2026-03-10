"""Review execution and notification helpers for Jenny routines."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger
from app.models.thesis import Thesis
from app.portfolio.analytics_returns import calculate_position_performances

logger = get_logger(__name__)


class JennyReviewEngine:
    """Run Jenny agent reviews and convert them into notifications."""

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
        if thesis is not None:
            return False
        data_quality_pct = symbol_profile.get("data_quality_pct")
        return (
            data_quality_pct is not None
            and data_quality_pct < service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT
        )

    def build_symbol_context(
        self,
        service: Any,
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
            "symbol_profile": symbol_profile,
            "review_mode": "allocation" if is_passive_fund else "thesis",
            "data_quality_pct": data_quality_pct,
            "evidence_status": (
                "thin"
                if data_quality_pct is not None
                and data_quality_pct < service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT
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
            "invalidation_triggers": service.thesis_service.check_invalidation_triggers(symbol)
            if thesis
            else [],
        }

    def run_agent_review(self, service: Any, spec: Any, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        client_cls = (
            service._agent_hub_client_class() if hasattr(service, "_agent_hub_client_class") else AgentHubAPIClient
        )
        client = client_cls(
            agent_slug=spec.agent_slug,
            timeout=service.JENNY_AGENT_TIMEOUT_SECONDS,
        )
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
            response = client.generate(
                prompt=prompt,
                system=spec.system_prompt,
                purpose=f"jenny:{spec.agent_slug}",
            )
            service.agent_run_repo.store_message(run_id, "assistant", response.content)
            parsed = self.parse_agent_response(response.content, spec.agent_slug)
            parsed.setdefault("metadata", {})
            parsed["metadata"]["symbol_profile"] = {
                "security_type": payload.get("security_type"),
                "is_passive_fund": payload.get("review_mode") == "allocation",
                "data_quality_pct": payload.get("data_quality_pct"),
            }
            parsed["metadata"]["invalidation_triggers"] = list(
                payload.get("invalidation_triggers") or []
            )
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
        finally:
            client.close()

    def build_agent_prompt(self, mode: str, payload: dict[str, Any]) -> str:
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

    def normalize_confidence(self, raw_confidence: Any) -> float | None:
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

    def normalize_verdict(self, raw_verdict: Any) -> str:
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

    def parse_agent_response(self, content: str, agent_name: str) -> dict[str, Any]:
        try:
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0].strip()
            elif "{" in content and "}" in content:
                content = content[content.index("{") : content.rindex("}") + 1]
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
            "verdict": self.normalize_verdict(parsed.get("verdict", "review")),
            "confidence": self.normalize_confidence(parsed.get("confidence", 0.5)),
            "rationale": str(parsed.get("rationale") or "No rationale provided."),
            "recommendation": (
                str(parsed.get("recommendation")) if parsed.get("recommendation") else None
            ),
            "strengths": [str(item) for item in strengths][:5],
            "weaknesses": [str(item) for item in weaknesses][:5],
            "metadata": {"raw_response": parsed},
        }

    def fallback_evaluation(
        self,
        symbol: str,
        thesis: Thesis | None,
        *,
        service: Any,
        agent_name: str = "fallback_operator",
        symbol_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        verdict = "review"
        rationale = "Jenny could not reach Agent Hub, so this symbol needs manual review."
        recommendation = "Check the thesis and current price action before taking action."
        strengths = [
            "Existing thesis is still stored."
            if thesis
            else "Keeps the workflow running without fake certainty."
        ]
        weaknesses = ["Agent Hub unavailable, so confidence is limited."]
        profile = symbol_profile or {}
        data_quality_pct = profile.get("data_quality_pct")
        if (
            data_quality_pct is not None
            and data_quality_pct < service.MIN_AGENT_REVIEW_DATA_QUALITY_PCT
            and thesis is None
        ):
            rationale = "There is not enough fresh evidence to form a trustworthy review yet."
            recommendation = "Wait for fresher price, signal, and catalyst data before acting."
            strengths = ["Jenny avoided pretending the evidence was stronger than it is."]
            weaknesses = ["Fresh data is too thin for a trustworthy review right now."]
        elif profile.get("is_passive_fund") and thesis is None:
            rationale = (
                "This passive fund is being treated as an allocation review instead of a missing company thesis."
            )
            if profile.get("is_live_position"):
                recommendation = (
                    "Use portfolio weight, overlap, and cash needs to decide whether to hold or trim. "
                    "Avoid adding until the next review completes."
                )
            else:
                recommendation = (
                    "Review whether you still need this broad exposure in the watchlist before adding it."
                )
            strengths = [
                "Passive fund holdings do not require a single-company thesis to stay actionable."
            ]
            weaknesses = [
                "Fund reviews rely more on allocation and concentration than company-specific catalysts."
            ]
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
            "metadata": {
                "fallback": True,
                "symbol": symbol,
                "symbol_profile": profile,
                "invalidation_triggers": [],
            },
            "agent_run_id": None,
        }

    def create_notifications(
        self,
        service: Any,
        *,
        routine_id: str,
        live_symbols: set[str],
        evaluations_by_symbol: dict[str, list[dict[str, Any]]],
    ) -> int:
        count = 0
        review_map = {
            symbol: service._aggregate_symbol_review(
                symbol, evaluations, service.thesis_service.get_thesis(symbol)
            )
            for symbol, evaluations in evaluations_by_symbol.items()
        }
        position_actions = service._build_position_action_map(
            {symbol: review for symbol, review in review_map.items() if symbol in live_symbols}
        )
        for symbol, review in review_map.items():
            position_action = position_actions.get(symbol)
            evaluations = evaluations_by_symbol.get(symbol, [])
            if symbol in live_symbols and position_action and position_action["action"] != "hold":
                service._upsert_notification(
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
                service._upsert_notification(
                    routine_id,
                    symbol,
                    category=f"position_{review.final_verdict}",
                    severity="critical" if review.final_verdict == "exit" else "warning",
                    title=f"{symbol}: {review.final_verdict.title()} this position",
                    detail=" ".join(review.reasons)
                    or f"Jenny wants you to {review.final_verdict} {symbol}.",
                    recommendation=review.evaluations[0].recommendation if review.evaluations else None,
                )
                count += 1
            if (
                symbol not in live_symbols
                and review.final_verdict == "buy"
                and (review.average_confidence or 0) >= 0.7
            ):
                service._upsert_notification(
                    routine_id,
                    symbol,
                    category="watchlist_buy_candidate",
                    severity="info",
                    title=f"{symbol}: high-conviction setup",
                    detail=" ".join(review.reasons)
                    or f"Jenny flagged {symbol} as a vetted setup.",
                    recommendation=review.evaluations[0].recommendation if review.evaluations else None,
                )
                count += 1

            thesis = service.thesis_service.get_thesis(symbol)
            invalidation_triggers = service._extract_invalidation_triggers(evaluations)
            profile = service._extract_symbol_profile(evaluations)
            if invalidation_triggers and not (position_action and position_action["action"] == "exit"):
                service._upsert_notification(
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
                service._upsert_notification(
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

    def extract_symbol_profile(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        for evaluation in evaluations:
            profile = (evaluation.get("metadata") or {}).get("symbol_profile")
            if isinstance(profile, dict):
                return profile
        return {}

    def extract_invalidation_triggers(self, evaluations: list[dict[str, Any]]) -> list[str]:
        for evaluation in evaluations:
            raw_triggers = (evaluation.get("metadata") or {}).get("invalidation_triggers")
            if isinstance(raw_triggers, list):
                return [str(trigger) for trigger in raw_triggers if trigger]
        return []

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
        with service.storage.connection() as conn:
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
                    [
                        routine_id,
                        severity,
                        title,
                        detail,
                        recommendation,
                        datetime.now(UTC).isoformat(),
                        str(existing[0]),
                    ],
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

    def build_position_action_map(
        self,
        service: Any,
        review_map: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        if not review_map or not hasattr(service, "portfolio_mgr") or not hasattr(service, "price_fetcher"):
            return {}

        positions = [
            position
            for position in service.portfolio_mgr.get_positions()
            if position.position_type != "paper" and position.symbol in review_map
        ]
        if not positions:
            return {}

        price_data = service.price_fetcher.fetch_price_data([position.symbol for position in positions])
        performances = {
            performance.symbol: performance
            for performance in calculate_position_performances(positions, price_data)
        }
        action_map: dict[str, dict[str, Any]] = {}
        for position in positions:
            performance = performances.get(position.symbol)
            if performance is None:
                continue
            thesis = service.thesis_service.get_thesis(position.symbol)
            invalidation_triggers = (
                service.thesis_service.check_invalidation_triggers(position.symbol) if thesis else []
            )
            action_map[position.symbol] = self.get_position_action(
                service,
                symbol=position.symbol,
                gain_pct=performance.gain_pct,
                weight_pct=performance.weight_pct,
                thesis=thesis,
                invalidation_triggers=invalidation_triggers,
                aggregated_review=review_map[position.symbol],
            )
        return action_map

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
                "detail": " ".join(aggregated_review.reasons)
                or f"Jenny thinks {symbol} should come out of the portfolio.",
                "recommendation": (
                    aggregated_review.evaluations[0].recommendation
                    if aggregated_review.evaluations
                    else "Review why the trade no longer belongs in the portfolio."
                ),
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
