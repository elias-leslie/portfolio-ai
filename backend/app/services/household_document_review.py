"""Jenny-led household document review and inference generation."""

from __future__ import annotations

import base64
import csv
import json
from pathlib import Path
from typing import Any

from agent_hub.models.content import ImageContent, MessageInput, TextContent
from pypdf import PdfReader

from app.agents.clients.agent_hub_client import AGENT_HUB_ENABLED, AgentHubAPIClient
from app.logging_config import get_logger

logger = get_logger(__name__)

JSON_REVIEW_INSTRUCTIONS = """Review the household finance document and return strict JSON only.

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
      "rationale": "why this needs confirmation"
    }
  ]
}

Only infer values if the evidence is strong. Ask targeted questions for ambiguity.
"""


class HouseholdDocumentReviewService:
    """Extract review data from uploaded household documents."""

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
        payload = {
            "document_id": document_id,
            "filename": filename,
            "source_type": source_type,
            "document_type": document_type,
            "content_type": content_type,
        }

        if AGENT_HUB_ENABLED:
            reviewed = self._review_with_llm(
                payload=payload,
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
            )
            if reviewed is not None:
                reviewed.setdefault("structured_data", {})
                reviewed.setdefault("inferred_values", [])
                reviewed.setdefault("questions", [])
                reviewed["extracted_text"] = extracted_text
                return reviewed

        return self._fallback_review(
            payload=payload,
            extracted_text=extracted_text,
        )

    def _review_with_llm(
        self,
        *,
        payload: dict[str, Any],
        stored_path: Path,
        content_type: str | None,
        extracted_text: str | None,
    ) -> dict[str, Any] | None:
        try:
            client = AgentHubAPIClient(agent_slug="chat", use_memory=False)
            messages = self._build_messages(
                payload=payload,
                stored_path=stored_path,
                content_type=content_type,
                extracted_text=extracted_text,
            )
            response = client._client.complete(
                project_id="portfolio-ai",
                agent_slug="chat",
                model="claude-sonnet-4-5",
                messages=messages,
                temperature=0.2,
                timeout_seconds=90,
                purpose="household_document_review",
                use_memory=False,
                system_prompt=JSON_REVIEW_INSTRUCTIONS,
            )
            return json.loads(response.content)
        except Exception as exc:
            logger.warning("household_document_review_llm_failed", error=str(exc))
            return None

    def _build_messages(
        self,
        *,
        payload: dict[str, Any],
        stored_path: Path,
        content_type: str | None,
        extracted_text: str | None,
    ) -> list[MessageInput]:
        content_blocks: list[Any] = [
            TextContent(
                text=(
                    "Document metadata:\n"
                    f"{json.dumps(payload, indent=2)}\n\n"
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

        if content_type and content_type.startswith("image/"):
            content_blocks.append(self._image_block(stored_path, content_type))

        return [MessageInput(role="user", content=content_blocks)]

    def _image_block(self, stored_path: Path, content_type: str) -> ImageContent:
        encoded = base64.b64encode(stored_path.read_bytes()).decode("utf-8")
        return ImageContent.from_base64(encoded, media_type=content_type)

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
                rows.append(", ".join(cell.strip() for cell in row[:12]))
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

    def _fallback_review(
        self,
        *,
        payload: dict[str, Any],
        extracted_text: str | None,
    ) -> dict[str, Any]:
        summary = (
            f"Uploaded {payload['document_type'].replace('_', ' ')} from {payload['source_type'].replace('_', ' ')}."
        )
        questions = [
            {
                "field_name": None,
                "question": "What role should this document play in the household plan?",
                "priority": "medium",
                "rationale": "Jenny could not confidently infer the full financial meaning from the file alone.",
            }
        ]
        if payload["source_type"] in {"bank", "credit_card"}:
            questions.append(
                {
                    "field_name": "monthly_essential_target",
                    "question": "Is this account part of your core monthly household spending?",
                    "priority": "high",
                    "rationale": "This determines whether Jenny should treat the spend as budget-driving data.",
                }
            )
        if payload["source_type"] in {"retirement", "brokerage"}:
            questions.append(
                {
                    "field_name": "target_retirement_spend",
                    "question": "Should this account count toward retirement readiness tracking?",
                    "priority": "medium",
                    "rationale": "Jenny needs to know whether the account is part of the retirement plan or general savings.",
                }
            )
        return {
            "summary": summary,
            "document_type": payload["document_type"],
            "source_type": payload["source_type"],
            "confidence": 0.45,
            "structured_data": {
                "text_preview": extracted_text[:500] if extracted_text else None,
            },
            "inferred_values": [],
            "questions": questions,
            "extracted_text": extracted_text,
        }
