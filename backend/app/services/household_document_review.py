"""Jenny-led household document review and inference generation."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz
from agent_hub.models.content import ImageContent, MessageInput, TextContent
from pypdf import PdfReader

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger
from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)
from app.storage import get_storage

logger = get_logger(__name__)

JSON_REVIEW_INSTRUCTIONS = """Return strict JSON only for this household finance document review.

Schema:
{
  "summary": "short summary",
  "document_type": "statement|brokerage_statement|retirement_statement|receipt|invoice|other",
  "source_type": "bank|credit_card|brokerage|retirement|receipt|billing|other",
  "confidence": 0.0-1.0,
  "structured_data": {
    "merchant": "optional",
    "statement_period": "optional",
    "total_amount": "optional",
    "currency": "optional",
    "account_hint": "optional"
  },
  "inferred_values": [
    {
      "field_name": "monthly_net_income_target|monthly_essential_target|monthly_discretionary_target|monthly_savings_target|target_retirement_age|target_retirement_spend",
      "value": "stringified value",
      "confidence": 0.0-1.0,
      "rationale": "why you inferred it"
    }
  ],
  "questions": [
    {
      "field_name": "optional matching field name",
      "question": "short direct question",
      "priority": "high|medium|low",
      "recommendation": "short recommended answer or next step",
      "rationale": "why this needs confirmation"
    }
  ]
}

