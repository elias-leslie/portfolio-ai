"""Jenny-led household document review and inference generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger
from app.services._household_document_baseline import _baseline_review
from app.services._household_document_llm import _build_messages, _parse_review_payload
from app.services._household_document_pipeline_utils import (
    normalize_financial_document_classification,
)
from app.services._household_document_review_context import HouseholdDocumentContextMixin
from app.services._household_document_review_matching import (
    _looks_generic_account_name,
    _name_tokens,
    _normalize_match_text,
    _owner_matches,
    best_related_account_match,
)
from app.services._household_document_review_normalization import (
    merge_llm_result,
    normalize_review_checks,
    normalize_summary,
)
from app.services._household_document_review_signatures import (
    _MONEY_SIGNATURE_SOURCE_TYPES,
    HouseholdDocumentSignatureMixin,
    build_signature_candidates,
    merge_signature_pattern_with_baseline,
    sanitize_money_signature_structured_data,
)
from app.services._household_document_text import _extract_csv_text, _extract_text
from app.services.household_account_identity import clean_text, derive_account_mask
from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)
from app.storage import get_storage

logger = get_logger(__name__)

# Re-export for backward compatibility with tests and other importers.
__all__ = [
    "HouseholdDocumentReviewService",
    "_baseline_review",
    "_build_messages",
    "_extract_csv_text",
    "_extract_text",
    "_parse_review_payload",
]


class HouseholdDocumentReviewService(HouseholdDocumentContextMixin, HouseholdDocumentSignatureMixin):
    """Extract review data from uploaded household documents."""

    _merge_llm_result = staticmethod(merge_llm_result)
    _normalize_review_checks = staticmethod(normalize_review_checks)
    _normalize_summary = staticmethod(normalize_summary)
    _merge_signature_pattern_with_baseline = staticmethod(merge_signature_pattern_with_baseline)
    _sanitize_money_signature_structured_data = staticmethod(sanitize_money_signature_structured_data)
    _normalize_match_text = staticmethod(_normalize_match_text)
    _name_tokens = staticmethod(_name_tokens)
    _owner_matches = staticmethod(_owner_matches)
    _looks_generic_account_name = staticmethod(_looks_generic_account_name)
    build_signature_candidates = staticmethod(build_signature_candidates)

    def __init__(self, agent_service: HouseholdReviewAgentService | None = None) -> None:
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
        household_context = self._build_household_context(baseline_review=baseline, extracted_text=extracted_text)
        signature_result = self._signature_result(
            baseline=baseline,
            household_context=household_context,
            filename=filename,
            extracted_text=extracted_text,
            prior_review=prior_review,
            reconciliation_summary=reconciliation_summary,
        )
        if signature_result is not None:
            return signature_result

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
                return self._finalize_review(
                    reviewed=self._merge_llm_result(reviewed, baseline, extracted_text),
                    baseline=baseline,
                    household_context=household_context,
                    filename=filename,
                    extracted_text=extracted_text,
                    review_strategy="agent",
                )

        return self._finalize_review(
            reviewed=baseline,
            baseline=baseline,
            household_context=household_context,
            filename=filename,
            extracted_text=extracted_text,
            review_strategy="baseline",
        )

    def _signature_result(
        self,
        *,
        baseline: dict[str, Any],
        household_context: dict[str, Any] | None,
        filename: str,
        extracted_text: str | None,
        prior_review: dict[str, Any] | None,
        reconciliation_summary: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if prior_review is not None or reconciliation_summary is not None:
            return None
        signature_review = self._signature_review(filename=filename, extracted_text=extracted_text)
        if signature_review is None:
            return None

        signature_type = str(signature_review.pop("_signature_type", "") or "")
        signature_review["extracted_text"] = extracted_text
        baseline_structured = baseline.get("structured_data")
        baseline_accounts = baseline_structured.get("financial_accounts") if isinstance(baseline_structured, dict) else None
        baseline_has_accounts = isinstance(baseline_accounts, list) and bool(baseline_accounts)
        has_strong_baseline_identity = isinstance(baseline_structured, dict) and bool(
            baseline_has_accounts or baseline_structured.get("merchant")
        )
        signature_structured = signature_review.get("structured_data")
        signature_accounts = signature_structured.get("financial_accounts") if isinstance(signature_structured, dict) else None
        signature_has_accounts = isinstance(signature_accounts, list) and bool(signature_accounts)
        is_money_review = str(baseline.get("source_type") or "") in _MONEY_SIGNATURE_SOURCE_TYPES

        should_merge = (
            is_money_review and (has_strong_baseline_identity or baseline_has_accounts or signature_has_accounts)
        ) or (
            signature_type in {"csv_header", "filename_pattern"}
            and (has_strong_baseline_identity or signature_has_accounts)
        )
        if is_money_review and not should_merge:
            return None
        reviewed = (
            self._merge_signature_pattern_with_baseline(
                signature_review=signature_review,
                baseline=baseline,
                extracted_text=extracted_text,
            )
            if should_merge
            else signature_review
        )
        return self._finalize_review(
            reviewed=reviewed,
            baseline=baseline,
            household_context=household_context,
            filename=filename,
            extracted_text=extracted_text,
            review_strategy="signature",
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
                if prior_review is not None or reconciliation_summary is not None or baseline_confidence < 0.97
                else "low"
            )
            response = client.complete_messages(
                messages=_build_messages(
                    payload=payload,
                    stored_path=stored_path,
                    content_type=content_type,
                    extracted_text=extracted_text,
                    baseline_review=baseline_review,
                    household_context=household_context,
                    prior_review=prior_review,
                    reconciliation_summary=reconciliation_summary,
                ),
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
        reviewed = self._reconcile_reviewed_accounts(reviewed=reviewed, household_context=household_context, filename=filename)
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
        reviewed["review_checks"] = self._normalize_review_checks(reviewed=reviewed, extracted_text=extracted_text)
        reviewed["_review_strategy"] = review_strategy
        return reviewed

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
        related_accounts = household_context.get("related_accounts")
        if not isinstance(raw_accounts, list) or not raw_accounts or not isinstance(related_accounts, list) or not related_accounts:
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
            if match is not None:
                canonical_matches.append(self._apply_canonical_match(raw_account=raw_account, match=match, filename=filename))

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
        return best_related_account_match(
            raw_account=raw_account,
            related_accounts=related_accounts,
            default_source_type=default_source_type,
            default_document_type=default_document_type,
            filename=filename,
        )

    def _apply_canonical_match(
        self,
        *,
        raw_account: dict[str, Any],
        match: dict[str, Any],
        filename: str,
    ) -> dict[str, Any]:
        related_account = match["related_account"]
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
        elif canonical_mask and extracted_mask and extracted_mask != canonical_mask and not filename_mask_applied and explicit_match_key and primary_identity_key and explicit_match_key == primary_identity_key:
            raw_account["extracted_account_mask"] = extracted_mask
            raw_account["account_mask"] = canonical_mask

        for raw_key, related_key in {
            "institution_name": "institution_name",
            "owner_name": "owner_name",
            "account_type": "account_type",
            "asset_group": "asset_group",
        }.items():
            if not clean_text(raw_account.get(raw_key)) and related_account.get(related_key):
                raw_account[raw_key] = related_account[related_key]
        if (not clean_text(raw_account.get("account_name")) or self._looks_generic_account_name(raw_account.get("account_name"))) and related_account.get("canonical_label"):
            raw_account["account_name"] = related_account["canonical_label"]

        raw_account["canonical_match_method"] = str(match["method"])
        raw_account["canonical_match_score"] = int(match["score"])
        return {
            "household_account_id": related_account["household_account_id"],
            "method": str(match["method"]),
            "score": int(match["score"]),
        }
