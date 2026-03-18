"""Shared utility and normalizer functions for household finance service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.household_finance import HouseholdResolvedValue


def iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return iso(value)


def to_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def to_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def normalize_priority(value: Any) -> str:
    priority = str(value or "medium").strip().lower()
    if priority not in {"high", "medium", "low"}:
        return "medium"
    return priority


def normalize_question_format(value: Any) -> str:
    question_format = str(value or "short_text").strip().lower()
    aliases = {
        "text": "short_text",
        "number": "integer",
        "yes_no": "boolean",
        "multiple_choice": "single_select",
    }
    normalized = aliases.get(question_format, question_format)
    if normalized not in {
        "short_text",
        "long_text",
        "boolean",
        "integer",
        "currency",
        "single_select",
        "multi_select",
        "date",
    }:
        return "short_text"
    return normalized


def normalize_question_options(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    options = [str(item).strip() for item in value if str(item).strip()]
    return options or None


def normalize_question_direction(value: Any) -> str:
    direction = str(value or "jenny_to_user").strip().lower()
    if direction not in {"jenny_to_user", "user_to_jenny"}:
        return "jenny_to_user"
    return direction


def resolved_numeric_value(
    resolved_values: list[HouseholdResolvedValue],
    field_name: str,
) -> float | None:
    for value in resolved_values:
        if value.field_name != field_name or value.value is None:
            continue
        try:
            return float(str(value.value).replace(",", ""))
        except ValueError:
            return None
    return None
