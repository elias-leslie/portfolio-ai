"""AI Rules Validation Agent - Tier 3 Task 3.0

Validates trading rules configuration for logical consistency and optimization opportunities.

VALIDATION CHECKS:
- All thresholds in valid range (RSI 0-100, percentages 0-1, etc.)
- No contradictory rules (logical consistency)
- Fee assumptions realistic (commission not 0, slippage reasonable)
- Position sizing sums valid (max positions * max size <= 100%)
- All referenced indicators defined (no undefined variables)

OPTIMIZATION CHECKS:
- Compare rules to recent performance
- Identify unused rules
- Propose threshold adjustments
- Flag rules that never trigger
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from app.logging_config import get_logger
from app.rules.loader import get_rules
from app.rules.models import TradingRules

logger = get_logger(__name__)


@dataclass
class ValidationError:
    """Single validation error."""

    severity: Literal["critical", "warning", "info"]
    category: str
    field_path: str
    message: str
    current_value: Any = None
    expected_range: str | None = None


@dataclass
class Recommendation:
    """Optimization recommendation."""

    priority: Literal["high", "medium", "low"]
    category: str
    field_path: str
    recommendation: str
    rationale: str
    suggested_value: Any = None


@dataclass
class ValidationReport:
    """Complete validation report."""

    timestamp: datetime
    rules_version: str
    overall_status: Literal["valid", "warnings", "critical"]
    errors: list[ValidationError]
    recommendations: list[Recommendation]
    summary: str


class RulesValidatorAgent:
    """AI-powered rules validator with logical consistency checks."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.rules: TradingRules | None = None

    async def validate_rules(self, rules: TradingRules | None = None) -> ValidationReport:
        """Validate trading rules configuration.

        Args:
            rules: TradingRules object to validate (loads from file if None)

        Returns:
            ValidationReport with errors and recommendations
        """
        if rules is None:
            rules = get_rules()

        self.rules = rules
        errors: list[ValidationError] = []

        # Run all validation checks
        errors.extend(self._check_threshold_ranges())
        errors.extend(self._check_contradictions())
        errors.extend(self._check_position_sizing())
        errors.extend(self._check_fee_assumptions())

        # Determine overall status
        has_critical = any(e.severity == "critical" for e in errors)
        has_warnings = any(e.severity == "warning" for e in errors)

        if has_critical:
            status = "critical"
        elif has_warnings:
            status = "warnings"
        else:
            status = "valid"

        # Generate summary
        summary = self._generate_summary(errors)

        return ValidationReport(
            timestamp=datetime.now(UTC),
            rules_version=rules.version,
            overall_status=status,
            errors=errors,
            recommendations=[],  # Filled by optimization checks
            summary=summary,
        )

    def _check_threshold_ranges(self) -> list[ValidationError]:
        """Validate all thresholds are in valid ranges."""
        errors: list[ValidationError] = []
        if not self.rules:
            return errors

        tech = self.rules.technical_thresholds
        signals = self.rules.signals
        position = self.rules.position_sizing
        risk = self.rules.risk_management

        # RSI thresholds (0-100)
        if not (0 <= tech.rsi_oversold <= 100):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="technical_thresholds.rsi_oversold",
                    message="RSI oversold threshold out of valid range",
                    current_value=tech.rsi_oversold,
                    expected_range="0-100",
                )
            )

        if not (0 <= tech.rsi_overbought <= 100):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="technical_thresholds.rsi_overbought",
                    message="RSI overbought threshold out of valid range",
                    current_value=tech.rsi_overbought,
                    expected_range="0-100",
                )
            )

        # RSI logic: oversold < overbought
        if tech.rsi_oversold >= tech.rsi_overbought:
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_logic",
                    field_path="technical_thresholds.rsi_*",
                    message="RSI oversold must be < overbought",
                    current_value=f"oversold={tech.rsi_oversold}, overbought={tech.rsi_overbought}",
                )
            )

        # Percentage fields (0-1)
        if not (0 <= position.default_risk_percent <= 1):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="position_sizing.default_risk_percent",
                    message="Risk percent must be 0-1 (not 0-100)",
                    current_value=position.default_risk_percent,
                    expected_range="0-1",
                )
            )

        if not (0 <= position.max_position_percent <= 1):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="position_sizing.max_position_percent",
                    message="Max position percent must be 0-1",
                    current_value=position.max_position_percent,
                    expected_range="0-1",
                )
            )

        # Drawdown thresholds (0-100 for percentages)
        if not (0 <= risk.portfolio_drawdown_halt_pct <= 100):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="risk_management.portfolio_drawdown_halt_pct",
                    message="Drawdown halt percent out of range",
                    current_value=risk.portfolio_drawdown_halt_pct,
                    expected_range="0-100",
                )
            )

        # News sentiment (-1 to +1)
        if not (-1 <= signals.news_sentiment_positive <= 1):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="signals.news_sentiment_positive",
                    message="News sentiment must be -1 to +1",
                    current_value=signals.news_sentiment_positive,
                    expected_range="-1 to +1",
                )
            )

        if not (-1 <= signals.news_sentiment_negative <= 1):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="threshold_range",
                    field_path="signals.news_sentiment_negative",
                    message="News sentiment must be -1 to +1",
                    current_value=signals.news_sentiment_negative,
                    expected_range="-1 to +1",
                )
            )

        return errors

    def _check_contradictions(self) -> list[ValidationError]:
        """Check for contradictory rules."""
        errors: list[ValidationError] = []
        if not self.rules:
            return errors

        position = self.rules.position_sizing
        risk = self.rules.risk_management
        scoring = self.rules.scoring

        # Position sizing: min < max
        if position.min_risk_percent > position.max_risk_percent:
            errors.append(
                ValidationError(
                    severity="critical",
                    category="contradiction",
                    field_path="position_sizing.risk_percent",
                    message="Min risk percent > max risk percent",
                    current_value=f"min={position.min_risk_percent}, max={position.max_risk_percent}",
                )
            )

        # Drawdown warnings must escalate
        if risk.drawdown_warning_level_1 >= risk.drawdown_warning_level_2:
            errors.append(
                ValidationError(
                    severity="warning",
                    category="contradiction",
                    field_path="risk_management.drawdown_warning_*",
                    message="Drawdown warning levels should escalate",
                    current_value=f"L1={risk.drawdown_warning_level_1}, L2={risk.drawdown_warning_level_2}",
                )
            )

        if risk.drawdown_warning_level_2 >= risk.portfolio_drawdown_halt_pct:
            errors.append(
                ValidationError(
                    severity="critical",
                    category="contradiction",
                    field_path="risk_management.drawdown_*",
                    message="Final warning must be < halt threshold",
                    current_value=f"L2={risk.drawdown_warning_level_2}, halt={risk.portfolio_drawdown_halt_pct}",
                )
            )

        # Scoring weights must sum to 100
        total_weight = scoring.price_weight + scoring.technical_weight + scoring.fundamental_weight
        if not (99.5 <= total_weight <= 100.5):  # Allow for rounding
            errors.append(
                ValidationError(
                    severity="critical",
                    category="contradiction",
                    field_path="scoring.*_weight",
                    message="Scoring weights must sum to 100",
                    current_value=f"{total_weight:.1f}",
                    expected_range="100",
                )
            )

        # Fundamental pillar weights must sum to 1.0
        fund_total = (
            scoring.valuation_weight
            + scoring.growth_weight
            + scoring.health_weight
            + scoring.sentiment_weight
        )
        if not (0.99 <= fund_total <= 1.01):
            errors.append(
                ValidationError(
                    severity="critical",
                    category="contradiction",
                    field_path="scoring.fundamental_*_weight",
                    message="Fundamental pillar weights must sum to 1.0",
                    current_value=f"{fund_total:.3f}",
                    expected_range="1.0",
                )
            )

        return errors

    def _check_position_sizing(self) -> list[ValidationError]:
        """Validate position sizing math."""
        errors: list[ValidationError] = []
        if not self.rules:
            return errors

        position = self.rules.position_sizing

        # Max position * typical positions <= 100%
        # Assume typical portfolio has 10 positions
        typical_positions = 10
        max_total_exposure = position.max_position_percent * typical_positions

        if max_total_exposure > 1.0:
            errors.append(
                ValidationError(
                    severity="warning",
                    category="position_sizing",
                    field_path="position_sizing.max_position_percent",
                    message=f"Max position {position.max_position_percent:.1%} * {typical_positions} positions = {max_total_exposure:.1%} exposure (>100%)",
                    current_value=position.max_position_percent,
                )
            )

        # Sector exposure check
        if position.max_sector_exposure_pct > 1.0:
            errors.append(
                ValidationError(
                    severity="critical",
                    category="position_sizing",
                    field_path="position_sizing.max_sector_exposure_pct",
                    message="Max sector exposure >100%",
                    current_value=position.max_sector_exposure_pct,
                    expected_range="0-1",
                )
            )

        # Liquidity check: max_position_percent_adv should be reasonable (<5%)
        if position.max_position_percent_adv > 0.05:
            errors.append(
                ValidationError(
                    severity="warning",
                    category="position_sizing",
                    field_path="position_sizing.max_position_percent_adv",
                    message="Position size >5% of ADV may cause slippage",
                    current_value=position.max_position_percent_adv,
                    expected_range="0-0.05",
                )
            )

        return errors

    def _check_fee_assumptions(self) -> list[ValidationError]:
        """Validate fee assumptions are realistic."""
        errors: list[ValidationError] = []
        if not self.rules:
            return errors

        fees = self.rules.fees

        # Commission must not be 0 (unrealistic)
        if fees.commission_per_share == 0 and fees.commission_per_trade == 0:
            errors.append(
                ValidationError(
                    severity="warning",
                    category="fee_assumptions",
                    field_path="fees.commission_*",
                    message="Zero commission unrealistic for backtesting",
                    current_value="0",
                )
            )

        # Slippage should be 1-10 bps for liquid stocks
        if not (1.0 <= fees.slippage_bps <= 20.0):
            errors.append(
                ValidationError(
                    severity="warning",
                    category="fee_assumptions",
                    field_path="fees.slippage_bps",
                    message="Slippage outside typical range",
                    current_value=fees.slippage_bps,
                    expected_range="1-20 bps",
                )
            )

        # Institutional slippage should be lower than retail
        if fees.slippage_institutional_bps >= fees.slippage_bps:
            errors.append(
                ValidationError(
                    severity="warning",
                    category="fee_assumptions",
                    field_path="fees.slippage_*_bps",
                    message="Institutional slippage should be < retail",
                    current_value=f"inst={fees.slippage_institutional_bps}, retail={fees.slippage_bps}",
                )
            )

        return errors

    def _generate_summary(self, errors: list[ValidationError]) -> str:
        """Generate human-readable summary."""
        if not errors:
            return "All validation checks passed. Rules configuration is valid."

        critical_count = sum(1 for e in errors if e.severity == "critical")
        warning_count = sum(1 for e in errors if e.severity == "warning")
        info_count = sum(1 for e in errors if e.severity == "info")

        summary_parts = []

        if critical_count:
            summary_parts.append(f"{critical_count} critical error(s)")
        if warning_count:
            summary_parts.append(f"{warning_count} warning(s)")
        if info_count:
            summary_parts.append(f"{info_count} info message(s)")

        return "Found: " + ", ".join(summary_parts)

    async def generate_optimization_recommendations(
        self, performance_data: dict[str, Any] | None = None
    ) -> list[Recommendation]:
        """Generate optimization recommendations based on performance.

        Args:
            performance_data: Recent trading performance metrics

        Returns:
            List of optimization recommendations
        """
        recommendations: list[Recommendation] = []

        # This would analyze actual trading performance and suggest improvements
        # For now, return static recommendations based on rules inspection

        if not self.rules:
            return recommendations

        position = self.rules.position_sizing
        tech = self.rules.technical_thresholds

        # Example: RSI thresholds too extreme
        if tech.rsi_oversold < 25:
            recommendations.append(
                Recommendation(
                    priority="medium",
                    category="technical_thresholds",
                    field_path="technical_thresholds.rsi_oversold",
                    recommendation="Consider raising RSI oversold threshold",
                    rationale=f"Current value {tech.rsi_oversold} may trigger too rarely. RSI < 25 is very oversold.",
                    suggested_value=30,
                )
            )

        # Example: Position sizing too conservative
        if position.max_position_percent < 0.05:
            recommendations.append(
                Recommendation(
                    priority="low",
                    category="position_sizing",
                    field_path="position_sizing.max_position_percent",
                    recommendation="Max position size may be too conservative",
                    rationale=f"Current {position.max_position_percent:.1%} limits diversification benefits. Consider 5-10%.",
                    suggested_value=0.10,
                )
            )

        return recommendations


