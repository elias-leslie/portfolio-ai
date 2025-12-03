"""Disagreement Detection API - Multi-LLM consensus tracking.

Provides endpoints for viewing and tracking disagreements between
Gemini and Claude LLM reviewers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/disagreements", tags=["disagreements"])

storage = get_storage()


class DisagreementItem(BaseModel):
    """Single disagreement between providers."""

    review_pair_id: str
    symbol: str
    created_at: str
    agreement_score: float
    disagreement_severity: str
    gemini_review: str | None
    claude_review: str | None
    consensus_summary: str


class DisagreementStats(BaseModel):
    """Statistics about provider disagreements."""

    total_reviews: int
    total_review_pairs: int
    agreement_count: int
    minor_disagreement_count: int
    major_disagreement_count: int
    agreement_rate: float
    minor_disagreement_rate: float
    major_disagreement_rate: float
    avg_agreement_score: float
    trend_7d: list[dict[str, Any]]


class DisagreementsResponse(BaseModel):
    """Response for disagreements list endpoint."""

    items: list[DisagreementItem]
    total: int


@router.get("", response_model=DisagreementsResponse)
async def list_disagreements(
    days: int = 7,
    severity: str | None = None,
    limit: int = 50,
) -> DisagreementsResponse:
    """List recent provider disagreements.

    Args:
        days: Number of days to look back (default 7)
        severity: Filter by severity (minor, major, or None for all)
        limit: Maximum number of results (default 50)

    Returns:
        List of disagreements with both provider reviews
    """
    try:
        since = datetime.now(UTC) - timedelta(days=days)

        # Build query with optional severity filter
        severity_clause = ""
        params: list[Any] = [since, limit]
        if severity:
            severity_clause = "AND disagreement_severity = ?"
            params = [since, severity, limit]

        # Get disagreements (grouped by review_pair_id)
        query = f"""
            SELECT
                review_pair_id,
                symbol,
                MAX(created_at) as created_at,
                AVG(agreement_score) as agreement_score,
                MAX(disagreement_severity) as disagreement_severity,
                MAX(CASE WHEN provider = 'gemini' THEN review_text END) as gemini_review,
                MAX(CASE WHEN provider = 'claude' THEN review_text END) as claude_review
            FROM strategy_reviews
            WHERE created_at >= ?
                AND review_pair_id IS NOT NULL
                AND provider_disagreement = true
                {severity_clause}
            GROUP BY review_pair_id, symbol
            ORDER BY created_at DESC
            LIMIT ?
        """

        df = storage.query(query, params)

        items: list[DisagreementItem] = []
        for row in df.to_dicts():
            severity_val = row.get("disagreement_severity", "minor")
            summary = _generate_summary(severity_val)
            items.append(
                DisagreementItem(
                    review_pair_id=row["review_pair_id"],
                    symbol=row["symbol"],
                    created_at=str(row["created_at"]),
                    agreement_score=float(row.get("agreement_score") or 0.0),
                    disagreement_severity=severity_val,
                    gemini_review=row.get("gemini_review"),
                    claude_review=row.get("claude_review"),
                    consensus_summary=summary,
                )
            )

        return DisagreementsResponse(items=items, total=len(items))

    except Exception as e:
        logger.error(f"Failed to list disagreements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/stats", response_model=DisagreementStats)
async def get_disagreement_stats(days: int = 30) -> DisagreementStats:
    """Get disagreement statistics and trends.

    Args:
        days: Number of days to analyze (default 30)

    Returns:
        Statistics including rates and 7-day trend
    """
    try:
        since = datetime.now(UTC) - timedelta(days=days)

        # Get overall stats
        stats_query = """
            SELECT
                COUNT(*) as total_reviews,
                COUNT(DISTINCT review_pair_id) as total_pairs,
                SUM(CASE WHEN disagreement_severity = 'none' OR disagreement_severity IS NULL THEN 1 ELSE 0 END) as agreement_count,
                SUM(CASE WHEN disagreement_severity = 'minor' THEN 1 ELSE 0 END) as minor_count,
                SUM(CASE WHEN disagreement_severity = 'major' THEN 1 ELSE 0 END) as major_count,
                AVG(agreement_score) as avg_agreement
            FROM strategy_reviews
            WHERE created_at >= ?
        """

        stats_df = storage.query(stats_query, [since])
        stats_row = stats_df.to_dicts()[0] if not stats_df.is_empty() else {}

        total = int(stats_row.get("total_reviews") or 0)
        pairs = int(stats_row.get("total_pairs") or 0)
        agreement = int(stats_row.get("agreement_count") or 0)
        minor = int(stats_row.get("minor_count") or 0)
        major = int(stats_row.get("major_count") or 0)
        avg_score = float(stats_row.get("avg_agreement") or 0.0)

        # Calculate rates
        agreement_rate = agreement / total if total > 0 else 1.0
        minor_rate = minor / total if total > 0 else 0.0
        major_rate = major / total if total > 0 else 0.0

        # Get 7-day trend
        trend_query = """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as reviews,
                SUM(CASE WHEN provider_disagreement = true THEN 1 ELSE 0 END) as disagreements,
                AVG(agreement_score) as avg_score
            FROM strategy_reviews
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 7
        """

        trend_since = datetime.now(UTC) - timedelta(days=7)
        trend_df = storage.query(trend_query, [trend_since])

        trend = [
            {
                "date": str(row["date"]),
                "reviews": row["reviews"],
                "disagreements": row["disagreements"],
                "avg_score": float(row.get("avg_score") or 0.0),
            }
            for row in trend_df.to_dicts()
        ]

        return DisagreementStats(
            total_reviews=total,
            total_review_pairs=pairs,
            agreement_count=agreement,
            minor_disagreement_count=minor,
            major_disagreement_count=major,
            agreement_rate=agreement_rate,
            minor_disagreement_rate=minor_rate,
            major_disagreement_rate=major_rate,
            avg_agreement_score=avg_score,
            trend_7d=trend,
        )

    except Exception as e:
        logger.error(f"Failed to get disagreement stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{symbol}", response_model=DisagreementsResponse)
async def get_symbol_disagreements(
    symbol: str,
    days: int = 30,
) -> DisagreementsResponse:
    """Get disagreements for a specific symbol.

    Args:
        symbol: Stock symbol
        days: Number of days to look back (default 30)

    Returns:
        List of disagreements for the symbol
    """
    try:
        since = datetime.now(UTC) - timedelta(days=days)

        query = """
            SELECT
                review_pair_id,
                symbol,
                MAX(created_at) as created_at,
                AVG(agreement_score) as agreement_score,
                MAX(disagreement_severity) as disagreement_severity,
                MAX(CASE WHEN provider = 'gemini' THEN review_text END) as gemini_review,
                MAX(CASE WHEN provider = 'claude' THEN review_text END) as claude_review
            FROM strategy_reviews
            WHERE created_at >= ?
                AND symbol = ?
                AND review_pair_id IS NOT NULL
            GROUP BY review_pair_id, symbol
            ORDER BY created_at DESC
        """

        df = storage.query(query, [since, symbol.upper()])

        items: list[DisagreementItem] = []
        for row in df.to_dicts():
            severity_val = row.get("disagreement_severity", "none")
            summary = _generate_summary(severity_val)
            items.append(
                DisagreementItem(
                    review_pair_id=row["review_pair_id"],
                    symbol=row["symbol"],
                    created_at=str(row["created_at"]),
                    agreement_score=float(row.get("agreement_score") or 0.0),
                    disagreement_severity=severity_val or "none",
                    gemini_review=row.get("gemini_review"),
                    claude_review=row.get("claude_review"),
                    consensus_summary=summary,
                )
            )

        return DisagreementsResponse(items=items, total=len(items))

    except Exception as e:
        logger.error(f"Failed to get symbol disagreements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


def _generate_summary(severity: str | None) -> str:
    """Generate consensus summary from severity."""
    if severity == "major":
        return "ALERT: Reviewers significantly disagree - manual review recommended"
    if severity == "minor":
        return "Reviewers have minor differences in emphasis but align on direction"
    return "Both reviewers agree on the assessment"
