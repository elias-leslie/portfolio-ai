"""Trading Intelligence Gap Detection Service.

This module compares trading analysis requirements (from trading_requirements.yaml)
against available system capabilities to identify gaps preventing profitable trading edge.

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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, TypedDict

import yaml

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


# ========================================================================
# Type Definitions
# ========================================================================


class CapabilityRequirement(TypedDict, total=False):
    """Single capability requirement from trading_requirements.yaml."""

    capability: str
    gap_id: str
    criticality: Literal["P0", "P1", "P2", "P3"]
    current_state: str
    desired_state: str
    why: str
    data_sources: list[dict[str, Any]]
    tables: list[str]
    freshness_requirement: str
    coverage_requirement: str
    notes: str | None


class GapInfo(TypedDict):
    """Identified gap with metadata."""

    gap_id: str
    capability: str
    analysis_type: str
    criticality: Literal["P0", "P1", "P2", "P3"]
    current_state: str
    desired_state: str
    impact: str  # "why" field from requirements
    data_sources: list[dict[str, Any]]
    effort: Literal["LOW", "MEDIUM", "HIGH"]
    blocks_strategies: list[str]
    recommendation: str
    severity: Literal["blocking", "limiting", "optional"]


class CoverageResult(TypedDict):
    """Coverage calculation result for an analysis type."""

    analysis_type: str
    description: str
    total_capabilities: int
    available_capabilities: int
    missing_capabilities: int
    coverage_pct: float
    maturity_level: int
    gaps: list[GapInfo]


class GapAnalysisResult(TypedDict):
    """Complete gap analysis result."""

    timestamp: str
    total_gaps: int
    p0_gaps: int
    p1_gaps: int
    p2_gaps: int
    p3_gaps: int
    analysis_types: dict[str, CoverageResult]
    top_10_priorities: list[GapInfo]
    mvp_roadmap: dict[str, Any]


# ========================================================================
# Gap Detector Service
# ========================================================================


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

        # Load trading requirements
        if requirements_path is None:
            base_path = pathlib.Path(__file__).parent.parent
            requirements_path = base_path / "config" / "trading_requirements.yaml"

        self.requirements_path = pathlib.Path(requirements_path)
        self.requirements = self._load_requirements()

        # Cache for capabilities (refreshed per analysis)
        self._capabilities_cache: dict[str, Any] | None = None

    def _load_requirements(self) -> dict[str, Any]:
        """Load trading requirements from YAML config.

        Returns:
            Dict with requirements structure

        Raises:
            FileNotFoundError: If requirements file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if not self.requirements_path.exists():
            msg = f"Trading requirements file not found: {self.requirements_path}"
            raise FileNotFoundError(msg)

        logger.info(
            "loading_trading_requirements",
            path=str(self.requirements_path),
        )

        with self.requirements_path.open(encoding="utf-8") as f:
            requirements = yaml.safe_load(f)

        logger.info(
            "trading_requirements_loaded",
            version=requirements.get("version"),
            total_gaps=requirements.get("metadata", {}).get("total_gaps"),
            analysis_types=len(requirements.get("analysis_types", {})),
        )

        return requirements  # type: ignore[no-any-return]

    def _get_current_capabilities(self) -> dict[str, Any]:
        """Query current system capabilities from capability registry.

        Returns:
            Dict mapping table names to capability metadata
        """
        if self._capabilities_cache is not None:
            return self._capabilities_cache

        logger.info("fetching_current_capabilities")

        capabilities = {}

        with self.conn_mgr.connection() as conn:
            # Fetch database capabilities
            tables_result = conn.execute(
                """
                SELECT
                    table_name,
                    category,
                    row_count,
                    total_columns,
                    columns,
                    completeness_pct,
                    date_range_start,
                    date_range_end,
                    days_since_update,
                    freshness_status
                FROM db_capabilities
                ORDER BY table_name
                """
            ).fetchall()

            for row in tables_result:
                # Unpack tuple result (order matches SELECT columns)
                (
                    table_name,
                    category,
                    row_count,
                    total_columns,
                    columns,
                    completeness_pct,
                    date_range_start,
                    date_range_end,
                    days_since_update,
                    freshness_status,
                ) = row

                capabilities[table_name] = {
                    "category": category,
                    "row_count": row_count,
                    "total_columns": total_columns,
                    "columns": columns,
                    "completeness_pct": completeness_pct,
                    "date_range_start": date_range_start,
                    "date_range_end": date_range_end,
                    "days_since_update": days_since_update,
                    "freshness_status": freshness_status,
                }

        self._capabilities_cache = capabilities

        logger.info(
            "capabilities_fetched",
            total_tables=len(capabilities),
        )

        return capabilities

    def _check_capability_available(
        self,
        requirement: CapabilityRequirement,
        capabilities: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if a required capability is available in the system.

        Args:
            requirement: Capability requirement from trading_requirements.yaml
            capabilities: Current system capabilities

        Returns:
            Tuple of (is_available: bool, reason: str)
        """
        required_tables = requirement.get("tables", [])

        if not required_tables:
            # No specific tables required (might be calculated metric)
            return (False, "no_tables_specified")

        # Check if all required tables exist and have data
        missing_tables = []
        empty_tables = []
        stale_tables = []

        for table_name in required_tables:
            if table_name not in capabilities:
                missing_tables.append(table_name)
                continue

            table_cap = capabilities[table_name]

            # Check if table has data
            if table_cap["row_count"] == 0:
                empty_tables.append(table_name)
                continue

            # Check freshness
            if table_cap["freshness_status"] == "stale":
                stale_tables.append(table_name)

        if missing_tables:
            return (
                False,
                f"missing_tables: {', '.join(missing_tables)}",
            )

        if empty_tables:
            return (
                False,
                f"empty_tables: {', '.join(empty_tables)}",
            )

        if stale_tables:
            return (
                False,
                f"stale_tables: {', '.join(stale_tables)}",
            )

        # All required tables exist, have data, and are fresh
        return (True, "available")

    def _calculate_coverage(
        self,
        analysis_type: str,
        requirements: list[CapabilityRequirement],
        capabilities: dict[str, Any],
    ) -> tuple[float, list[GapInfo]]:
        """Calculate coverage % for an analysis type.

        Coverage formula (weighted by criticality):
        - P0 (Critical) = 4 points
        - P1 (High) = 2 points
        - P2 (Medium) = 1 point
        - P3 (Low) = 0.5 points

        Coverage % = (Available Points / Total Points) * 100

        Args:
            analysis_type: Analysis type name (e.g., "technical_analysis")
            requirements: List of capability requirements
            capabilities: Current system capabilities

        Returns:
            Tuple of (coverage_pct: float, gaps: list[GapInfo])
        """
        # Criticality weights
        weights = {
            "P0": 4.0,
            "P1": 2.0,
            "P2": 1.0,
            "P3": 0.5,
        }

        total_points = 0.0
        available_points = 0.0
        gaps: list[GapInfo] = []

        for req in requirements:
            criticality = req["criticality"]
            weight = weights.get(criticality, 1.0)
            total_points += weight

            is_available, reason = self._check_capability_available(req, capabilities)

            if is_available:
                available_points += weight
            else:
                # Capability is missing → Create gap
                gap = self._create_gap_info(
                    req,
                    analysis_type,
                    reason,
                )
                gaps.append(gap)

        if total_points == 0:
            coverage_pct = 0.0
        else:
            coverage_pct = (available_points / total_points) * 100.0

        return (coverage_pct, gaps)

    def _create_gap_info(
        self,
        requirement: CapabilityRequirement,
        analysis_type: str,
        reason: str,
    ) -> GapInfo:
        """Create GapInfo from requirement.

        Args:
            requirement: Capability requirement
            analysis_type: Analysis type name
            reason: Why the gap exists

        Returns:
            GapInfo dict
        """
        # Determine severity based on criticality
        criticality = requirement["criticality"]
        severity: Literal["blocking", "limiting", "optional"]
        if criticality == "P0":
            severity = "blocking"
        elif criticality == "P1":
            severity = "limiting"
        else:
            severity = "optional"

        # Estimate effort based on data sources
        data_sources = requirement.get("data_sources", [])
        effort: Literal["LOW", "MEDIUM", "HIGH"]
        if any("internal" in str(ds) for ds in data_sources):
            effort = "LOW"  # Use existing data
        elif criticality in ("P0", "P1"):
            effort = "MEDIUM"  # New data source, high priority
        else:
            effort = "HIGH"  # Low priority, might be complex

        # Extract strategies blocked (from gap_definition.md if available)
        blocks_strategies: list[str] = []
        if criticality == "P0":
            blocks_strategies.append("All strategies (critical infrastructure)")
        elif "momentum" in requirement["capability"].lower():
            blocks_strategies.append("Momentum Trading")
        elif "earnings" in requirement["capability"].lower():
            blocks_strategies.append("Earnings Plays")
        elif "options" in requirement["capability"].lower():
            blocks_strategies.append("Options Flow Trading")
        # Add more heuristics as needed

        # Generate recommendation
        recommendation = self._generate_recommendation(requirement, reason)

        gap: GapInfo = {
            "gap_id": requirement["gap_id"],
            "capability": requirement["capability"],
            "analysis_type": analysis_type,
            "criticality": criticality,
            "current_state": requirement["current_state"],
            "desired_state": requirement["desired_state"],
            "impact": requirement["why"],
            "data_sources": data_sources,
            "effort": effort,
            "blocks_strategies": blocks_strategies,
            "recommendation": recommendation,
            "severity": severity,
        }

        return gap

    def _generate_recommendation(
        self,
        requirement: CapabilityRequirement,
        reason: str,
    ) -> str:
        """Generate actionable recommendation to fill gap.

        Args:
            requirement: Capability requirement
            reason: Why gap exists

        Returns:
            Recommendation string
        """
        data_sources = requirement.get("data_sources", [])
        tables = requirement.get("tables", [])

        if "missing_tables" in reason:
            # Tables don't exist → Need to create schema + ingestion
            if data_sources:
                source_names = [next(iter(ds.keys())) for ds in data_sources if ds]
                return (
                    f"Create tables {tables}, implement ingestion from "
                    f"{', '.join(source_names)}, schedule daily refresh"
                )
            return f"Create tables {tables}, implement data pipeline"

        if "empty_tables" in reason:
            # Tables exist but empty → Need to populate
            if data_sources:
                source_names = [next(iter(ds.keys())) for ds in data_sources if ds]
                return (
                    f"Populate {tables} by fetching from "
                    f"{', '.join(source_names)}, backfill historical data"
                )
            return f"Populate {tables} with initial data"

        if "stale_tables" in reason:
            # Tables exist but stale → Fix refresh schedule
            return (
                f"Fix scheduled refresh for {tables}, verify Celery task is running, "
                "check data source availability"
            )

        # Generic recommendation
        return "Implement data pipeline to fill this gap (see gap_definition.md for details)"

    def _get_maturity_level(self, coverage_pct: float) -> int:
        """Get maturity level (0-3) based on coverage %.

        Args:
            coverage_pct: Coverage percentage (0-100)

        Returns:
            Maturity level (0=Missing, 1=Minimal, 2=Adequate, 3=Complete)
        """
        if coverage_pct == 0:
            return 0  # Missing
        if coverage_pct < 40:
            return 1  # Minimal
        if coverage_pct < 80:
            return 2  # Adequate
        return 3  # Complete

    def analyze_gaps(self) -> GapAnalysisResult:
        """Perform complete gap analysis across all analysis types.

        Returns:
            GapAnalysisResult with coverage % per analysis type and all gaps
        """
        logger.info("starting_gap_analysis")

        capabilities = self._get_current_capabilities()
        analysis_types_config = self.requirements.get("analysis_types", {})

        all_gaps: list[GapInfo] = []
        coverage_results: dict[str, CoverageResult] = {}

        for analysis_type, config in analysis_types_config.items():
            description = config.get("description", "")

            # Collect all requirements (required + recommended + optional)
            requirements: list[CapabilityRequirement] = []
            requirements.extend(config.get("required") or [])
            requirements.extend(config.get("recommended") or [])
            requirements.extend(config.get("optional") or [])

            # Calculate coverage
            coverage_pct, gaps = self._calculate_coverage(
                analysis_type,
                requirements,
                capabilities,
            )

            maturity_level = self._get_maturity_level(coverage_pct)

            coverage_result: CoverageResult = {
                "analysis_type": analysis_type,
                "description": description,
                "total_capabilities": len(requirements),
                "available_capabilities": len(requirements) - len(gaps),
                "missing_capabilities": len(gaps),
                "coverage_pct": round(coverage_pct, 1),
                "maturity_level": maturity_level,
                "gaps": gaps,
            }

            coverage_results[analysis_type] = coverage_result
            all_gaps.extend(gaps)

        # Count gaps by criticality
        p0_gaps = [g for g in all_gaps if g["criticality"] == "P0"]
        p1_gaps = [g for g in all_gaps if g["criticality"] == "P1"]
        p2_gaps = [g for g in all_gaps if g["criticality"] == "P2"]
        p3_gaps = [g for g in all_gaps if g["criticality"] == "P3"]

        # Get TOP 10 priorities from requirements
        edge_capabilities = self.requirements.get("edge_capabilities", {})
        top_10_priorities = self._get_top_10_priorities(all_gaps, edge_capabilities)

        # Get MVP roadmap
        mvp_roadmap = self.requirements.get("mvp_roadmap", {})

        result: GapAnalysisResult = {
            "timestamp": datetime.now(UTC).isoformat(),
            "total_gaps": len(all_gaps),
            "p0_gaps": len(p0_gaps),
            "p1_gaps": len(p1_gaps),
            "p2_gaps": len(p2_gaps),
            "p3_gaps": len(p3_gaps),
            "analysis_types": coverage_results,
            "top_10_priorities": top_10_priorities,
            "mvp_roadmap": mvp_roadmap,
        }

        logger.info(
            "gap_analysis_complete",
            total_gaps=len(all_gaps),
            p0=len(p0_gaps),
            p1=len(p1_gaps),
            avg_coverage=round(
                sum(r["coverage_pct"] for r in coverage_results.values()) / len(coverage_results),
                1,
            )
            if coverage_results
            else 0,
        )

        return result

    def _get_top_10_priorities(
        self,
        all_gaps: list[GapInfo],
        edge_capabilities: dict[str, Any],
    ) -> list[GapInfo]:
        """Get TOP 10 priority gaps based on edge_capabilities ranking.

        Args:
            all_gaps: All identified gaps
            edge_capabilities: edge_capabilities section from requirements YAML

        Returns:
            List of top 10 priority gaps (sorted by rank)
        """
        # Create map of gap_id → rank
        gap_rank_map: dict[str, int] = {}
        for rank_key, cap in edge_capabilities.items():
            if rank_key.startswith("rank_"):
                rank = int(rank_key.split("_")[1])
                gap_id = cap.get("gap_id")
                if gap_id:
                    gap_rank_map[gap_id] = rank

        # Filter gaps that are in TOP 10 and sort by rank
        top_10 = [g for g in all_gaps if g["gap_id"] in gap_rank_map]
        top_10.sort(key=lambda g: gap_rank_map[g["gap_id"]])

        return top_10[:10]

    def _check_ticker_data_availability(self, ticker: str) -> dict[str, Any]:
        """Check what data exists for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict mapping table names to availability status
        """
        availability: dict[str, Any] = {}

        # Check key tables for ticker-specific data
        tables_to_check = [
            ("day_bars", "SELECT COUNT(*) FROM day_bars WHERE ticker = %s", [ticker]),
            (
                "technical_indicators",
                "SELECT COUNT(*) FROM technical_indicators WHERE ticker = %s",
                [ticker],
            ),
            (
                "fundamentals",
                "SELECT COUNT(*) FROM fundamentals WHERE ticker = %s",
                [ticker],
            ),
            (
                "news_cache",
                "SELECT COUNT(*) FROM news_cache WHERE ticker = %s",
                [ticker],
            ),
            (
                "analyst_ratings",
                "SELECT COUNT(*) FROM analyst_ratings WHERE ticker = %s",
                [ticker],
            ),
        ]

        # Check each table individually to avoid transaction rollback issues
        for table_name, query, params in tables_to_check:
            try:
                with self.conn_mgr.connection() as conn:
                    result = conn.execute(query, params).fetchone()
                    row_count = result[0] if result else 0
                    availability[table_name] = {
                        "exists": True,
                        "has_data": row_count > 0,
                        "row_count": row_count,
                    }
            except Exception as e:
                logger.warning(
                    f"Failed to check {table_name} for {ticker}: {e}",
                    table=table_name,
                    ticker=ticker,
                )
                availability[table_name] = {
                    "exists": False,
                    "has_data": False,
                    "row_count": 0,
                }

        return availability

    def _ticker_has_capability(
        self,
        ticker: str,
        requirement: CapabilityRequirement,
        ticker_data_availability: dict[str, Any],
    ) -> bool:
        """Check if a ticker has data for a specific capability.

        Args:
            ticker: Stock ticker symbol
            requirement: Capability requirement from trading_requirements.yaml
            ticker_data_availability: Pre-fetched data availability for ticker

        Returns:
            True if ticker has data for this capability
        """
        required_tables = requirement.get("tables", [])

        if not required_tables:
            # No specific tables required - assume available
            return True

        # Check if ticker has data in ALL required tables
        for table_name in required_tables:
            table_avail = ticker_data_availability.get(table_name, {})
            if not table_avail.get("has_data", False):
                return False

        return True

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
        logger.info("analyzing_ticker_gaps", ticker=ticker)

        # Check what data exists for this ticker
        ticker_data_availability = self._check_ticker_data_availability(ticker)

        # Calculate coverage per analysis type
        coverage_by_analysis: dict[str, float] = {}
        all_missing: list[str] = []

        for analysis_type, type_reqs in self.requirements["analysis_types"].items():
            required_caps = type_reqs.get("required") or []
            recommended_caps = type_reqs.get("recommended") or []

            # Count available capabilities
            available_required = sum(
                1
                for req in required_caps
                if self._ticker_has_capability(ticker, req, ticker_data_availability)
            )
            available_recommended = sum(
                1
                for req in recommended_caps
                if self._ticker_has_capability(ticker, req, ticker_data_availability)
            )

            # Calculate coverage (required weighted 2x, recommended 1x)
            total_weight = len(required_caps) * 2 + len(recommended_caps)
            if total_weight > 0:
                coverage_pct = (
                    (available_required * 2 + available_recommended) / total_weight
                ) * 100
            else:
                coverage_pct = 0.0

            coverage_by_analysis[analysis_type] = coverage_pct

            # Track missing capabilities
            for req in required_caps:
                if not self._ticker_has_capability(ticker, req, ticker_data_availability):
                    all_missing.append(f"{req['capability']} ({analysis_type})")

        # Calculate overall readiness score (average of all analysis types)
        if coverage_by_analysis:
            readiness_score = sum(coverage_by_analysis.values()) / len(coverage_by_analysis)
        else:
            readiness_score = 0.0

        # Determine confidence level
        if readiness_score >= 75:
            confidence_level = "HIGH"
        elif readiness_score >= 50:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        return {
            "ticker": ticker,
            "readiness_score": round(readiness_score, 1),
            "confidence_level": confidence_level,
            "coverage_by_analysis": {k: round(v, 1) for k, v in coverage_by_analysis.items()},
            "missing_capabilities": all_missing[:10],  # Top 10 most critical
            "data_availability": ticker_data_availability,
        }

    def analyze_watchlist_gaps(self) -> dict[str, Any]:
        """Analyze gaps affecting current watchlist.

        Returns:
            Dict with watchlist gap analysis
        """
        logger.info("analyzing_watchlist_gaps")

        # TODO: Implement watchlist-specific gap analysis
        # - Get current watchlist tickers
        # - Check coverage per ticker
        # - Aggregate: "8/12 watchlist tickers missing earnings data"

        return {
            "message": "Watchlist gap analysis not yet implemented",
        }

    def generate_task_list(self, gap_ids: list[str]) -> dict[str, Any]:
        """Generate task list to fill specific gaps.

        Args:
            gap_ids: List of gap IDs to fill (e.g., ["GAP-001", "GAP-012"])

        Returns:
            Dict with task list metadata
        """
        logger.info("generating_task_list", gap_ids=gap_ids)

        # TODO: Implement task list generation
        # - For each gap_id, create detailed implementation task
        # - Reference gap_definition.md for full specifications
        # - Create markdown task file (tasks-XXXX-fill-gaps.md)

        return {
            "gap_ids": gap_ids,
            "message": "Task list generation not yet implemented",
        }
