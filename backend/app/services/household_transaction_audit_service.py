"""Autonomous transaction audit for household accounting correctness."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger
from app.services.agent_hub_prompt_service import require_agent_hub_prompt
from app.services.household_review_agent_service import HOUSEHOLD_REVIEW_AGENT_SLUG
from app.services.household_transaction_service import (
    _effective_transaction_classification,
    _effective_transaction_flow,
)

logger = get_logger(__name__)

PROMPT_AUDIT_SYSTEM = "household-transaction-audit-system-prompt"
PROMPT_AUDIT_JSON_CONTRACT = "household-transaction-audit-json-contract"
PROMPT_MONEY_RULES = "financial-document-reviewer-money-rules"

_MAX_AGENT_CANDIDATES = 24
_HIGH_CONFIDENCE = 0.88
_MEDIUM_CONFIDENCE = 0.68
_SUSPICIOUS_TX_PATTERN = re.compile(
    r"(credit crd epay|payment thank you|inst xfer|online transfer|recurring transfer|"
    r"moneyline|zelle from|zelle to|ui benefit|payroll|payables|salary|atm withdrawal|"
    r"transfer from|transfer to|venmo|cash app|cashapp|refund|return|walmart|target|"
    r"costco|sam'?s club|publix|whole foods|buc-?ee)",
    re.IGNORECASE,
)


def _coerce_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_audit_payload(content: Any) -> dict[str, Any]:
    if isinstance(content, str):
        text = content
    else:
        text = str(content or "")
    text = text.strip()
    candidates: list[str] = []
    if text.startswith("{") and text.endswith("}"):
        candidates.append(text)
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("No valid JSON audit payload found.")


class HouseholdTransactionAuditService:
    """Audit stored household transactions and self-heal clear mistakes."""

    def audit_transactions(
        self,
        service: Any,
        *,
        document_id: str | None = None,
        limit: int = 240,
    ) -> dict[str, int]:
        candidates = self._load_candidates(service, document_id=document_id, limit=limit)
        if not candidates:
            return {
                "reviewed": 0,
                "auto_fixed": 0,
                "agent_fixed": 0,
                "flagged": 0,
                "merchant_rules_applied": 0,
            }

        auto_fixed = 0
        flagged = 0
        merchant_rules_applied = 0
        remaining: list[dict[str, Any]] = []

        for candidate in candidates:
            if self._apply_deterministic_fix(service, candidate):
                auto_fixed += 1
                continue
            if self._needs_agent(candidate):
                remaining.append(candidate)
                continue
            self._mark_reviewed(service, candidate)

        agent_fixed = 0
        if remaining and AGENT_HUB_ENABLED:
            try:
                decisions = self._run_agent_audit(service, remaining[:_MAX_AGENT_CANDIDATES])
            except Exception as exc:
                logger.warning("household_transaction_audit_agent_failed", error=str(exc))
                decisions = []
            decision_map = {
                str(item.get("transaction_id") or "").strip(): item
                for item in decisions
                if isinstance(item, dict) and str(item.get("transaction_id") or "").strip()
            }
            for candidate in remaining:
                decision = decision_map.get(candidate["id"])
                if decision is None:
                    self._flag_candidate(
                        service,
                        candidate,
                        reason="Agent did not return a decision. Needs review.",
                    )
                    flagged += 1
                    continue
                outcome, merchant_rule_applied = self._apply_agent_decision(
                    service,
                    candidate,
                    decision,
                )
                if outcome == "fixed":
                    agent_fixed += 1
                elif outcome == "flagged":
                    flagged += 1
                if merchant_rule_applied:
                    merchant_rules_applied += 1
        else:
            for candidate in remaining:
                self._flag_candidate(
                    service,
                    candidate,
                    reason="Classification ambiguity remains after deterministic audit.",
                )
                flagged += 1

        return {
            "reviewed": len(candidates),
            "auto_fixed": auto_fixed,
            "agent_fixed": agent_fixed,
            "flagged": flagged,
            "merchant_rules_applied": merchant_rules_applied,
        }

    def _load_candidates(
        self,
        service: Any,
        *,
        document_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where_sql = ""
        if document_id is not None:
            where_sql = "WHERE t.document_id = %s"
            params.append(document_id)
        else:
            where_sql = """
                WHERE t.transaction_date >= %s
                  AND (
                        COALESCE(t.confidence, 0) < 0.88
                     OR COALESCE(t.metadata->'audit'->>'status', '') = 'needs_review'
                     OR CONCAT_WS(' ', COALESCE(t.description, ''), COALESCE(t.raw_merchant, '')) ~* %s
                  )
            """
            params.extend(
                [
                    datetime.now(UTC) - timedelta(days=180),
                    _SUSPICIOUS_TX_PATTERN.pattern,
                ]
            )

        params.append(max(limit, 1))
        with service.storage.connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    t.id,
                    t.document_id,
                    t.merchant_id,
                    t.household_account_id,
                    t.transaction_date,
                    t.posted_date,
                    t.description,
                    COALESCE(m.canonical_name, t.raw_merchant, t.description) AS merchant,
                    t.raw_merchant,
                    CAST(t.amount AS DOUBLE PRECISION),
                    t.flow_type,
                    t.category,
                    t.essentiality,
                    t.confidence,
                    t.metadata,
                    COALESCE(m.metadata, '{{}}'::jsonb),
                    d.source_type,
                    d.document_type,
                    d.filename,
                    COALESCE(ta.label, a.canonical_label, t.account_label) AS account_label,
                    COALESCE(similar_txns.similar_count, 0) AS similar_count
                FROM household_transactions t
                LEFT JOIN household_merchants m
                  ON m.id = t.merchant_id
                LEFT JOIN household_documents d
                  ON d.id = t.document_id
                LEFT JOIN household_accounts a
                  ON a.id = t.household_account_id
                LEFT JOIN LATERAL (
                    SELECT label
                    FROM household_tracked_accounts ta
                    WHERE ta.household_account_id = t.household_account_id
                    ORDER BY ta.updated_at DESC
                    LIMIT 1
                ) ta ON TRUE
                LEFT JOIN (
                    SELECT merchant_id, COUNT(*) AS similar_count
                    FROM household_transactions
                    WHERE transaction_date >= CURRENT_DATE - INTERVAL '365 days'
                    GROUP BY merchant_id
                ) similar_txns ON similar_txns.merchant_id = t.merchant_id
                {where_sql}
                ORDER BY COALESCE(t.updated_at, t.created_at) DESC, t.transaction_date DESC
                LIMIT %s
                """,
                params,
            ).fetchall()

        candidates: list[dict[str, Any]] = []
        for row in rows:
            metadata = _coerce_metadata(row[14])
            merchant_metadata = _coerce_metadata(row[15])
            merchant = _normalize_text(row[7] or row[8] or row[6])
            description = _normalize_text(row[6])
            amount = float(row[9] or 0.0)
            stored_flow = _normalize_text(row[10]).lower() or "expense"
            stored_category = _normalize_text(row[11]) or "Household"
            stored_essentiality = _normalize_text(row[12]) or "mixed"
            resolved_flow = _effective_transaction_flow(
                flow_type=stored_flow,
                raw_merchant=merchant,
                description=description,
                source_type=_normalize_text(row[16]),
            )
            resolved_category, resolved_essentiality = _effective_transaction_classification(
                flow_type=resolved_flow,
                raw_merchant=merchant,
                description=description,
                amount=amount,
                stored_category=stored_category,
                stored_essentiality=stored_essentiality,
                merchant_metadata=merchant_metadata,
            )
            candidates.append(
                {
                    "id": str(row[0]),
                    "document_id": str(row[1]) if row[1] is not None else None,
                    "merchant_id": str(row[2]) if row[2] is not None else None,
                    "household_account_id": str(row[3]) if row[3] is not None else None,
                    "transaction_date": row[4].date().isoformat() if hasattr(row[4], "date") else str(row[4]),
                    "posted_date": row[5].date().isoformat() if hasattr(row[5], "date") else None,
                    "description": description,
                    "merchant": merchant,
                    "amount": amount,
                    "stored_flow_type": stored_flow,
                    "stored_category": stored_category,
                    "stored_essentiality": stored_essentiality,
                    "resolved_flow_type": resolved_flow,
                    "resolved_category": resolved_category,
                    "resolved_essentiality": resolved_essentiality,
                    "confidence": float(row[13] or 0.0),
                    "metadata": metadata,
                    "merchant_metadata": merchant_metadata,
                    "source_type": _normalize_text(row[16]),
                    "document_type": _normalize_text(row[17]),
                    "filename": _normalize_text(row[18]),
                    "account_label": _normalize_text(row[19]) or None,
                    "similar_count": int(row[20] or 0),
                }
            )
        return candidates

    def _needs_agent(self, candidate: dict[str, Any]) -> bool:
        merchant_metadata = candidate.get("merchant_metadata")
        if isinstance(merchant_metadata, dict) and isinstance(merchant_metadata.get("manual_rule"), dict):
            return False
        audit_metadata = candidate["metadata"].get("audit")
        if isinstance(audit_metadata, dict) and audit_metadata.get("status") == "needs_review":
            return True
        if candidate["stored_flow_type"] != candidate["resolved_flow_type"]:
            return True
        if candidate["stored_category"] != candidate["resolved_category"]:
            return True
        if candidate["stored_essentiality"] != candidate["resolved_essentiality"]:
            return True
        return candidate["confidence"] < 0.75

    def _apply_deterministic_fix(self, service: Any, candidate: dict[str, Any]) -> bool:
        merchant_metadata = candidate.get("merchant_metadata")
        if isinstance(merchant_metadata, dict) and isinstance(merchant_metadata.get("manual_rule"), dict):
            self._mark_reviewed(service, candidate)
            return False

        stored_flow = candidate["stored_flow_type"]
        stored_category = candidate["stored_category"]
        stored_essentiality = candidate["stored_essentiality"]
        resolved_flow = candidate["resolved_flow_type"]
        resolved_category = candidate["resolved_category"]
        resolved_essentiality = candidate["resolved_essentiality"]

        flow_changed = stored_flow != resolved_flow
        category_changed = stored_category != resolved_category
        essentiality_changed = stored_essentiality != resolved_essentiality

        if not flow_changed and not category_changed and not essentiality_changed:
            self._mark_reviewed(service, candidate)
            return False

        merchant_text = f"{candidate['merchant']} {candidate['description']}".lower()
        safe_reclass = any(
            token in merchant_text
            for token in (
                "refund",
                "return",
                "payroll",
                "salary",
                "ui benefit",
                "payables",
                "credit crd epay",
                "payment thank you",
                "inst xfer",
                "moneyline",
                "zelle",
                "transfer from",
                "transfer to",
                "online transfer",
                "recurring transfer",
                "atm withdrawal",
                "venmo",
                "cash app",
                "cashapp",
                "walmart",
                "target",
                "costco",
                "sam's club",
                "sams club",
                "buc-ee",
                "buc ee",
                "publix",
                "whole foods",
            )
        )
        if not safe_reclass and candidate["confidence"] >= 0.75:
            return False

        self._update_transaction(
            service,
            transaction_id=candidate["id"],
            flow_type=resolved_flow,
            category=resolved_category,
            essentiality=resolved_essentiality,
            confidence=max(candidate["confidence"], 0.9),
            metadata_updates={
                "audit": {
                    "status": "auto_fixed",
                    "source": "transaction_audit_deterministic",
                    "reviewed_at": datetime.now(UTC).isoformat(),
                    "reason": "Deterministic transaction audit corrected stored flow/category.",
                    "suggested_flow_type": resolved_flow,
                    "suggested_category": resolved_category,
                    "suggested_essentiality": resolved_essentiality,
                }
            },
        )
        return True

    def _build_agent_messages(self, candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
        compact_candidates = [
            {
                "transaction_id": candidate["id"],
                "date": candidate["transaction_date"],
                "account_label": candidate["account_label"],
                "merchant": candidate["merchant"],
                "description": candidate["description"],
                "amount": candidate["amount"],
                "source_type": candidate["source_type"],
                "document_type": candidate["document_type"],
                "filename": candidate["filename"],
                "similar_count": candidate["similar_count"],
                "stored": {
                    "flow_type": candidate["stored_flow_type"],
                    "category": candidate["stored_category"],
                    "essentiality": candidate["stored_essentiality"],
                    "confidence": candidate["confidence"],
                },
                "deterministic_recommendation": {
                    "flow_type": candidate["resolved_flow_type"],
                    "category": candidate["resolved_category"],
                    "essentiality": candidate["resolved_essentiality"],
                },
            }
            for candidate in candidates
        ]
        user_prompt = "\n".join(
            [
                "Audit these household transactions as an accountant.",
                "Keep ledger rows. Never delete rows. Never hide rows. Only correct flow/category/essentiality or mark real ambiguity.",
                require_agent_hub_prompt(PROMPT_AUDIT_JSON_CONTRACT),
                "",
                json.dumps({"candidates": compact_candidates}, indent=2),
            ]
        )
        system_prompt = "\n\n".join(
            [
                require_agent_hub_prompt(PROMPT_AUDIT_SYSTEM),
                require_agent_hub_prompt(PROMPT_MONEY_RULES),
            ]
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _run_agent_audit(
        self,
        service: Any,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        del service
        if not candidates:
            return []
        client = AgentHubAPIClient(
            agent_slug=HOUSEHOLD_REVIEW_AGENT_SLUG,
            use_memory=True,
        )
        try:
            response = client.complete_messages(
                messages=self._build_agent_messages(candidates),
                purpose="household_transaction_audit",
                thinking_level="medium",
                response_format={"type": "json_object"},
                use_memory=True,
            )
        finally:
            client.close()
        payload = _parse_audit_payload(getattr(response, "content", ""))
        reviews = payload.get("reviews")
        return reviews if isinstance(reviews, list) else []

    def _apply_agent_decision(
        self,
        service: Any,
        candidate: dict[str, Any],
        decision: dict[str, Any],
    ) -> tuple[str, bool]:
        confidence = float(decision.get("confidence") or 0.0)
        reason = _normalize_text(decision.get("reason")) or "Agent audit requested review."
        action = _normalize_text(decision.get("decision")).lower() or "keep"
        suggested_flow = _normalize_text(decision.get("flow_type")) or candidate["stored_flow_type"]
        suggested_category = _normalize_text(decision.get("category")) or candidate["stored_category"]
        suggested_essentiality = (
            _normalize_text(decision.get("essentiality")) or candidate["stored_essentiality"]
        )
        apply_to_merchant = bool(decision.get("apply_to_merchant"))

        if action in {"keep", "no_change"} and confidence >= _MEDIUM_CONFIDENCE:
            self._mark_reviewed(service, candidate)
            return "kept", False

        if action in {"update", "reclassify", "reflow", "update_both"} and confidence >= _HIGH_CONFIDENCE:
            merchant_rule_applied = False
            self._update_transaction(
                service,
                transaction_id=candidate["id"],
                flow_type=suggested_flow,
                category=suggested_category,
                essentiality=suggested_essentiality,
                confidence=max(candidate["confidence"], confidence),
                metadata_updates={
                    "audit": {
                        "status": "agent_fixed",
                        "source": "transaction_audit_agent",
                        "reviewed_at": datetime.now(UTC).isoformat(),
                        "reason": reason,
                        "suggested_flow_type": suggested_flow,
                        "suggested_category": suggested_category,
                        "suggested_essentiality": suggested_essentiality,
                    }
                },
            )
            if (
                apply_to_merchant
                and candidate.get("merchant_id")
                and candidate["similar_count"] >= 3
                and suggested_flow == "expense"
            ):
                merchant_rule_applied = self._apply_merchant_rule(
                    service,
                    merchant_id=str(candidate["merchant_id"]),
                    category=suggested_category,
                    essentiality=suggested_essentiality,
                )
            return "fixed", merchant_rule_applied

        self._flag_candidate(
            service,
            candidate,
            reason=reason,
            suggested_flow=suggested_flow,
            suggested_category=suggested_category,
            suggested_essentiality=suggested_essentiality,
        )
        return "flagged", False

    def _apply_merchant_rule(
        self,
        service: Any,
        *,
        merchant_id: str,
        category: str,
        essentiality: str,
    ) -> bool:
        updated_at = datetime.now(UTC)
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_transactions
                SET category = %s,
                    essentiality = %s,
                    confidence = GREATEST(COALESCE(confidence, 0), 0.97),
                    updated_at = %s
                WHERE merchant_id = %s
                  AND flow_type = 'expense'
                """,
                [category, essentiality, updated_at, merchant_id],
            )
            row = conn.execute(
                """
                UPDATE household_merchants
                SET primary_category = %s,
                    essentiality = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = %s
                WHERE id = %s
                RETURNING id
                """,
                [
                    category,
                    essentiality,
                    json.dumps(
                        {
                            "manual_rule": {
                                "category": category,
                                "essentiality": essentiality,
                                "updated_at": updated_at.isoformat(),
                                "source": "transaction_audit_agent",
                            }
                        }
                    ),
                    updated_at,
                    merchant_id,
                ],
            ).fetchone()
            conn.commit()
        return row is not None

    def _update_transaction(
        self,
        service: Any,
        *,
        transaction_id: str,
        flow_type: str,
        category: str,
        essentiality: str,
        confidence: float,
        metadata_updates: dict[str, Any],
    ) -> None:
        updated_at = datetime.now(UTC)
        metadata_payload = json.dumps(metadata_updates)
        with service.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_transactions
                SET flow_type = %s,
                    category = %s,
                    essentiality = %s,
                    confidence = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    flow_type,
                    category,
                    essentiality,
                    confidence,
                    metadata_payload,
                    updated_at,
                    transaction_id,
                ],
            )
            conn.commit()

    def _mark_reviewed(self, service: Any, candidate: dict[str, Any]) -> None:
        self._merge_audit_metadata(
            service,
            transaction_id=candidate["id"],
            payload={
                "audit": {
                    "status": "reviewed",
                    "source": "transaction_audit",
                    "reviewed_at": datetime.now(UTC).isoformat(),
                }
            },
        )

    def _flag_candidate(
        self,
        service: Any,
        candidate: dict[str, Any],
        *,
        reason: str,
        suggested_flow: str | None = None,
        suggested_category: str | None = None,
        suggested_essentiality: str | None = None,
    ) -> None:
        updated_at = datetime.now(UTC)
        self._merge_audit_metadata(
            service,
            transaction_id=candidate["id"],
            payload={
                "audit": {
                    "status": "needs_review",
                    "source": "transaction_audit",
                    "reviewed_at": updated_at.isoformat(),
                    "reason": reason,
                    "suggested_flow_type": suggested_flow or candidate["resolved_flow_type"],
                    "suggested_category": suggested_category or candidate["resolved_category"],
                    "suggested_essentiality": (
                        suggested_essentiality or candidate["resolved_essentiality"]
                    ),
                }
            },
            confidence=min(candidate["confidence"] or 0.55, 0.55),
        )

    def _merge_audit_metadata(
        self,
        service: Any,
        *,
        transaction_id: str,
        payload: dict[str, Any],
        confidence: float | None = None,
    ) -> None:
        updated_at = datetime.now(UTC)
        params: list[Any] = [json.dumps(payload), updated_at]
        confidence_sql = ""
        if confidence is not None:
            confidence_sql = ", confidence = LEAST(COALESCE(confidence, %s), %s)"
            params.extend([confidence, confidence])
        params.append(transaction_id)
        with service.storage.connection() as conn:
            conn.execute(
                f"""
                UPDATE household_transactions
                SET metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                    updated_at = %s
                    {confidence_sql}
                WHERE id = %s
                """,
                params,
            )
            conn.commit()
