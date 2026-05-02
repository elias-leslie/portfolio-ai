"""Jenny-led household document review and inference generation."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger
from app.services._household_document_baseline import (
    TEXT_PREVIEW_LENGTH,
    _baseline_review,
    _build_questions,
    _extract_amounts,
)
from app.services._household_document_llm import (
    _build_messages,
    _parse_review_payload,
)
from app.services._household_document_pipeline_utils import (
    looks_like_transaction_activity,
    normalize_financial_document_classification,
)
from app.services._household_document_text import (
    _extract_csv_text,
    _extract_text,
)
from app.services.household_account_identity import (
    account_identity_candidates,
    clean_text,
    derive_account_mask,
)
from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)
from app.storage import get_storage

logger = get_logger(__name__)

_GENERIC_FILENAME_PATTERN_STEMS = frozenset(
    {
        "add",
        "anything",
        "attachment",
        "capture",
        "document",
        "file",
        "image",
        "img",
        "photo",
        "picture",
        "scan",
        "scanned",
        "screenshot",
        "screen_shot",
        "upload",
    }
)

_MONEY_SIGNATURE_SOURCE_TYPES = frozenset({"bank", "credit_card", "brokerage", "retirement"})
_CONTEXT_STOPWORDS = frozenset(
    {
        "account",
        "accounts",
        "activity",
        "amount",
        "balance",
        "cash",
        "date",
        "details",
        "document",
        "history",
        "management",
        "member",
        "plan",
        "positions",
        "recent",
        "statement",
        "summary",
        "total",
        "transaction",
        "transactions",
        "uploaded",
        "view",
    }
)
_MONEY_SIGNATURE_VOLATILE_FIELDS = frozenset(
    {
        "activity_observed_through",
        "as_of_date",
        "statement_period",
        "text_preview",
        "total_amount",
    }
)
_MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS = frozenset(
    {
        "activity_observed_through",
        "as_of_date",
        "balance",
        "cash_balance",
        "confidence",
        "holdings_value",
    }
)
_GENERIC_ACCOUNT_NAME_TERMS = frozenset(
    {
        "account",
        "activity",
        "card",
        "credit",
        "document",
        "export",
        "history",
        "statement",
        "transactions",
        "upload",
    }
)

# Re-export for backward compatibility with tests and other importers.
__all__ = [
    "HouseholdDocumentReviewService",
    "_baseline_review",
    "_build_messages",
    "_extract_csv_text",
    "_extract_text",
    "_parse_review_payload",
]


class HouseholdDocumentReviewService:
    """Extract review data from uploaded household documents."""

    def __init__(
        self,
        agent_service: HouseholdReviewAgentService | None = None,
    ) -> None:
        self.agent_service = agent_service or HouseholdReviewAgentService()
        self.storage = get_storage()

    def review(
        self,
        *,
        document_id: str,
        filename: str,
        stored_path: Path,
        content_type: str | None,
        source_type: str,
        document_type: str,
        prior_review: dict[str, Any] | None = None,
        reconciliation_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extracted_text = _extract_text(stored_path, content_type)
        baseline = _baseline_review(
            filename=filename,
            source_type=source_type,
            document_type=document_type,
            extracted_text=extracted_text,
        )
        household_context = self._build_household_context(
            baseline_review=baseline,
            extracted_text=extracted_text,
        )
        signature_review = None
        if prior_review is None and reconciliation_summary is None:
            signature_review = self._signature_review(filename=filename, extracted_text=extracted_text)
        if signature_review is not None:
            signature_type = str(signature_review.pop("_signature_type", "") or "")
            signature_review["extracted_text"] = extracted_text
            baseline_structured = baseline.get("structured_data")
            baseline_has_financial_accounts = False
            has_strong_baseline_identity = False
            is_money_review = str(baseline.get("source_type") or "") in _MONEY_SIGNATURE_SOURCE_TYPES
            if isinstance(baseline_structured, dict):
                financial_accounts = baseline_structured.get("financial_accounts")
                baseline_has_financial_accounts = isinstance(financial_accounts, list) and bool(financial_accounts)
                has_strong_baseline_identity = bool(
                    baseline_has_financial_accounts
                    or baseline_structured.get("merchant")
                )
            signature_structured = signature_review.get("structured_data")
            signature_has_financial_accounts = isinstance(signature_structured, dict) and isinstance(
                signature_structured.get("financial_accounts"), list
            ) and bool(signature_structured.get("financial_accounts"))
            if is_money_review:
                if has_strong_baseline_identity or baseline_has_financial_accounts or signature_has_financial_accounts:
                    merged_signature = self._merge_signature_pattern_with_baseline(
                        signature_review=signature_review,
                        baseline=baseline,
                        extracted_text=extracted_text,
                    )
                    return self._finalize_review(
                        reviewed=merged_signature,
                        baseline=baseline,
                        household_context=household_context,
                        filename=filename,
                        extracted_text=extracted_text,
                        review_strategy="signature",
                    )
                signature_review = None
            elif signature_type in {"csv_header", "filename_pattern"}:
                if has_strong_baseline_identity or signature_has_financial_accounts:
                    merged_signature = self._merge_signature_pattern_with_baseline(
                        signature_review=signature_review,
                        baseline=baseline,
                        extracted_text=extracted_text,
                    )
                    return self._finalize_review(
                        reviewed=merged_signature,
                        baseline=baseline,
                        household_context=household_context,
                        filename=filename,
                        extracted_text=extracted_text,
                        review_strategy="signature",
                    )
            elif signature_review is not None:
                return self._finalize_review(
                    reviewed=signature_review,
                    baseline=baseline,
                    household_context=household_context,
                    filename=filename,
                    extracted_text=extracted_text,
                    review_strategy="signature",
                )

        if AGENT_HUB_ENABLED:
            reviewed = self._review_with_llm(
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "source_type": baseline["source_type"],
                    "document_type": baseline["document_type"],
                    "content_type": content_type,
                },
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
                baseline_review=baseline,
                household_context=household_context,
                prior_review=prior_review,
                reconciliation_summary=reconciliation_summary,
            )
            if reviewed is not None:
                merged_llm = self._merge_llm_result(reviewed, baseline, extracted_text)
                return self._finalize_review(
                    reviewed=merged_llm,
                    baseline=baseline,
                    household_context=household_context,
                    filename=filename,
                    extracted_text=extracted_text,
                    review_strategy="agent",
                )

        if baseline["confidence"] >= 0.88:
            return self._finalize_review(
                reviewed=baseline,
                baseline=baseline,
                household_context=household_context,
                filename=filename,
                extracted_text=extracted_text,
                review_strategy="baseline",
            )

        return self._finalize_review(
            reviewed=baseline,
            baseline=baseline,
            household_context=household_context,
            filename=filename,
            extracted_text=extracted_text,
            review_strategy="baseline",
        )

    def _review_with_llm(
        self,
        *,
        payload: dict[str, Any],
        stored_path: Path,
        content_type: str | None,
        extracted_text: str | None,
        baseline_review: dict[str, Any],
        household_context: dict[str, Any] | None = None,
        prior_review: dict[str, Any] | None = None,
        reconciliation_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        try:
            self.agent_service.ensure_agent()
            client = AgentHubAPIClient(agent_slug=HOUSEHOLD_REVIEW_AGENT_SLUG, use_memory=True)
            baseline_confidence = float(baseline_review.get("confidence") or 0.0)
            thinking_level = (
                "medium"
                if prior_review is not None
                or reconciliation_summary is not None
                or baseline_confidence < 0.97
                else "low"
            )
            messages = _build_messages(
                payload=payload,
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
                baseline_review=baseline_review,
                household_context=household_context,
                prior_review=prior_review,
                reconciliation_summary=reconciliation_summary,
            )
            response = client.complete_messages(
                messages=messages,
                purpose="household_document_review",
                response_format={"type": "json_object"},
                use_memory=True,
                thinking_level=thinking_level,
            )
            return _parse_review_payload(response.content)
        except Exception as exc:
            logger.warning("household_document_review_llm_failed", error=str(exc))
            return None

    def _finalize_review(
        self,
        *,
        reviewed: dict[str, Any],
        baseline: dict[str, Any],
        household_context: dict[str, Any] | None,
        filename: str,
        extracted_text: str | None,
        review_strategy: str,
    ) -> dict[str, Any]:
        reviewed["extracted_text"] = extracted_text
        reviewed = self._reconcile_reviewed_accounts(
            reviewed=reviewed,
            household_context=household_context,
            filename=filename,
        )
        source_type, document_type = normalize_financial_document_classification(
            reviewed=reviewed,
            fallback_source_type=str(baseline.get("source_type") or ""),
            fallback_document_type=str(baseline.get("document_type") or ""),
            filename=filename,
            extracted_text=extracted_text,
        )
        reviewed["source_type"] = source_type
        reviewed["document_type"] = document_type
        reviewed["summary"] = self._normalize_summary(
            reviewed=reviewed,
            fallback_summary=str(baseline.get("summary") or ""),
            source_type=source_type,
            document_type=document_type,
            extracted_text=extracted_text,
        )
        reviewed["review_checks"] = HouseholdDocumentReviewService._normalize_review_checks(
            reviewed=reviewed,
            extracted_text=extracted_text,
        )
        reviewed["_review_strategy"] = review_strategy
        return reviewed

    def _build_household_context(
        self,
        *,
        baseline_review: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any] | None:
        structured_data = baseline_review.get("structured_data")
        structured = structured_data if isinstance(structured_data, dict) else {}
        source_type = str(baseline_review.get("source_type") or "").strip()
        institution_hint = str(
            structured.get("provider_name")
            or structured.get("institution_name")
            or structured.get("merchant")
            or ""
        ).strip()
        account_hint = str(structured.get("account_hint") or "").strip()
        owner_hint = str(structured.get("owner_name") or "").strip()
        signal_text = " ".join(
            part
            for part in (
                institution_hint,
                account_hint,
                owner_hint,
                (extracted_text or "")[:4000],
            )
            if part
        )
        hint_tokens = {
            token
            for token in re.findall(r"[a-z0-9]{3,}", signal_text.lower())
            if token not in _CONTEXT_STOPWORDS
        }
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.id,
                    a.canonical_label,
                    a.source_type,
                    a.asset_group,
                    a.account_type,
                    a.institution_name,
                    a.owner_name,
                    a.account_mask,
                    a.primary_identity_key,
                    COALESCE(MAX(e.as_of_date)::text, NULL) AS last_as_of_date,
                    COUNT(DISTINCT e.id) AS evidence_count
                FROM household_accounts a
                LEFT JOIN household_evidence_accounts e ON e.household_account_id = a.id
                GROUP BY
                    a.id,
                    a.canonical_label,
                    a.source_type,
                    a.asset_group,
                    a.account_type,
                    a.institution_name,
                    a.owner_name,
                    a.account_mask,
                    a.primary_identity_key,
                    a.updated_at
                ORDER BY MAX(e.as_of_date) DESC NULLS LAST, a.updated_at DESC
                LIMIT 64
                """
            ).fetchall()
        if not rows:
            return None

        ranked: list[tuple[int, Any]] = []
        for row in rows:
            haystack = " ".join(
                str(value or "")
                for value in row[1:9]
            ).lower()
            row_tokens = {
                token
                for token in re.findall(r"[a-z0-9]{3,}", haystack)
                if token not in _CONTEXT_STOPWORDS
            }
            score = 0
            if source_type and str(row[2] or "") == source_type:
                score += 5
            if institution_hint and institution_hint.lower() in haystack:
                score += 4
            if account_hint and account_hint.lower() in haystack:
                score += 3
            if owner_hint and owner_hint.lower().split(" ")[0] in haystack:
                score += 2
            score += len(hint_tokens & row_tokens) * 2
            ranked.append((score, row))

        ranked.sort(key=lambda item: item[0], reverse=True)
        selected_rows = [row for score, row in ranked if score > 0][:8]
        if not selected_rows:
            selected_rows = [
                row
                for _, row in ranked
                if not source_type or str(row[2] or "") == source_type
            ][:6] or [row for _, row in ranked[:6]]

        account_ids = [str(row[0]) for row in selected_rows]
        identity_examples: dict[str, list[str]] = {account_id: [] for account_id in account_ids}
        recent_evidence_examples: list[dict[str, Any]] = []
        with self.storage.connection() as conn:
            identity_rows = conn.execute(
                """
                SELECT household_account_id, identity_key
                FROM household_account_identities
                WHERE household_account_id = ANY(%s)
                ORDER BY is_primary DESC, confidence DESC NULLS LAST, updated_at DESC
                """,
                [account_ids],
            ).fetchall()
            evidence_rows = conn.execute(
                """
                SELECT
                    e.household_account_id,
                    d.filename,
                    d.source_type,
                    d.document_type,
                    d.review_summary,
                    e.account_name,
                    e.owner_name,
                    e.account_mask,
                    e.as_of_date
                FROM household_evidence_accounts e
                JOIN household_documents d ON d.id = e.document_id
                WHERE e.household_account_id = ANY(%s)
                ORDER BY e.as_of_date DESC NULLS LAST, d.uploaded_at DESC
                LIMIT 12
                """,
                [account_ids],
            ).fetchall()
        for account_id, identity_key in identity_rows:
            key = str(account_id)
            values = identity_examples.setdefault(key, [])
            text = str(identity_key or "").strip()
            if text and text not in values and len(values) < 3:
                values.append(text)
        for row in evidence_rows:
            recent_evidence_examples.append(
                {
                    "household_account_id": str(row[0]),
                    "filename": str(row[1] or ""),
                    "source_type": str(row[2] or ""),
                    "document_type": str(row[3] or ""),
                    "review_summary": str(row[4] or "") or None,
                    "account_name": str(row[5] or "") or None,
                    "owner_name": str(row[6] or "") or None,
                    "account_mask": str(row[7] or "") or None,
                    "as_of_date": str(row[8] or "") or None,
                }
            )

        related_accounts = [
            {
                "household_account_id": str(row[0]),
                "canonical_label": str(row[1] or ""),
                "source_type": str(row[2] or ""),
                "asset_group": str(row[3] or ""),
                "account_type": str(row[4] or ""),
                "institution_name": str(row[5] or "") or None,
                "owner_name": str(row[6] or "") or None,
                "account_mask": str(row[7] or "") or None,
                "primary_identity_key": str(row[8] or "") or None,
                "last_as_of_date": str(row[9] or "") or None,
                "evidence_count": int(row[10] or 0),
                "identity_examples": identity_examples.get(str(row[0]), []),
            }
            for row in selected_rows
        ]
        return {
            "household_account_count": len(rows),
            "related_accounts": related_accounts,
            "recent_related_evidence": recent_evidence_examples,
        }

    @staticmethod
    def _normalize_match_text(value: object) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @classmethod
    def _name_tokens(cls, *values: object) -> set[str]:
        tokens: set[str] = set()
        for value in values:
            normalized = cls._normalize_match_text(value)
            if not normalized:
                continue
            for token in re.split(r"[^a-z0-9]+", normalized):
                if len(token) < 3 or token in _CONTEXT_STOPWORDS:
                    continue
                tokens.add(token)
        return tokens

    @classmethod
    def _owner_matches(cls, left: object, right: object) -> bool:
        left_tokens = [token for token in re.split(r"[^a-z0-9]+", cls._normalize_match_text(left)) if token]
        right_tokens = [token for token in re.split(r"[^a-z0-9]+", cls._normalize_match_text(right)) if token]
        if not left_tokens or not right_tokens:
            return False
        if left_tokens == right_tokens:
            return True
        if left_tokens[0] != right_tokens[0]:
            return False
        return len(left_tokens) > 1 and len(right_tokens) > 1 and left_tokens[-1] == right_tokens[-1]

    @classmethod
    def _looks_generic_account_name(cls, value: object) -> bool:
        tokens = cls._name_tokens(value)
        return bool(tokens) and tokens <= _GENERIC_ACCOUNT_NAME_TERMS

    def _reconcile_reviewed_accounts(
        self,
        *,
        reviewed: dict[str, Any],
        household_context: dict[str, Any] | None,
        filename: str,
    ) -> dict[str, Any]:
        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict) or not household_context:
            return reviewed
        raw_accounts = structured_data.get("financial_accounts")
        if not isinstance(raw_accounts, list) or not raw_accounts:
            return reviewed
        related_accounts = household_context.get("related_accounts")
        if not isinstance(related_accounts, list) or not related_accounts:
            return reviewed

        canonical_matches: list[dict[str, Any]] = []
        default_source_type = str(reviewed.get("source_type") or "")
        default_document_type = str(reviewed.get("document_type") or "")

        for raw_account in raw_accounts:
            if not isinstance(raw_account, dict):
                continue
            match = self._best_related_account_match(
                raw_account=raw_account,
                related_accounts=related_accounts,
                default_source_type=default_source_type,
                default_document_type=default_document_type,
                filename=filename,
            )
            if match is None:
                continue
            related_account = match["related_account"]
            match_method = str(match["method"])
            match_score = int(match["score"])
            raw_account["household_account_id"] = related_account["household_account_id"]
            if related_account.get("primary_identity_key") and not self._normalize_match_text(raw_account.get("match_key")):
                raw_account["match_key"] = related_account["primary_identity_key"]
            canonical_mask = clean_text(related_account.get("account_mask"))
            extracted_mask = clean_text(raw_account.get("account_mask"))
            filename_mask = clean_text(derive_account_mask(None, clean_text(raw_account.get("account_name")), filename))
            explicit_match_key = self._normalize_match_text(raw_account.get("match_key"))
            primary_identity_key = self._normalize_match_text(related_account.get("primary_identity_key"))
            filename_mask_applied = False
            if filename_mask and explicit_match_key and primary_identity_key and explicit_match_key == primary_identity_key:
                if extracted_mask and extracted_mask != filename_mask:
                    raw_account["extracted_account_mask"] = extracted_mask
                raw_account["account_mask"] = filename_mask
                extracted_mask = filename_mask
                filename_mask_applied = True
            if canonical_mask and not extracted_mask:
                raw_account["account_mask"] = canonical_mask
            elif (
                canonical_mask
                and extracted_mask
                and extracted_mask != canonical_mask
                and not filename_mask_applied
                and explicit_match_key
                and primary_identity_key
                and explicit_match_key == primary_identity_key
            ):
                raw_account["extracted_account_mask"] = extracted_mask
                raw_account["account_mask"] = canonical_mask
            if not clean_text(raw_account.get("institution_name")) and related_account.get("institution_name"):
                raw_account["institution_name"] = related_account["institution_name"]
            if not clean_text(raw_account.get("owner_name")) and related_account.get("owner_name"):
                raw_account["owner_name"] = related_account["owner_name"]
            if not clean_text(raw_account.get("account_type")) and related_account.get("account_type"):
                raw_account["account_type"] = related_account["account_type"]
            if not clean_text(raw_account.get("asset_group")) and related_account.get("asset_group"):
                raw_account["asset_group"] = related_account["asset_group"]
            if (
                not clean_text(raw_account.get("account_name"))
                or self._looks_generic_account_name(raw_account.get("account_name"))
            ) and related_account.get("canonical_label"):
                raw_account["account_name"] = related_account["canonical_label"]
            raw_account["canonical_match_method"] = match_method
            raw_account["canonical_match_score"] = match_score
            canonical_matches.append(
                {
                    "household_account_id": related_account["household_account_id"],
                    "method": match_method,
                    "score": match_score,
                }
            )

        if canonical_matches:
            review_checks = dict(reviewed.get("review_checks")) if isinstance(reviewed.get("review_checks"), dict) else {}
            review_checks["canonical_match_count"] = len(canonical_matches)
            review_checks["canonical_matches"] = canonical_matches
            reviewed["review_checks"] = review_checks
        return reviewed

    def _best_related_account_match(
        self,
        *,
        raw_account: dict[str, Any],
        related_accounts: list[dict[str, Any]],
        default_source_type: str,
        default_document_type: str,
        filename: str,
    ) -> dict[str, Any] | None:
        explicit_match_key = self._normalize_match_text(raw_account.get("match_key"))
        raw_account_name = clean_text(raw_account.get("account_name")) or clean_text(raw_account.get("account_hint"))
        filename_mask = clean_text(derive_account_mask(None, raw_account_name, filename))
        raw_mask = clean_text(
            derive_account_mask(
                clean_text(raw_account.get("account_mask")),
                raw_account_name,
                filename,
            )
        )
        raw_institution = clean_text(raw_account.get("institution_name"))
        raw_owner = clean_text(raw_account.get("owner_name"))
        raw_account_type = clean_text(raw_account.get("account_type"))
        raw_asset_group = clean_text(raw_account.get("asset_group"))
        candidate_keys = set(
            account_identity_candidates(
                source_type=raw_account.get("source_type") or default_source_type,
                asset_group=raw_asset_group,
                account_type=raw_account_type,
                institution_name=raw_institution,
                account_name=raw_account_name,
                owner_name=raw_owner,
                account_mask=raw_mask,
                fallback_label=raw_account_name,
                explicit_match_key=explicit_match_key or None,
            )
        )
        if not candidate_keys and default_document_type not in {"statement", "brokerage_statement", "retirement_statement"}:
            return None
        raw_name_tokens = self._name_tokens(
            raw_account_name,
            raw_account.get("institution_name"),
            raw_account.get("account_hint"),
        )
        scored: list[dict[str, Any]] = []
        for related in related_accounts:
            if not isinstance(related, dict):
                continue
            score = 0
            method = "tokens"
            primary_identity_key = self._normalize_match_text(related.get("primary_identity_key"))
            identity_examples = {
                self._normalize_match_text(identity)
                for identity in related.get("identity_examples", [])
                if self._normalize_match_text(identity)
            }
            related_mask = self._normalize_match_text(related.get("account_mask"))
            related_institution = self._normalize_match_text(related.get("institution_name"))
            related_owner = related.get("owner_name")
            related_account_type = self._normalize_match_text(related.get("account_type"))
            related_asset_group = self._normalize_match_text(related.get("asset_group"))
            related_name_tokens = self._name_tokens(
                related.get("canonical_label"),
                related.get("institution_name"),
            )
            if explicit_match_key and primary_identity_key and explicit_match_key == primary_identity_key:
                score += 120
                method = "explicit_match_key"
            elif primary_identity_key and primary_identity_key in candidate_keys:
                score += 85
                method = "primary_identity"
            overlap = candidate_keys & identity_examples
            if overlap:
                score += 50 + (len(overlap) - 1) * 10
                if method == "tokens":
                    method = "identity_example"
            if raw_mask and related_mask and self._normalize_match_text(raw_mask) == related_mask:
                score += 60
                if method == "tokens":
                    method = "mask"
            elif filename_mask and related_mask and self._normalize_match_text(filename_mask) == related_mask:
                score += 55
                if method == "tokens":
                    method = "filename_mask"
            if raw_institution and related_institution and self._normalize_match_text(raw_institution) == related_institution:
                score += 18
            if raw_owner and self._owner_matches(raw_owner, related_owner):
                score += 12
            if raw_account_type and related_account_type and self._normalize_match_text(raw_account_type) == related_account_type:
                score += 10
            if raw_asset_group and related_asset_group and self._normalize_match_text(raw_asset_group) == related_asset_group:
                score += 6
            shared_name_tokens = raw_name_tokens & related_name_tokens
            if shared_name_tokens:
                score += min(len(shared_name_tokens) * 6, 24)
            if score >= 40:
                scored.append(
                    {
                        "related_account": related,
                        "score": score,
                        "method": method,
                    }
                )
        if not scored:
            return None
        scored.sort(key=lambda item: item["score"], reverse=True)
        best = scored[0]
        next_score = scored[1]["score"] if len(scored) > 1 else -1
        if int(best["score"]) >= 120:
            return best
        if int(best["score"]) >= 70 and int(best["score"]) >= next_score + 10:
            return best
        return None

    @staticmethod
    def _merge_llm_result(
        reviewed: dict[str, Any],
        baseline: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any]:
        """Merge LLM review with baseline defaults and return the enriched result."""
        structured_data = reviewed.setdefault("structured_data", {})
        if isinstance(structured_data, dict):
            structured_data.update(
                {k: v for k, v in baseline["structured_data"].items() if k not in structured_data}
            )
        reviewed.setdefault("inferred_values", [])
        reviewed.setdefault("planning_items", [])
        if not isinstance(reviewed.get("questions"), list):
            reviewed["questions"] = []
        if not reviewed.get("summary"):
            reviewed["summary"] = baseline["summary"]
        if reviewed.get("confidence") is None:
            reviewed["confidence"] = baseline["confidence"]
        reviewed["source_type"] = str(reviewed.get("source_type") or baseline["source_type"])
        reviewed["document_type"] = str(reviewed.get("document_type") or baseline["document_type"])
        reviewed["review_checks"] = HouseholdDocumentReviewService._normalize_review_checks(
            reviewed=reviewed,
            extracted_text=extracted_text,
        )
        reviewed["extracted_text"] = extracted_text
        return reviewed

    @staticmethod
    def _normalize_review_checks(
        *,
        reviewed: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any]:
        raw_review_checks = reviewed.get("review_checks")
        review_checks = dict(raw_review_checks) if isinstance(raw_review_checks, dict) else {}
        structured_data = reviewed.get("structured_data")
        financial_accounts = []
        if isinstance(structured_data, dict) and isinstance(structured_data.get("financial_accounts"), list):
            financial_accounts = [
                account
                for account in structured_data["financial_accounts"]
                if isinstance(account, dict)
            ]
        if review_checks.get("expected_account_count") in {None, ""}:
            review_checks["expected_account_count"] = len(financial_accounts)
        if review_checks.get("expects_transaction_activity") is None:
            has_position_snapshot = any(
                isinstance(account.get("holdings"), list)
                or account.get("position_snapshot") is True
                for account in financial_accounts
            )
            review_source_type = str(reviewed.get("source_type") or "")
            review_document_type = str(reviewed.get("document_type") or "")
            review_checks["expects_transaction_activity"] = (
                False
                if has_position_snapshot
                and review_source_type in {"brokerage", "retirement"}
                and review_document_type
                in {"brokerage_statement", "retirement_statement"}
                else looks_like_transaction_activity(
                    source_type=review_source_type,
                    document_type=review_document_type,
                    extracted_text=extracted_text,
                )
            )
        if review_checks.get("ambiguity_remaining") is None:
            review_checks["ambiguity_remaining"] = bool(reviewed.get("questions"))
        if (
            review_checks.get("ambiguity_remaining")
            and not review_checks.get("ambiguity_reason")
            and reviewed.get("questions")
        ):
            review_checks["ambiguity_reason"] = "Additional user input still required."
        return review_checks

    @staticmethod
    def _normalize_summary(
        *,
        reviewed: dict[str, Any],
        fallback_summary: str,
        source_type: str,
        document_type: str,
        extracted_text: str | None,
    ) -> str:
        current_summary = str(reviewed.get("summary") or "").strip()
        generic = (
            not current_summary
            or current_summary.lower() in {
                "uploaded other from other.",
                "uploaded statement from credit card.",
                "uploaded statement from bank.",
                "uploaded brokerage statement from brokerage.",
                "uploaded retirement statement from retirement.",
            }
        )
        summary = current_summary or fallback_summary or "Reviewed household finance document."
        if generic:
            structured_data = reviewed.get("structured_data")
            structured = structured_data if isinstance(structured_data, dict) else {}
            subject = str(
                structured.get("account_hint")
                or structured.get("provider_name")
                or structured.get("merchant")
                or "Household account"
            ).strip()

            if looks_like_transaction_activity(
                source_type=source_type,
                document_type=document_type,
                extracted_text=extracted_text,
            ):
                if source_type == "credit_card":
                    summary = f"{subject} activity export with machine-readable card transactions."
                elif source_type == "bank":
                    summary = f"{subject} activity export with machine-readable cash transactions."
                elif source_type == "brokerage":
                    summary = f"{subject} export with machine-readable account activity."
            elif source_type == "credit_card" and document_type == "statement":
                summary = f"{subject} statement with household card activity."
            elif source_type == "bank" and document_type == "statement":
                summary = f"{subject} statement with household cash activity."
            elif source_type == "brokerage" and document_type == "brokerage_statement":
                summary = f"{subject} snapshot with investable assets and account activity."
            elif source_type == "retirement" and document_type == "retirement_statement":
                summary = f"{subject} retirement snapshot for long-term planning."

        return summary

    @staticmethod
    def _merge_signature_pattern_with_baseline(
        *,
        signature_review: dict[str, Any],
        baseline: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any]:
        baseline_structured = (
            dict(baseline.get("structured_data"))
            if isinstance(baseline.get("structured_data"), dict)
            else {}
        )
        signature_structured = HouseholdDocumentReviewService._sanitize_money_signature_structured_data(
            signature_review.get("structured_data"),
            source_type=str(signature_review.get("source_type") or baseline.get("source_type") or ""),
        )
        merged_structured = dict(signature_structured)
        for key, value in baseline_structured.items():
            if value not in (None, "", [], {}):
                merged_structured[key] = value
        merged = {
            **baseline,
            "summary": str(baseline.get("summary") or signature_review.get("summary") or ""),
            "source_type": str(baseline.get("source_type") or signature_review.get("source_type") or "other"),
            "document_type": str(baseline.get("document_type") or signature_review.get("document_type") or "other"),
            "confidence": max(
                float(signature_review.get("confidence") or 0.0),
                float(baseline.get("confidence") or 0.0),
            ),
            "structured_data": merged_structured,
            "inferred_values": baseline.get("inferred_values") if isinstance(baseline.get("inferred_values"), list) else [],
            "questions": (
                signature_review.get("questions")
                if isinstance(signature_review.get("questions"), list)
                else baseline.get("questions")
                if isinstance(baseline.get("questions"), list)
                else []
            ),
            "extracted_text": extracted_text,
        }
        return merged

    @staticmethod
    def _sanitize_money_signature_structured_data(
        structured_data: object,
        *,
        source_type: str,
    ) -> dict[str, Any]:
        if not isinstance(structured_data, dict):
            return {}
        if str(source_type or "") not in _MONEY_SIGNATURE_SOURCE_TYPES:
            return dict(structured_data)
        sanitized: dict[str, Any] = {}
        for raw_key, value in structured_data.items():
            key = str(raw_key)
            if key in _MONEY_SIGNATURE_VOLATILE_FIELDS:
                continue
            if key == "financial_accounts" and isinstance(value, list):
                stable_accounts: list[dict[str, Any]] = []
                for raw_account in value:
                    if not isinstance(raw_account, dict):
                        continue
                    stable_account = {
                        account_key: account_value
                        for account_key, account_value in raw_account.items()
                        if account_key not in _MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS
                        and account_value not in (None, "", [], {})
                    }
                    if stable_account:
                        stable_accounts.append(stable_account)
                if stable_accounts:
                    sanitized[key] = stable_accounts
                continue
            if value not in (None, "", [], {}):
                sanitized[key] = value
        return sanitized

    def build_signature_candidates(
        self,
        *,
        filename: str,
        extracted_text: str | None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        candidates: list[tuple[str, str, dict[str, Any]]] = []
        normalized = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower())
        normalized = re.sub(r"\d", "#", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        tokens = [
            re.sub(r"#+", "", token)
            for token in normalized.split("_")
            if re.sub(r"#+", "", token)
        ]
        is_generic_pattern = bool(tokens) and all(
            token in _GENERIC_FILENAME_PATTERN_STEMS for token in tokens
        )
        if sum(c.isalpha() for c in normalized) >= 4 and not is_generic_pattern:
            candidates.append(
                ("filename_pattern", f"filename_pattern::{normalized}", {"normalized_filename": normalized})
            )
        if not extracted_text:
            return candidates
        non_empty_lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
        if non_empty_lines:
            prefix = " | ".join(non_empty_lines[:4]).lower()
            prefix = re.sub(r"\d", "#", prefix)
            prefix = re.sub(r"[^a-z0-9()|]+", "_", prefix)
            prefix = re.sub(r"_+", "_", prefix).strip("_")
            if len(prefix) >= 16:
                digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:24]
                candidates.append(
                    ("text_prefix", f"text_prefix::{digest}", {"normalized_prefix": prefix})
                )
        if filename.lower().endswith(".csv"):
            first_line = next(
                (line.strip() for line in extracted_text.splitlines() if line.strip()), ""
            )
            if first_line:
                normalized_headers = "|".join(
                    cell.strip().lower().replace(" ", "_") for cell in first_line.split(",")[:20]
                )
                if normalized_headers:
                    digest = hashlib.sha256(normalized_headers.encode("utf-8")).hexdigest()[:24]
                    candidates.append(
                        ("csv_header", f"csv_header::{digest}", {"normalized_headers": normalized_headers})
                    )
        return candidates

    def _signature_review(
        self,
        *,
        filename: str,
        extracted_text: str | None,
    ) -> dict[str, Any] | None:
        candidates = self.build_signature_candidates(filename=filename, extracted_text=extracted_text)
        if not candidates:
            return None

        signature = self._find_signature([key for _, key, _ in candidates])
        if signature is None:
            return None

        confidence = float(signature["confidence"] or 0.0)
        threshold = 0.94 if signature["signature_type"] == "filename_pattern" else 0.9
        if confidence < threshold:
            return None
        signature_structured = self._sanitize_money_signature_structured_data(
            signature.get("structured_data"),
            source_type=str(signature.get("source_type") or ""),
        )
        if (
            str(signature.get("source_type") or "") in _MONEY_SIGNATURE_SOURCE_TYPES
            and str(signature.get("signature_type") or "") not in {"csv_header", "filename_pattern"}
            and not (
                isinstance(signature_structured.get("financial_accounts"), list)
                and bool(signature_structured.get("financial_accounts"))
            )
        ):
            return None

        structured_data: dict[str, Any] = dict(signature_structured)
        structured_data.setdefault("merchant", signature["merchant"])
        structured_data.setdefault("account_hint", signature["account_hint"])
        if extracted_text:
            structured_data["text_preview"] = extracted_text[:TEXT_PREVIEW_LENGTH]
        statement_period, total_amount = _extract_amounts(extracted_text)
        if statement_period and not structured_data.get("statement_period"):
            structured_data["statement_period"] = statement_period
        if total_amount and not structured_data.get("total_amount"):
            structured_data["total_amount"] = total_amount

        subject = structured_data.get("merchant") or structured_data.get("account_hint")
        summary = (
            f"Matched learned {signature['signature_type'].replace('_', ' ')} signature "
            f"for {signature['document_type'].replace('_', ' ')} from "
            f"{signature['source_type'].replace('_', ' ')}."
        )
        if isinstance(subject, str) and subject:
            summary = f"{subject} matched a learned household document pattern."
        if isinstance(total_amount, str) and total_amount:
            summary = f"{summary} Detected total amount {total_amount}."

        self._touch_signature(signature["id"])
        return {
            "summary": summary,
            "document_type": signature["document_type"],
            "source_type": signature["source_type"],
            "confidence": confidence,
            "structured_data": structured_data,
            "inferred_values": [],
            "questions": _build_questions(
                source_type=signature["source_type"],
                document_type=signature["document_type"],
                summary=summary,
                merchant=signature["merchant"],
                account_hint=signature["account_hint"],
            ),
            "_signature_type": signature["signature_type"],
        }

    def _find_signature(self, signature_keys: list[str]) -> dict[str, Any] | None:
        if not signature_keys:
            return None
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id, signature_type, source_type, document_type,
                    merchant, account_hint, confidence, metadata
                FROM household_document_signatures
                WHERE signature_key = ANY(%s)
                ORDER BY confidence DESC NULLS LAST, updated_at DESC
                LIMIT 1
                """,
                [signature_keys],
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row[0]),
            "signature_type": str(row[1]),
            "source_type": str(row[2]),
            "document_type": str(row[3]),
            "merchant": str(row[4]) if row[4] is not None else None,
            "account_hint": str(row[5]) if row[5] is not None else None,
            "confidence": float(row[6]) if row[6] is not None else None,
            "structured_data": (
                row[7].get("structured_data")
                if isinstance(row[7], dict)
                else None
            ),
        }

    def _touch_signature(self, signature_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_document_signatures
                SET match_count = match_count + 1,
                    last_seen_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [now, now, signature_id],
            )
            conn.commit()
