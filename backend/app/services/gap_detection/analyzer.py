"""Gap analysis engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from ...logging_config import get_logger
from .types import CapabilityRequirement, CoverageResult, GapAnalysisResult, GapInfo

if TYPE_CHECKING:
    from .capability_checker import CapabilityChecker
    from .requirements import RequirementsLoader

logger = get_logger(__name__)


class GapAnalyzer:
    """Analyzes gaps between requirements and capabilities."""

    # Criticality weights for coverage calculation
    WEIGHTS: ClassVar[dict[str, float]] = {
        "P0": 4.0,
        "P1": 2.0,
        "P2": 1.0,
        "P3": 0.5,
    }

    def __init__(
        self,
        requirements_loader: RequirementsLoader,
        capability_checker: CapabilityChecker,
    ) -> None:
        """Initialize gap analyzer.

        Args:
            requirements_loader: Requirements loader instance
            capability_checker: Capability checker instance
        """
        self.requirements_loader = requirements_loader
        self.capability_checker = capability_checker

    def analyze_gaps(self) -> GapAnalysisResult:
        """Perform complete gap analysis across all analysis types.

        Returns:
            GapAnalysisResult with coverage % per analysis type and all gaps
        """
        logger.info("starting_gap_analysis")

        capabilities = self.capability_checker.get_current_capabilities()
        analysis_types_config = self.requirements_loader.get_analysis_types()

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
        edge_capabilities = self.requirements_loader.get_edge_capabilities()
        top_10_priorities = self._get_top_10_priorities(all_gaps, edge_capabilities)

        # Get MVP roadmap
        mvp_roadmap = self.requirements_loader.get_mvp_roadmap()

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
        ticker_data_availability = self.capability_checker.check_ticker_data_availability(ticker)

        # Calculate coverage per analysis type
        coverage_by_analysis: dict[str, float] = {}
        all_missing: list[str] = []
        analysis_types = self.requirements_loader.get_analysis_types()

        for analysis_type, type_reqs in analysis_types.items():
            required_caps = type_reqs.get("required") or []
            recommended_caps = type_reqs.get("recommended") or []

            # Count available capabilities
            available_required = sum(
                1
                for req in required_caps
                if self.capability_checker.ticker_has_capability(
                    ticker, req, ticker_data_availability
                )
            )
            available_recommended = sum(
                1
                for req in recommended_caps
                if self.capability_checker.ticker_has_capability(
                    ticker, req, ticker_data_availability
                )
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
                if not self.capability_checker.ticker_has_capability(
                    ticker, req, ticker_data_availability
                ):
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
        total_points = 0.0
        available_points = 0.0
        gaps: list[GapInfo] = []

        for req in requirements:
            criticality = req["criticality"]
            weight = self.WEIGHTS.get(criticality, 1.0)
            total_points += weight

            is_available, reason = self.capability_checker.check_capability_available(
                req, capabilities
            )

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