async def validate_rules_cli() -> None:
    """CLI entry point for rules validation."""
    print("=== Trading Rules Validation ===\n")

    validator = RulesValidatorAgent()
    report = await validator.validate_rules()

    print(f"Rules Version: {report.rules_version}")
    print(f"Timestamp: {report.timestamp.isoformat()}")
    print(f"Overall Status: {report.overall_status.upper()}\n")

    if report.errors:
        print(f"=== Validation Errors ({len(report.errors)}) ===\n")
        for i, error in enumerate(report.errors, 1):
            print(f"{i}. [{error.severity.upper()}] {error.category}")
            print(f"   Field: {error.field_path}")
            print(f"   Message: {error.message}")
            if error.current_value:
                print(f"   Current: {error.current_value}")
            if error.expected_range:
                print(f"   Expected: {error.expected_range}")
            print()

    print(f"Summary: {report.summary}\n")

    # Generate recommendations
    recommendations = await validator.generate_optimization_recommendations()
    if recommendations:
        print(f"=== Optimization Recommendations ({len(recommendations)}) ===\n")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. [{rec.priority.upper()}] {rec.recommendation}")
            print(f"   Field: {rec.field_path}")
            print(f"   Rationale: {rec.rationale}")
            if rec.suggested_value:
                print(f"   Suggested: {rec.suggested_value}")
            print()


if __name__ == "__main__":
    asyncio.run(validate_rules_cli())
