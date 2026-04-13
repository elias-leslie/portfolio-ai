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
from app.services._household_document_text import (
    _extract_csv_text,
    _extract_text,
)
from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)
from app.storage import get_storage

logger = get_logger(__name__)

_GENERIC_FILENAME_PATTERN_STEMS = frozenset(
    {
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
    ) -> dict[str, Any]:
        extracted_text = _extract_text(stored_path, content_type)
        baseline = _baseline_review(
            filename=filename,
            source_type=source_type,
            document_type=document_type,
            extracted_text=extracted_text,
        )
        signature_review = self._signature_review(filename=filename, extracted_text=extracted_text)
        if signature_review is not None:
            signature_type = str(signature_review.pop("_signature_type", "") or "")
            signature_review["extracted_text"] = extracted_text
            baseline_structured = baseline.get("structured_data")
            has_strong_baseline_identity = False
            if isinstance(baseline_structured, dict):
                financial_accounts = baseline_structured.get("financial_accounts")
                has_strong_baseline_identity = bool(
                    (isinstance(financial_accounts, list) and financial_accounts)
                    or baseline_structured.get("merchant")
                    or baseline_structured.get("account_hint")
                )
            if has_strong_baseline_identity and signature_type in {"csv_header", "filename_pattern"}:
                return self._merge_signature_pattern_with_baseline(
                    signature_review=signature_review,
                    baseline=baseline,
                    extracted_text=extracted_text,
                )
            return signature_review

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
            )
            if reviewed is not None:
                return self._merge_llm_result(reviewed, baseline, extracted_text)

        if baseline["confidence"] >= 0.88:
            baseline["extracted_text"] = extracted_text
            return baseline

        baseline["extracted_text"] = extracted_text
        return baseline

    def _review_with_llm(
        self,
        *,
        payload: dict[str, Any],
        stored_path: Path,
        content_type: str | None,
        extracted_text: str | None,
        baseline_review: dict[str, Any],
    ) -> dict[str, Any] | None:
        try:
            self.agent_service.ensure_agent()
            client = AgentHubAPIClient(agent_slug=HOUSEHOLD_REVIEW_AGENT_SLUG, use_memory=True)
            messages = _build_messages(
                payload=payload,
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
                baseline_review=baseline_review,
            )
            response = client.complete_messages(
                messages=messages,
                purpose="household_document_review",
                response_format={"type": "json_object"},
                use_memory=True,
                thinking_level="low",
            )
            return _parse_review_payload(response.content)
        except Exception as exc:
            logger.warning("household_document_review_llm_failed", error=str(exc))
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
        reviewed.setdefault("questions", baseline["questions"])
        if not reviewed.get("summary"):
            reviewed["summary"] = baseline["summary"]
        if reviewed.get("confidence") is None:
            reviewed["confidence"] = baseline["confidence"]
        reviewed["source_type"] = str(reviewed.get("source_type") or baseline["source_type"])
        reviewed["document_type"] = str(reviewed.get("document_type") or baseline["document_type"])
        reviewed["extracted_text"] = extracted_text
        return reviewed

    @staticmethod
    def _merge_signature_pattern_with_baseline(
        *,
        signature_review: dict[str, Any],
        baseline: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any]:
        merged = {
            **baseline,
            "summary": str(baseline.get("summary") or signature_review.get("summary") or ""),
            "source_type": str(baseline.get("source_type") or signature_review.get("source_type") or "other"),
            "document_type": str(baseline.get("document_type") or signature_review.get("document_type") or "other"),
            "confidence": max(
                float(signature_review.get("confidence") or 0.0),
                float(baseline.get("confidence") or 0.0),
            ),
            "structured_data": baseline.get("structured_data") if isinstance(baseline.get("structured_data"), dict) else {},
            "inferred_values": baseline.get("inferred_values") if isinstance(baseline.get("inferred_values"), list) else [],
            "questions": baseline.get("questions") if isinstance(baseline.get("questions"), list) else [],
            "extracted_text": extracted_text,
        }
        return merged

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

        structured_data: dict[str, Any] = {
            "merchant": signature["merchant"],
            "account_hint": signature["account_hint"],
            "text_preview": extracted_text[:TEXT_PREVIEW_LENGTH] if extracted_text else None,
        }
        statement_period, total_amount = _extract_amounts(extracted_text)
        if statement_period:
            structured_data["statement_period"] = statement_period
        if total_amount:
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
                    merchant, account_hint, confidence
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
