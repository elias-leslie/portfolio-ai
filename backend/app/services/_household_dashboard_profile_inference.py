"""Transaction-driven household profile inference helpers."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import HouseholdProfile, HouseholdReports
from app.services._household_dashboard_query_sql import INCOME_MONTHLY_AVG_SQL

logger = get_logger(__name__)


def confidence_for_months(month_count: int) -> float:
    if month_count <= 0:
        return 0.0
    if month_count == 1:
        return 0.6
    if month_count == 2:
        return 0.75
    return 0.85


def build_inferences(
    avg_monthly_income: float,
    income_months: int,
    income_confidence: float,
    avg_essential: float,
    avg_discretionary: float,
    avg_savings: float,
    coverage_months: int,
    confidence: float,
) -> list[tuple[str, float, float, str]]:
    inferences: list[tuple[str, float, float, str]] = []
    if avg_monthly_income > 0:
        inferences.append((
            "monthly_net_income_target", avg_monthly_income, income_confidence,
            f"I see ~${avg_monthly_income:,.0f}/mo income across {income_months} month{'s' if income_months != 1 else ''} of deposit data.",
        ))
    if avg_essential > 0:
        inferences.append((
            "monthly_essential_target", avg_essential, confidence,
            f"I see ~${avg_essential:,.0f}/mo in essential spending across {coverage_months} month{'s' if coverage_months != 1 else ''} of transaction data.",
        ))
    if avg_discretionary > 0:
        inferences.append((
            "monthly_discretionary_target", avg_discretionary, confidence,
            f"I see ~${avg_discretionary:,.0f}/mo in discretionary spending across {coverage_months} month{'s' if coverage_months != 1 else ''} of transaction data.",
        ))
    if avg_savings > 0:
        total_spending = avg_essential + avg_discretionary
        inferences.append((
            "monthly_savings_target", avg_savings, min(income_confidence, confidence),
            f"Based on ~${avg_monthly_income:,.0f}/mo income minus ~${total_spending:,.0f}/mo spending, implied savings capacity is ~${avg_savings:,.0f}/mo.",
        ))
    return inferences


def _update_inference(conn: Any, field_name: str, rounded_value: float, confidence: float, rationale: str, metadata_json: str, now: str) -> None:
    conn.execute(
        """
        UPDATE household_inferred_values
        SET value_text = %s, confidence = %s, rationale = %s,
            metadata = %s::jsonb, updated_at = %s
        WHERE field_name = %s
          AND metadata->>'source' = 'transaction_inference'
        """,
        [str(rounded_value), confidence, rationale, metadata_json, now, field_name],
    )


def _insert_inference(conn: Any, field_name: str, rounded_value: float, confidence: float, rationale: str, metadata_json: str, now: str) -> None:
    conn.execute(
        """
        INSERT INTO household_inferred_values (
            id, field_name, value_text, confidence, status, rationale,
            source_document_id, metadata, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        """,
        [
            str(uuid.uuid4()), field_name, str(rounded_value),
            confidence, "inferred", rationale, None, metadata_json, now, now,
        ],
    )


def upsert_transaction_inference(
    conn: Any,
    *,
    field_name: str,
    value: float,
    confidence: float,
    rationale: str,
    existing_inferences: dict[str, dict[str, Any]],
    profile: HouseholdProfile,
) -> bool:
    if getattr(profile, field_name, None) is not None:
        return False
    existing = existing_inferences.get(field_name)
    if existing is not None:
        existing_confidence = float(existing.get("confidence") or 0.0)
        if existing_confidence >= confidence and existing.get("source", "") != "transaction_inference":
            return False
    rounded_value = round(value, 2)
    now = datetime.now(UTC).isoformat()
    metadata_json = json.dumps({"source": "transaction_inference"})
    if existing is not None and existing.get("source") == "transaction_inference":
        _update_inference(conn, field_name, rounded_value, confidence, rationale, metadata_json, now)
        return True
    _insert_inference(conn, field_name, rounded_value, confidence, rationale, metadata_json, now)
    return True


def _income_metrics(storage: Any) -> tuple[int, float]:
    with storage.connection() as conn:
        income_row = conn.execute(INCOME_MONTHLY_AVG_SQL).fetchone()
    income_months = int(income_row[0] or 0) if income_row else 0
    avg_monthly_income = float(income_row[1] or 0.0) if income_row else 0.0
    return income_months, avg_monthly_income


def _report_metrics(reports: HouseholdReports, avg_monthly_income: float) -> tuple[int, float, float, float]:
    coverage_months = reports.executive.coverage_months
    avg_essential = reports.executive.average_monthly_essentials
    avg_discretionary = reports.executive.average_monthly_discretionary
    avg_savings = max(avg_monthly_income - avg_essential - avg_discretionary, 0.0) if avg_monthly_income > 0 else 0.0
    return coverage_months, avg_essential, avg_discretionary, avg_savings


def infer_profile_from_transactions(
    storage: Any,
    *,
    profile: HouseholdProfile,
    reports: HouseholdReports,
    existing_inferences: dict[str, dict[str, Any]],
) -> None:
    income_months, avg_monthly_income = _income_metrics(storage)
    coverage_months, avg_essential, avg_discretionary, avg_savings = _report_metrics(
        reports,
        avg_monthly_income,
    )
    if coverage_months < 1:
        return
    inferences = build_inferences(
        avg_monthly_income,
        income_months,
        confidence_for_months(income_months),
        avg_essential,
        avg_discretionary,
        avg_savings,
        coverage_months,
        confidence_for_months(coverage_months),
    )
    if not inferences:
        return
    updated = False
    with storage.connection() as conn:
        for field_name, value, confidence, rationale in inferences:
            if not upsert_transaction_inference(
                conn,
                field_name=field_name,
                value=value,
                confidence=confidence,
                rationale=rationale,
                existing_inferences=existing_inferences,
                profile=profile,
            ):
                continue
            updated = True
            logger.info(
                "transaction_inference_upserted",
                field_name=field_name,
                value=round(value, 2),
                confidence=confidence,
            )
        if updated:
            conn.commit()
