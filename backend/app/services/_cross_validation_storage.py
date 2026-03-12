"""Database storage operations for cross-validation results."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager
from ._cross_validation_models import DisagreementReason, ValidationResult, ValidationStatus

logger = get_logger(__name__)


def save_result(result: ValidationResult) -> None:
    """Save validation result to database."""
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            conn.execute(
                """
                INSERT INTO cross_validation_results (
                    id, created_at, generator_provider, generator_model,
                    generator_output, generator_confidence, validator_provider,
                    validator_model, validator_review, validator_approved,
                    validator_confidence, has_disagreement, disagreement_reasons,
                    disagreement_details, status, resolved_at, resolved_by,
                    final_output, context_type, context_symbol, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    result.id,
                    result.created_at,
                    result.generator_provider,
                    result.generator_model,
                    result.generator_output,
                    result.generator_confidence,
                    result.validator_provider,
                    result.validator_model,
                    result.validator_review,
                    result.validator_approved,
                    result.validator_confidence,
                    result.has_disagreement,
                    json.dumps([r.value for r in result.disagreement_reasons]),
                    result.disagreement_details,
                    result.status.value,
                    result.resolved_at,
                    result.resolved_by,
                    result.final_output,
                    result.context_type,
                    result.context_symbol,
                    json.dumps(result.metadata),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.error("save_validation_result_failed", error=str(e), exc_info=True)


def row_to_result(row: Any) -> ValidationResult:
    """Convert database row (tuple) to ValidationResult.

    Column order from SELECT *:
    0: id, 1: created_at, 2: generator_provider, 3: generator_model,
    4: generator_output, 5: generator_confidence, 6: validator_provider,
    7: validator_model, 8: validator_review, 9: validator_approved,
    10: validator_confidence, 11: has_disagreement, 12: disagreement_reasons,
    13: disagreement_details, 14: status, 15: resolved_at, 16: resolved_by,
    17: final_output, 18: context_type, 19: context_symbol, 20: metadata
    """
    created_at = row[1]
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()

    resolved_at = row[15]
    if resolved_at and hasattr(resolved_at, "isoformat"):
        resolved_at = resolved_at.isoformat()

    disagreement_reasons_raw = row[12]
    if isinstance(disagreement_reasons_raw, str):
        disagreement_reasons_raw = json.loads(disagreement_reasons_raw or "[]")
    elif disagreement_reasons_raw is None:
        disagreement_reasons_raw = []

    metadata_raw = row[20]
    if isinstance(metadata_raw, str):
        metadata_raw = json.loads(metadata_raw or "{}")
    elif metadata_raw is None:
        metadata_raw = {}

    return ValidationResult(
        id=row[0],
        created_at=created_at,
        generator_provider=row[2],
        generator_model=row[3] or "",
        generator_output=row[4],
        generator_confidence=row[5],
        validator_provider=row[6],
        validator_model=row[7] or "",
        validator_review=row[8],
        validator_approved=row[9],
        validator_confidence=row[10],
        has_disagreement=row[11],
        disagreement_reasons=[DisagreementReason(r) for r in disagreement_reasons_raw],
        disagreement_details=row[13],
        status=ValidationStatus(row[14]),
        resolved_at=resolved_at,
        resolved_by=row[16],
        final_output=row[17],
        context_type=row[18],
        context_symbol=row[19],
        metadata=metadata_raw,
    )


def get_pending_validations(limit: int = 50) -> list[ValidationResult]:
    """Get pending validations awaiting human review."""
    conn_mgr = get_connection_manager()
    results = []
    try:
        with conn_mgr.connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM cross_validation_results
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (ValidationStatus.PENDING.value, limit),
            )
            for db_row in cursor.fetchall():
                results.append(row_to_result(db_row))
    except Exception as e:
        logger.error("get_pending_validations_failed", error=str(e), exc_info=True)
    return results


def resolve_validation(
    validation_id: str,
    approved: bool,
    final_output: str | None = None,
    resolved_by: str = "human",
) -> ValidationResult | None:
    """Resolve a pending validation.

    Args:
        validation_id: ID of validation to resolve
        approved: Whether to approve
        final_output: Modified output (if any)
        resolved_by: Who resolved ("human" or "auto")

    Returns:
        Updated ValidationResult or None if not found
    """
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM cross_validation_results WHERE id = %s",
                (validation_id,),
            )
            db_row = cursor.fetchone()
            if not db_row:
                return None

            result = row_to_result(db_row)
            new_status = _compute_resolve_status(approved, final_output, result.generator_output)
            now = datetime.now(UTC).isoformat()

            conn.execute(
                """
                UPDATE cross_validation_results
                SET status = %s, resolved_at = %s, resolved_by = %s, final_output = %s
                WHERE id = %s
                """,
                (
                    new_status.value,
                    now,
                    resolved_by,
                    final_output or result.generator_output,
                    validation_id,
                ),
            )
            conn.commit()

            result.status = new_status
            result.resolved_at = now
            result.resolved_by = resolved_by
            result.final_output = final_output or result.generator_output

            logger.info(
                "validation_resolved",
                validation_id=validation_id,
                status=new_status.value,
                resolved_by=resolved_by,
            )
            return result

    except Exception as e:
        logger.error("resolve_validation_failed", error=str(e), validation_id=validation_id, exc_info=True)
        return None


def _compute_resolve_status(
    approved: bool,
    final_output: str | None,
    generator_output: str,
) -> ValidationStatus:
    """Determine new status when resolving a validation."""
    if not approved:
        return ValidationStatus.REJECTED
    if final_output and final_output != generator_output:
        return ValidationStatus.MODIFIED
    return ValidationStatus.APPROVED
