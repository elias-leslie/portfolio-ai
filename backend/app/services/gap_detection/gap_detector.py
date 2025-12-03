"""Trading Intelligence Gap Detection Service (Facade).

This module provides the public interface for gap detection by coordinating
between the requirements loader, capability checker, and gap analyzer.

Key Functions:
- Load requirements from trading_requirements.yaml
- Query current capabilities from capability_scanner
- Compare REQUIRED vs AVAILABLE data per analysis type
- Calculate coverage % per analysis type (weighted by criticality)
- Identify gaps (missing/stale/low-coverage capabilities)
- Generate actionable recommendations to fill gaps
- Support per-ticker gap analysis (watchlist coverage)
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any

from ...logging_config import get_logger
from .analyzer import GapAnalyzer
from .capability_checker import CapabilityChecker
from .requirements import RequirementsLoader
from .types import GapAnalysisResult

if TYPE_CHECKING:
    from ...storage.connection import ConnectionManager

logger = get_logger(__name__)


class GapDetector:
    """Detects trading intelligence gaps by comparing requirements vs capabilities."""

    def __init__(
        self,
        connection_mgr: ConnectionManager,
        requirements_path: str | pathlib.Path | None = None,
    ) -> None:
        """Initialize gap detector.

        Args:
            connection_mgr: ConnectionManager instance for database access
            requirements_path: Optional path to trading_requirements.yaml
                (defaults to backend/app/config/trading_requirements.yaml)
        """
        self.conn_mgr = connection_mgr

        # Initialize components
        self.requirements_loader = RequirementsLoader(requirements_path)
        self.capability_checker = CapabilityChecker(connection_mgr)
        self.analyzer = GapAnalyzer(self.requirements_loader, self.capability_checker)

    def analyze_gaps(self) -> GapAnalysisResult:
        """Perform complete gap analysis across all analysis types.

        Returns:
            GapAnalysisResult with coverage % per analysis type and all gaps
        """
        return self.analyzer.analyze_gaps()

    def analyze_ticker_gaps(self, ticker: str) -> dict[str, Any]:
        """Analyze gaps for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with ticker-specific gap analysis including:
            - readiness_score: 0-100% overall readiness
            - coverage_by_analysis: Coverage % per analysis type
            - missing_capabilities: List of missing capabilities
            - confidence_level: LOW/MEDIUM/HIGH based on readiness
        """
        return self.analyzer.analyze_ticker_gaps(ticker)

    def analyze_watchlist_gaps(self) -> dict[str, Any]:
        """Analyze gaps affecting current watchlist.

        Returns:
            Dict with watchlist gap analysis including:
            - watchlist_tickers: List of ticker symbols
            - ticker_coverage: Per-ticker coverage analysis
            - aggregate_gaps: Gaps affecting multiple tickers
        """
        logger.info("analyzing_watchlist_gaps")

        # Get watchlist tickers from database
        try:
            with self.conn_mgr.connection() as conn:
                result = conn.execute(
                    "SELECT DISTINCT symbol FROM watchlist_items ORDER BY symbol"
                ).fetchall()
                tickers = [str(row[0]) for row in result if row[0] is not None]
        except Exception as e:
            logger.error("failed_to_fetch_watchlist_tickers", error=str(e))
            tickers = []

        if not tickers:
            logger.info("no_watchlist_tickers_found")
            return {
                "watchlist_tickers": [],
                "ticker_coverage": {},
                "aggregate_gaps": [],
            }

        logger.info("analyzing_watchlist_gaps", ticker_count=len(tickers))

        # Analyze each ticker
        ticker_coverage: dict[str, dict[str, Any]] = {}
        all_missing_capabilities: dict[str, list[str]] = {}  # capability → tickers missing it

        for ticker in tickers:
            try:
                analysis = self.analyzer.analyze_ticker_gaps(ticker)
                ticker_coverage[ticker] = analysis

                # Track which capabilities are missing per ticker
                for cap in analysis.get("missing_capabilities", []):
                    # cap format: "capability_name (analysis_type)"
                    cap_name = cap.split(" (")[0] if " (" in cap else cap
                    if cap_name not in all_missing_capabilities:
                        all_missing_capabilities[cap_name] = []
                    all_missing_capabilities[cap_name].append(ticker)
            except Exception as e:
                logger.warning("ticker_analysis_failed", ticker=ticker, error=str(e))
                ticker_coverage[ticker] = {
                    "ticker": ticker,
                    "readiness_score": 0.0,
                    "confidence_level": "LOW",
                    "coverage_by_analysis": {},
                    "missing_capabilities": [],
                    "data_availability": {},
                    "error": str(e),
                }

        # Aggregate gaps affecting multiple tickers
        aggregate_gaps: list[dict[str, Any]] = []
        for capability, affected_tickers in sorted(
            all_missing_capabilities.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        ):
            if len(affected_tickers) > 1:  # Only include if affects 2+ tickers
                aggregate_gaps.append(
                    {
                        "capability": capability,
                        "description": f"Missing {capability}",
                        "affected_tickers": len(affected_tickers),
                        "total_tickers": len(tickers),
                        "affected_pct": round(len(affected_tickers) / len(tickers) * 100, 1),
                        "tickers": affected_tickers,
                    }
                )

        logger.info(
            "watchlist_gaps_analyzed",
            ticker_count=len(tickers),
            aggregate_gap_count=len(aggregate_gaps),
        )

        return {
            "watchlist_tickers": tickers,
            "ticker_coverage": ticker_coverage,
            "aggregate_gaps": aggregate_gaps[:20],  # Top 20 aggregate gaps
        }

    def generate_task_list(self, gap_ids: list[str]) -> dict[str, Any]:
        """Generate task list to fill specific gaps.

        Args:
            gap_ids: List of gap IDs to fill (e.g., ["GAP-001", "GAP-012"])

        Returns:
            Dict with task list metadata
        """
        logger.info("generating_task_list", gap_ids=gap_ids)

        # Note: Task list generation not yet implemented
        # - For each gap_id, create detailed implementation task
        # - Reference gap_definition.md for full specifications
        # - Create markdown task file (tasks-XXXX-fill-gaps.md)

        return {
            "gap_ids": gap_ids,
            "message": "Task list generation not yet implemented",
        }