Only infer values if the evidence is strong. Infer source_type, document_type, and account_hint from the file whenever possible.
If account identity, institution, or document role is ambiguous, ask targeted questions instead of guessing.
"""


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
        extracted_text = self._extract_text(stored_path, content_type)
        baseline_review = self._baseline_review(
            filename=filename,
            source_type=source_type,
            document_type=document_type,
            extracted_text=extracted_text,
        )
        signature_review = self._signature_review(
            filename=filename,
            extracted_text=extracted_text,
        )
        if signature_review is not None:
            signature_review["extracted_text"] = extracted_text
            return signature_review

        if baseline_review["confidence"] >= 0.88:
            baseline_review["extracted_text"] = extracted_text
            return baseline_review

        payload = {
            "document_id": document_id,
            "filename": filename,
            "source_type": baseline_review["source_type"],
            "document_type": baseline_review["document_type"],
            "content_type": content_type,
        }

        if AGENT_HUB_ENABLED:
            reviewed = self._review_with_llm(
                payload=payload,
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
                baseline_review=baseline_review,
            )
            if reviewed is not None:
                structured_data = reviewed.setdefault("structured_data", {})
                if isinstance(structured_data, dict):
                    for key, value in baseline_review["structured_data"].items():
                        structured_data.setdefault(key, value)
                reviewed.setdefault("inferred_values", [])
                reviewed.setdefault("questions", baseline_review["questions"])
                if not reviewed.get("summary"):
                    reviewed["summary"] = baseline_review["summary"]
                if reviewed.get("confidence") is None:
                    reviewed["confidence"] = baseline_review["confidence"]
                reviewed["source_type"] = str(reviewed.get("source_type") or baseline_review["source_type"])
                reviewed["document_type"] = str(
                    reviewed.get("document_type") or baseline_review["document_type"]
                )
                reviewed["extracted_text"] = extracted_text
                return reviewed

        baseline_review["extracted_text"] = extracted_text
        return baseline_review

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
            messages = self._build_messages(
                payload=payload,
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
                baseline_review=baseline_review,
            )
            response = client._client.complete(
                project_id="portfolio-ai",
                agent_slug=HOUSEHOLD_REVIEW_AGENT_SLUG,
                messages=messages,
                temperature=0.1,
                timeout_seconds=120,
                purpose="household_document_review",
                use_memory=True,
                thinking_level="low",
            )
            return self._parse_review_payload(response.content)
        except Exception as exc:
            logger.warning("household_document_review_llm_failed", error=str(exc))
            return None

    def _parse_review_payload(self, content: Any) -> dict[str, Any]:
        text = self._coerce_content_to_text(content)
        candidates = self._json_candidates(text)
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("No valid JSON object found in review payload")

    def _coerce_content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                    continue
                text_value = getattr(item, "text", None)
                if isinstance(text_value, str):
                    chunks.append(text_value)
            return "\n".join(chunk for chunk in chunks if chunk)
        return str(content)

    def _json_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []

        fenced = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        candidates.extend(fenced)

        generic_fenced = re.findall(r"```\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
        candidates.extend(generic_fenced)

        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidates.append(text[first_brace : last_brace + 1].strip())

        # Preserve order while deduplicating.
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        return ordered

    def _build_messages(
        self,
        *,
        payload: dict[str, Any],
        stored_path: Path,
        content_type: str | None,
        extracted_text: str | None,
        baseline_review: dict[str, Any],
    ) -> list[MessageInput]:
        content_blocks: list[Any] = [
            TextContent(
                text=(
                    f"{JSON_REVIEW_INSTRUCTIONS}\n\n"
                    "Document metadata:\n"
                    f"{json.dumps(payload, indent=2)}\n\n"
                    "Deterministic reviewer baseline:\n"
                    f"{json.dumps(baseline_review, indent=2)}\n\n"
                    "Use any extracted text and visual evidence to infer likely household planning values."
                )
            )
        ]

        if extracted_text:
            content_blocks.append(
                TextContent(
                    text=(
                        "Extracted text preview:\n"
                        f"{extracted_text[:12000]}"
                    )
                )
            )

        if stored_path.suffix.lower() == ".pdf" or content_type == "application/pdf":
            content_blocks.extend(self._pdf_image_blocks(stored_path))

        if content_type and content_type.startswith("image/"):
            content_blocks.append(self._image_block(stored_path, content_type))

        return [MessageInput(role="user", content=content_blocks)]

    def _image_block(self, stored_path: Path, content_type: str) -> ImageContent:
        encoded = base64.b64encode(stored_path.read_bytes()).decode("utf-8")
        return ImageContent.from_base64(encoded, media_type=content_type)

    def _pdf_image_blocks(self, stored_path: Path) -> list[ImageContent]:
        blocks: list[ImageContent] = []
        try:
            with fitz.open(stored_path) as pdf:
                for page_index in range(min(len(pdf), 2)):
                    page = pdf.load_page(page_index)
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                    blocks.append(
                        ImageContent.from_base64(
                            base64.b64encode(pixmap.tobytes("png")).decode("utf-8"),
                            media_type="image/png",
                        )
                    )
        except Exception as exc:
            logger.warning("household_pdf_preview_failed", path=str(stored_path), error=str(exc))
            return []

        return blocks

    def _extract_text(self, stored_path: Path, content_type: str | None) -> str | None:
        suffix = stored_path.suffix.lower()
        if suffix == ".csv":
            return self._extract_csv_text(stored_path)
        if suffix == ".pdf" or content_type == "application/pdf":
            return self._extract_pdf_text(stored_path)
        if suffix in {".txt", ".json"}:
            return stored_path.read_text(encoding="utf-8", errors="ignore")[:12000]
        return None

    def _extract_csv_text(self, stored_path: Path) -> str:
        rows: list[str] = []
        with stored_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.reader(handle)
            for idx, row in enumerate(reader):
                rows.append(", ".join(cell.strip() for cell in row[:32]))
                if idx >= 20:
                    break
        return "\n".join(rows)

    def _extract_pdf_text(self, stored_path: Path) -> str | None:
        try:
            reader = PdfReader(str(stored_path))
            chunks: list[str] = []
            for page in reader.pages[:4]:
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append(text.strip())
            merged = "\n\n".join(chunks).strip()
            return merged[:12000] if merged else None
        except Exception as exc:
            logger.warning("household_pdf_extract_failed", path=str(stored_path), error=str(exc))
            return None

    def _baseline_review(
        self,
        *,
        filename: str,
        source_type: str,
        document_type: str,
        extracted_text: str | None,
    ) -> dict[str, Any]:
        structured_data: dict[str, Any] = {
            "text_preview": extracted_text[:500] if extracted_text else None,
        }
        inferred_source = source_type
        inferred_document = document_type
        confidence = 0.45
        summary = (
            f"Uploaded {document_type.replace('_', ' ')} from {source_type.replace('_', ' ')}."
        )

        filename_lower = filename.lower()
        text_lower = (extracted_text or "").lower()

        if (
            filename_lower == "order history.csv"
            or (
                "order date" in text_lower
                and "order id" in text_lower
                and "payment instrument type" in text_lower
            )
        ):
            inferred_source = "receipt"
            inferred_document = "receipt"
            confidence = 0.9
            structured_data["merchant"] = "Amazon"
            if "total amount" in text_lower or "unit price" in text_lower or "shipping charge" in text_lower:
                summary = "Amazon order history export with order pricing, shipping, and item-level purchase detail."
            else:
                summary = "Amazon order history export covering household purchases over time."
        elif "walmart.com" in text_lower or "order details - walmart.com" in text_lower or "walmart" in filename_lower:
            inferred_source = "receipt"
            inferred_document = "receipt"
            confidence = 0.84
            structured_data["merchant"] = "Walmart"
            summary = "Walmart order details with household shopping line items."
        elif "wells fargo everyday checking" in text_lower:
            inferred_source = "bank"
            inferred_document = "statement"
            confidence = 0.88
            structured_data["account_hint"] = "Wells Fargo Everyday Checking"
            summary = "Wells Fargo Everyday Checking statement showing household cash activity."
        elif "chase.com/amazon" in text_lower or "autopay is on" in text_lower:
            inferred_source = "credit_card"
            inferred_document = "statement"
            confidence = 0.86
            structured_data["account_hint"] = "Chase Amazon card"
            summary = "Chase Amazon credit-card statement with monthly household spending."
        elif "brokerage" in text_lower or "positions" in text_lower or "dividends" in text_lower:
            inferred_source = "brokerage"
            inferred_document = "brokerage_statement"
            confidence = 0.8
            summary = "Brokerage statement with investable assets and account activity."
        elif "ira" in text_lower or "401(k)" in text_lower or "retirement" in text_lower:
            inferred_source = "retirement"
            inferred_document = "retirement_statement"
            confidence = 0.8
            summary = "Retirement account statement for long-term planning."
        elif "invoice" in text_lower or "amount due" in text_lower or "bill" in text_lower:
            inferred_source = "billing"
            inferred_document = "invoice"
            confidence = 0.78
            summary = "Billing document with payment obligation."

        statement_period = self._extract_statement_period(extracted_text)
        if statement_period:
            structured_data["statement_period"] = statement_period

        total_amount = self._extract_total_amount(extracted_text)
        if total_amount:
            structured_data["total_amount"] = total_amount

        questions = self._build_questions(
            source_type=inferred_source,
            document_type=inferred_document,
            summary=summary,
            merchant=structured_data.get("merchant"),
            account_hint=structured_data.get("account_hint"),
        )

        return {
            "summary": summary,
            "document_type": inferred_document,
            "source_type": inferred_source,
            "confidence": confidence,
            "structured_data": structured_data,
            "inferred_values": [],
            "questions": questions,
        }

    def build_signature_candidates(
        self,
        *,
        filename: str,
        extracted_text: str | None,
    ) -> list[tuple[str, str, dict[str, Any]]]:
        candidates: list[tuple[str, str, dict[str, Any]]] = []
        filename_signature = self._filename_pattern_signature(filename)
        if filename_signature is not None:
            candidates.append(filename_signature)
        if not extracted_text:
            return candidates

        filename_lower = filename.lower()
        if filename_lower.endswith(".csv"):
            first_line = next(
                (line.strip() for line in extracted_text.splitlines() if line.strip()),
                "",
            )
            if first_line:
                normalized = "|".join(
                    cell.strip().lower().replace(" ", "_")
                    for cell in first_line.split(",")[:20]
                )
                if normalized:
                    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
                    candidates.append(
                        (
                            "csv_header",
                            f"csv_header::{digest}",
                            {"normalized_headers": normalized},
                        )
                    )
        return candidates

    def _filename_pattern_signature(
        self,
        filename: str,
    ) -> tuple[str, str, dict[str, Any]] | None:
        normalized = re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower())
        normalized = re.sub(r"\d", "#", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if sum(character.isalpha() for character in normalized) < 4:
            return None
        return (
            "filename_pattern",
            f"filename_pattern::{normalized}",
            {"normalized_filename": normalized},
        )

    def _signature_review(
        self,
        *,
        filename: str,
        extracted_text: str | None,
    ) -> dict[str, Any] | None:
        candidates = self.build_signature_candidates(
            filename=filename,
            extracted_text=extracted_text,
        )
        if not candidates:
            return None

        signature = self._find_signature([signature_key for _, signature_key, _ in candidates])
        if signature is None:
            return None

        confidence = float(signature["confidence"] or 0.0)
        threshold = self._signature_threshold(str(signature["signature_type"]))
        if confidence < threshold:
            return None

        structured_data = {
            "merchant": signature["merchant"],
            "account_hint": signature["account_hint"],
            "text_preview": extracted_text[:500] if extracted_text else None,
        }
        questions = self._build_questions(
            source_type=signature["source_type"],
            document_type=signature["document_type"],
            summary="Matched a previously learned document signature for this household.",
            merchant=signature["merchant"],
            account_hint=signature["account_hint"],
        )
        self._touch_signature(signature["id"])
        return {
            "summary": (
                f"Matched learned {signature['signature_type'].replace('_', ' ')} signature "
                f"for {signature['document_type'].replace('_', ' ')} from "
                f"{signature['source_type'].replace('_', ' ')}."
            ),
            "document_type": signature["document_type"],
            "source_type": signature["source_type"],
            "confidence": confidence,
            "structured_data": structured_data,
            "inferred_values": [],
            "questions": questions,
        }

    def _signature_threshold(self, signature_type: str) -> float:
        if signature_type == "filename_pattern":
            return 0.94
        return 0.9

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

    def _extract_statement_period(self, extracted_text: str | None) -> str | None:
        if not extracted_text:
            return None
        period_match = re.search(
            r"([A-Z][a-z]+ \d{1,2}, \d{4}\s*(?:-|to)\s*[A-Z][a-z]+ \d{1,2}, \d{4})",
            extracted_text,
        )
        if period_match:
            return period_match.group(1)
        return None

    def _extract_total_amount(self, extracted_text: str | None) -> str | None:
        if not extracted_text:
            return None
        amount_match = re.search(
            r"(?:new balance|amount due|order total|total)\s*[:$]?\s*\$?([0-9][0-9,]*\.\d{2})",
            extracted_text,
            flags=re.IGNORECASE,
        )
        if amount_match:
            return amount_match.group(1)
        return None

    def _build_questions(
        self,
        *,
        source_type: str,
        document_type: str,
        summary: str,
        merchant: Any,
        account_hint: Any,
    ) -> list[dict[str, Any]]:
        questions = [
            {
                "field_name": None,
                "question": "What role should this document play in the household plan?",
                "priority": "medium",
                "recommendation": "Confirm whether Jenny should use this for budgeting, cash-flow tracking, savings analysis, or only as a reference.",
                "rationale": "Jenny could not confidently infer the full financial meaning from the file alone.",
            }
        ]
        if source_type == "receipt" and isinstance(merchant, str) and merchant:
            return [
                {
                    "field_name": None,
                    "question": f"Should Jenny treat {merchant} orders like this as part of regular household spending?",
                    "priority": "medium",
                    "recommendation": f"Answer 'yes' if {merchant} is a recurring household shopping channel for groceries, consumables, or home goods.",
                    "rationale": "This helps Jenny separate recurring household shopping from one-off discretionary purchases.",
                }
            ]
        if source_type == "bank" and isinstance(account_hint, str) and account_hint:
            return [
                {
                    "field_name": "monthly_essential_target",
                    "question": f"Is {account_hint} your primary account for monthly bills, deposits, and budget tracking?",
                    "priority": "high",
                    "recommendation": "Answer 'yes' if most paycheck deposits, bill payments, and core household cash flow pass through this account.",
                    "rationale": "Primary checking accounts anchor the household cash-flow model.",
                }
            ]
        if source_type == "credit_card" and isinstance(account_hint, str) and account_hint:
            return [
                {
                    "field_name": "monthly_essential_target",
                    "question": f"Should Jenny treat {account_hint} as part of core household spending?",
                    "priority": "high",
                    "recommendation": "Answer 'yes' if this card is used for regular groceries, household shopping, subscriptions, or recurring family spending.",
                    "rationale": "This determines whether Jenny should treat the card as budget-driving spend data.",
                }
            ]
        if source_type == "other" or document_type == "other":
            questions.append(
                {
                    "field_name": None,
                    "question": "What kind of document is this and which account or merchant is it tied to?",
                    "priority": "high",
                    "recommendation": "Name the merchant or institution and say whether this is a receipt, order confirmation, or statement.",
                    "rationale": "Jenny could not confidently identify the institution, account, or document class from the file alone.",
                }
            )
        if source_type in {"bank", "credit_card"}:
            questions.append(
                {
                    "field_name": "monthly_essential_target",
                    "question": "Is this account part of your core monthly household spending?",
                    "priority": "high",
                    "recommendation": "Confirm if this account covers regular household bills, groceries, or everyday spending.",
                    "rationale": "This determines whether Jenny should treat the spend as budget-driving data.",
                }
            )
        if source_type in {"retirement", "brokerage"}:
            questions.append(
                {
                    "field_name": "target_retirement_spend",
                    "question": "Should this account count toward retirement readiness tracking?",
                    "priority": "medium",
                    "recommendation": "Confirm if this is a retirement or long-term investment account that should shape future-income planning.",
                    "rationale": "Jenny needs to know whether the account is part of the retirement plan or general savings.",
                }
            )
        if "keep refining" not in summary.lower():
            questions[0]["rationale"] = f"{questions[0]['rationale']} Current best read: {summary}"
        return questions
