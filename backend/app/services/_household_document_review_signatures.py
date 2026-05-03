"""Household document signature matching helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services._household_document_baseline import (
    TEXT_PREVIEW_LENGTH,
    _build_questions,
    _extract_amounts,
)

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


def sanitize_money_signature_structured_data(structured_data: object, *, source_type: str) -> dict[str, Any]:
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
            stable_accounts = [_stable_signature_account(account) for account in value if isinstance(account, dict)]
            stable_accounts = [account for account in stable_accounts if account]
            if stable_accounts:
                sanitized[key] = stable_accounts
            continue
        if value not in (None, "", [], {}):
            sanitized[key] = value
    return sanitized


def _stable_signature_account(raw_account: dict[str, Any]) -> dict[str, Any]:
    return {
        account_key: account_value
        for account_key, account_value in raw_account.items()
        if account_key not in _MONEY_SIGNATURE_ACCOUNT_VOLATILE_FIELDS and account_value not in (None, "", [], {})
    }


def merge_signature_pattern_with_baseline(
    *,
    signature_review: dict[str, Any],
    baseline: dict[str, Any],
    extracted_text: str | None,
) -> dict[str, Any]:
    baseline_structured = dict(baseline.get("structured_data")) if isinstance(baseline.get("structured_data"), dict) else {}
    signature_structured = sanitize_money_signature_structured_data(
        signature_review.get("structured_data"),
        source_type=str(signature_review.get("source_type") or baseline.get("source_type") or ""),
    )
    merged_structured = dict(signature_structured)
    for key, value in baseline_structured.items():
        if value not in (None, "", [], {}):
            merged_structured[key] = value
    return {
        **baseline,
        "summary": str(baseline.get("summary") or signature_review.get("summary") or ""),
        "source_type": str(baseline.get("source_type") or signature_review.get("source_type") or "other"),
        "document_type": str(baseline.get("document_type") or signature_review.get("document_type") or "other"),
        "confidence": max(float(signature_review.get("confidence") or 0.0), float(baseline.get("confidence") or 0.0)),
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


def build_signature_candidates(*, filename: str, extracted_text: str | None) -> list[tuple[str, str, dict[str, Any]]]:
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    normalized = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower())
    normalized = re.sub(r"\d", "#", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    tokens = [re.sub(r"#+", "", token) for token in normalized.split("_") if re.sub(r"#+", "", token)]
    is_generic_pattern = bool(tokens) and all(token in _GENERIC_FILENAME_PATTERN_STEMS for token in tokens)
    if sum(c.isalpha() for c in normalized) >= 4 and not is_generic_pattern:
        candidates.append(("filename_pattern", f"filename_pattern::{normalized}", {"normalized_filename": normalized}))
    if not extracted_text:
        return candidates
    candidates.extend(_text_signature_candidates(extracted_text))
    if filename.lower().endswith(".csv"):
        candidates.extend(_csv_signature_candidates(extracted_text))
    return candidates


def _text_signature_candidates(extracted_text: str) -> list[tuple[str, str, dict[str, Any]]]:
    non_empty_lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
    if not non_empty_lines:
        return []
    prefix = " | ".join(non_empty_lines[:4]).lower()
    prefix = re.sub(r"\d", "#", prefix)
    prefix = re.sub(r"[^a-z0-9()|]+", "_", prefix)
    prefix = re.sub(r"_+", "_", prefix).strip("_")
    if len(prefix) < 16:
        return []
    digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:24]
    return [("text_prefix", f"text_prefix::{digest}", {"normalized_prefix": prefix})]


def _csv_signature_candidates(extracted_text: str) -> list[tuple[str, str, dict[str, Any]]]:
    first_line = next((line.strip() for line in extracted_text.splitlines() if line.strip()), "")
    if not first_line:
        return []
    normalized_headers = "|".join(cell.strip().lower().replace(" ", "_") for cell in first_line.split(",")[:20])
    if not normalized_headers:
        return []
    digest = hashlib.sha256(normalized_headers.encode("utf-8")).hexdigest()[:24]
    return [("csv_header", f"csv_header::{digest}", {"normalized_headers": normalized_headers})]


class HouseholdDocumentSignatureMixin:
    storage: Any

    def build_signature_candidates(self, *, filename: str, extracted_text: str | None) -> list[tuple[str, str, dict[str, Any]]]:
        return build_signature_candidates(filename=filename, extracted_text=extracted_text)

    def _signature_review(self, *, filename: str, extracted_text: str | None) -> dict[str, Any] | None:
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
        signature_structured = sanitize_money_signature_structured_data(
            signature.get("structured_data"),
            source_type=str(signature.get("source_type") or ""),
        )
        if self._is_weak_money_signature(signature=signature, signature_structured=signature_structured):
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

        summary = _signature_summary(signature=signature, structured_data=structured_data, total_amount=total_amount)
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

    @staticmethod
    def _is_weak_money_signature(*, signature: dict[str, Any], signature_structured: dict[str, Any]) -> bool:
        return (
            str(signature.get("source_type") or "") in _MONEY_SIGNATURE_SOURCE_TYPES
            and str(signature.get("signature_type") or "") not in {"csv_header", "filename_pattern"}
            and not (
                isinstance(signature_structured.get("financial_accounts"), list)
                and bool(signature_structured.get("financial_accounts"))
            )
        )

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
            "structured_data": row[7].get("structured_data") if isinstance(row[7], dict) else None,
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


def _signature_summary(*, signature: dict[str, Any], structured_data: dict[str, Any], total_amount: str | None) -> str:
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
    return summary
