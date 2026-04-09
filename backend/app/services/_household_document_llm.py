"""LLM message building and response parsing for household document review."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from agent_hub.models.content import ImageContent, MessageInput, TextContent

from app.logging_config import get_logger
from app.services._household_document_text import _render_pdf_pages_to_png

logger = get_logger(__name__)

JSON_REVIEW_INSTRUCTIONS = """Return strict JSON only for this household finance document review.

Schema:
{
  "summary": "short summary",
  "document_type": "statement|brokerage_statement|retirement_statement|pay_stub|w2_1099|tax_return|mortgage_statement|heloc_statement|student_loan_statement|auto_loan_statement|insurance_policy|insurance_declarations|social_security_statement|pension_statement|benefits_summary|major_expense_support|receipt|invoice|other",
  "source_type": "bank|credit_card|brokerage|retirement|income|tax|debt|housing|insurance|retirement_income|benefits|receipt|billing|other",
  "confidence": 0.0-1.0,
  "structured_data": {
    "merchant": "optional",
    "statement_period": "optional",
    "total_amount": "optional",
    "currency": "optional",
    "account_hint": "optional",
    "owner_name": "optional",
    "provider_name": "optional",
    "financial_accounts": [
      {
        "asset_group": "cash|retirement|taxable|education|debt|credit|other",
        "account_type": "checking|savings|credit_card|brokerage|retirement|ira|401k|roth_ira|529|loan|mortgage|other",
        "institution_name": "optional",
        "account_name": "optional",
        "account_mask": "optional",
        "owner_name": "optional",
        "currency": "optional",
        "balance": "optional numeric string",
        "holdings_value": "optional numeric string",
        "cash_balance": "optional numeric string",
        "as_of_date": "optional ISO date string",
        "confidence": 0.0-1.0,
        "holdings": [
          {
            "symbol": "optional",
            "description": "optional",
            "quantity": "optional numeric string",
            "market_value": "optional numeric string",
            "weight_pct": "optional numeric string"
          }
        ]
      }
    ]
  },
  "inferred_values": [
    {
      "field_name": "adult_count|dependent_count|monthly_net_income_target|monthly_essential_target|monthly_discretionary_target|monthly_savings_target|target_retirement_age|target_retirement_spend|filing_status|state_of_residence|effective_tax_rate|marginal_federal_tax_rate|marginal_state_tax_rate|emergency_fund_target_months|emergency_fund_target_amount",
      "value": "stringified value",
      "confidence": 0.0-1.0,
      "rationale": "why you inferred it"
    }
  ],
  "planning_items": [
    {
      "section": "members|income_sources|debt_obligations|housing_costs|insurance_policies|retirement_income_sources|planned_expenses",
      "label": "human-readable label",
      "source_type": "section-specific optional enum",
      "owner_name": "optional",
      "relationship": "optional",
      "role": "optional",
      "category": "optional",
      "pay_frequency": "optional",
      "employer_or_source": "optional",
      "lender": "optional",
      "carrier": "optional",
      "housing_type": "optional",
      "occupancy_role": "optional",
      "expense_kind": "optional",
      "monthly_amount": "optional numeric string",
      "annual_amount": "optional numeric string",
      "net_amount": "optional numeric string",
      "gross_amount": "optional numeric string",
      "monthly_payment": "optional numeric string",
      "balance": "optional numeric string",
      "interest_rate": "optional numeric string",
      "premium_monthly": "optional numeric string",
      "coverage_amount": "optional numeric string",
      "deductible": "optional numeric string",
      "target_amount": "optional numeric string",
      "target_date": "optional ISO date string",
      "monthly_saving_target": "optional numeric string",
      "start_age": "optional integer",
      "notes": "optional note",
      "rationale": "brief evidence note"
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
Only emit planning_items when the document clearly supports a durable planning row.
Only emit financial_accounts when the document clearly exposes a real account snapshot with enough information to update the money system.
"""


def _pdf_image_blocks(stored_path: Path) -> list[ImageContent]:
    blocks: list[ImageContent] = []
    try:
        for png_bytes in _render_pdf_pages_to_png(stored_path, scale=1.5, max_pages=2):
            blocks.append(
                ImageContent.from_base64(
                    base64.b64encode(png_bytes).decode("utf-8"),
                    media_type="image/png",
                )
            )
    except Exception as exc:
        logger.warning("household_pdf_preview_failed", path=str(stored_path), error=str(exc))
        return []
    return blocks


def _build_messages(
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
        content_blocks.append(TextContent(text=f"Extracted text preview:\n{extracted_text[:12000]}"))
    if stored_path.suffix.lower() == ".pdf" or content_type == "application/pdf":
        content_blocks.extend(_pdf_image_blocks(stored_path))
    if content_type and content_type.startswith("image/"):
        content_blocks.append(
            ImageContent.from_base64(
                base64.b64encode(stored_path.read_bytes()).decode("utf-8"),
                media_type=content_type,
            )
        )
    return [MessageInput(role="user", content=content_blocks)]


def _parse_review_payload(content: Any) -> dict[str, Any]:
    """Coerce LLM response content to text and extract the first valid JSON object."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        chunks = [item if isinstance(item, str) else getattr(item, "text", None) for item in content]
        text = "\n".join(c for c in chunks if isinstance(c, str) and c)
    else:
        text = str(content)

    candidates: list[str] = []
    for pattern in [r"```json\s*(\{.*?\})\s*```", r"```\s*(\{.*?\})\s*```"]:
        candidates.extend(re.findall(pattern, text, flags=re.DOTALL | re.IGNORECASE))
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError("No valid JSON object found in review payload")
