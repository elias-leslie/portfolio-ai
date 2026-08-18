"""Redaction must hide identifiers without eating the numbers the reviewer needs."""

from __future__ import annotations

import pytest

from app.services._household_document_llm import _build_messages
from app.services.household_document_redaction import (
    redact_sensitive_text,
    redact_sensitive_value,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SSN: 123-45-6789", "SSN: [redacted-ssn]"),
        ("SSN 123 45 6789 on file", "SSN [redacted-ssn] on file"),
        ("Account 1234567890123", "Account ••••0123"),
        ("Card 4111 1111 1111 1111", "Card ••••1111"),
        ("Acct 4111-1111-1111-1111", "Acct ••••1111"),
        ("Routing 063100277", "Routing ••••0277"),
        ("Account number 12345678901.", "Account number ••••8901."),
    ],
)
def test_identifier_shapes_are_masked(raw: str, expected: str) -> None:
    assert redact_sensitive_text(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "Total 171.31, tax 12.04, subtotal 159.27",
        "Statement period 2026-08-01 through 2026-08-31",
        "Posted 08/18/2026 for 1,234.56",
        "Largo FL 33770",
        "Qty 12 at 4.50 each",
        "Balance 12345678.90",
    ],
)
def test_reviewer_relevant_numbers_survive(raw: str) -> None:
    assert redact_sensitive_text(raw) == raw


def test_walker_covers_nested_strings_and_bare_ints() -> None:
    payload = {
        "account_mask": "1234567890",
        "amount": 171.31,
        "account_number": 9876543210,
        "flagged": True,
        "lines": [{"description": "RXBAR", "code": 1761722}],
    }

    assert redact_sensitive_value(payload) == {
        "account_mask": "••••7890",
        "amount": 171.31,
        "account_number": "••••3210",
        "flagged": True,
        "lines": [{"description": "RXBAR", "code": 1761722}],
    }


def test_built_prompt_carries_no_full_account_number(tmp_path) -> None:
    messages = _build_messages(
        payload={"filename": "fidelity_statement.pdf", "account_label": "Brokerage 1234567890"},
        stored_path=tmp_path / "missing.pdf",
        content_type="application/pdf",
        extracted_text="Account 1234567890\nSSN 123-45-6789\nEnding balance 41,208.19",
        baseline_review={"account_mask": "1234567890"},
    )

    prompt = messages[0].content
    assert isinstance(prompt, str)
    assert "1234567890" not in prompt
    assert "123-45-6789" not in prompt
    assert "[redacted-ssn]" in prompt
    assert "••••7890" in prompt
    # The reviewer still needs the money.
    assert "41,208.19" in prompt


def test_static_prompt_examples_are_not_redacted(tmp_path) -> None:
    """The warehouse-markdown instruction quotes a real item code; keep it intact."""
    messages = _build_messages(
        payload={"filename": "costco.jpg"},
        stored_path=tmp_path / "missing.jpg",
        content_type="image/jpeg",
        extracted_text=None,
        baseline_review={},
    )

    prompt = messages[0].content
    assert isinstance(prompt, str)
    assert "0000388263 / 1761722" in prompt
