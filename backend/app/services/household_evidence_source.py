"""Read the exact review's source and arithmetic without applying any proposal."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException

from app.services._household_document_pipeline_receipt import (
    _decimal_value,
    _first_present_value,
    _fold_receipt_markdowns,
    _merge_receipt_discounts,
    _receipt_line_item_amounts,
)
from app.storage import get_storage


def _amount(value: object) -> float | None:
    parsed = _decimal_value(value)
    return float(parsed) if parsed is not None and parsed.is_finite() else None


def receipt_arithmetic(structured: dict[str, Any]) -> list[dict[str, object]]:
    raw = structured.get("transactions")
    transactions = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    if isinstance(structured.get("line_items"), list):
        transactions.append(structured)
    result = []
    for row in transactions:
        lines = row.get("line_items")
        if not isinstance(lines, list) or not lines:
            continue
        try:
            merged = _merge_receipt_discounts(_fold_receipt_markdowns(lines), row.get("discounts"))
            amounts = _receipt_line_item_amounts(merged)
        except (InvalidOperation, ValueError):
            continue
        if any(not value.is_finite() for value in amounts):
            continue
        net = float(sum(amounts, Decimal("0"))) if amounts else None
        subtotal = _amount(_first_present_value(row, ("subtotal", "subtotal_amount")))
        tax = _amount(
            row.get("tax_amount") if row.get("tax_amount") is not None else row.get("tax")
        )
        total = _amount(_first_present_value(row, ("amount", "total_amount", "total")))
        result.append(
            {
                "merchant": str(row.get("merchant") or structured.get("merchant") or "Receipt"),
                "readable_lines": len(amounts),
                "line_total": net,
                "subtotal": subtotal,
                "tax": tax,
                "total": total,
                "line_difference": round(net - subtotal, 2)
                if net is not None and subtotal is not None
                else None,
                "total_difference": round(subtotal + tax - total, 2)
                if subtotal is not None and tax is not None and total is not None
                else None,
            }
        )
    return result


def read_evidence_source(
    document_id: str, *, review_id: str | None = None, search: str = ""
) -> dict[str, Any]:
    with get_storage().connection() as conn:
        exists = conn.execute(
            "SELECT id FROM household_documents WHERE id=%s", [document_id]
        ).fetchone()
        if not exists:
            raise HTTPException(404, "Evidence document not found.")
        row = conn.execute(
            """SELECT id::text, extracted_text, structured_data, review_payload
            FROM household_document_reviews WHERE document_id=%s
            AND (%s::text IS NULL OR id::text=%s)
            ORDER BY created_at DESC,id DESC LIMIT 1""",
            [document_id, review_id, review_id],
        ).fetchone()
    if not row:
        if review_id:
            raise HTTPException(
                404, "The source for this review is unavailable. Refresh the evidence."
            )
        return {
            "review_id": None,
            "text": "",
            "truncated": False,
            "questions": [],
            "arithmetic": [],
        }
    text = str(row[1] or "")
    if search.strip():
        lines = text.splitlines()
        matched = [
            index
            for index, line in enumerate(lines)
            if search.strip().casefold() in line.casefold()
        ]
        indexes = sorted(
            {
                i
                for index in matched[:10]
                for i in range(max(0, index - 2), min(len(lines), index + 3))
            }
        )
        text = "\n".join(f"{i + 1}: {lines[i]}" for i in indexes)
    structured = row[2] if isinstance(row[2], dict) else {}
    payload = row[3] if isinstance(row[3], dict) else {}
    questions = payload.get("questions")
    return {
        "review_id": row[0],
        "text": text[:6000],
        "truncated": len(text) > 6000,
        "questions": [
            str(q.get("question")) for q in questions if isinstance(q, dict) and q.get("question")
        ]
        if isinstance(questions, list)
        else [],
        "arithmetic": receipt_arithmetic(structured),
    }
