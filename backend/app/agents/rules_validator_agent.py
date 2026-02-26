"""AI Rules Validation Agent - Tier 3 Task 3.0

Validates trading rules configuration for logical consistency and optimization opportunities.
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

Severity = Literal["critical", "warning", "info"]
Status = Literal["valid", "warnings", "critical"]


@dataclass
class ValidationError:
    """Single validation error."""
    severity: Severity
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
    overall_status: Status
    errors: list[ValidationError]
    recommendations: list[Recommendation]
    summary: str


def _err(sev: Severity, cat: str, path: str, msg: str,
         val: Any = None, rng: str | None = None) -> ValidationError:
    """Construct a ValidationError."""
    return ValidationError(sev, cat, path, msg, val, rng)


def _check_rsi(rules: TradingRules) -> list[ValidationError]:
    """Validate RSI thresholds."""
    tech = rules.technical_thresholds
    errors: list[ValidationError] = []
    if not (0 <= tech.rsi_oversold <= 100):
        errors.append(_err("critical", "threshold_range", "technical_thresholds.rsi_oversold",
                           "RSI oversold threshold out of valid range", tech.rsi_oversold, "0-100"))
    if not (0 <= tech.rsi_overbought <= 100):
        errors.append(_err("critical", "threshold_range", "technical_thresholds.rsi_overbought",
                           "RSI overbought threshold out of valid range", tech.rsi_overbought, "0-100"))
    if tech.rsi_oversold >= tech.rsi_overbought:
        errors.append(_err("critical", "threshold_logic", "technical_thresholds.rsi_*",
                           "RSI oversold must be < overbought",
                           f"oversold={tech.rsi_oversold}, overbought={tech.rsi_overbought}"))
    return errors


def _check_percents(rules: TradingRules) -> list[ValidationError]:
    """Validate percentage fields are in 0-1 range."""
    pos = rules.position_sizing
    errors: list[ValidationError] = []
    if not (0 <= pos.default_risk_percent <= 1):
        errors.append(_err("critical", "threshold_range", "position_sizing.default_risk_percent",
                           "Risk percent must be 0-1 (not 0-100)", pos.default_risk_percent, "0-1"))
    if not (0 <= pos.max_position_percent <= 1):
        errors.append(_err("critical", "threshold_range", "position_sizing.max_position_percent",
                           "Max position percent must be 0-1", pos.max_position_percent, "0-1"))
    return errors


def _check_drawdown_range(rules: TradingRules) -> list[ValidationError]:
    """Validate drawdown halt percent is in 0-100 range."""
    risk = rules.risk_management
    if not (0 <= risk.portfolio_drawdown_halt_pct <= 100):
        return [_err("critical", "threshold_range", "risk_management.portfolio_drawdown_halt_pct",
                     "Drawdown halt percent out of range", risk.portfolio_drawdown_halt_pct, "0-100")]
    return []


def _check_sentiment(rules: TradingRules) -> list[ValidationError]:
    """Validate news sentiment thresholds are in -1 to +1 range."""
    sig = rules.signals
    errors: list[ValidationError] = []
    for field, val in [("news_sentiment_positive", sig.news_sentiment_positive),
                       ("news_sentiment_negative", sig.news_sentiment_negative)]:
        if not (-1 <= val <= 1):
            errors.append(_err("critical", "threshold_range", f"signals.{field}",
                               "News sentiment must be -1 to +1", val, "-1 to +1"))
    return errors


def _check_contradictions(rules: TradingRules) -> list[ValidationError]:
    """Check for contradictory rules."""
    pos = rules.position_sizing
    risk = rules.risk_management
    scoring = rules.scoring
    errors: list[ValidationError] = []
    if pos.min_risk_percent > pos.max_risk_percent:
        errors.append(_err("critical", "contradiction", "position_sizing.risk_percent",
                           "Min risk percent > max risk percent",
                           f"min={pos.min_risk_percent}, max={pos.max_risk_percent}"))
    if risk.drawdown_warning_level_1 >= risk.drawdown_warning_level_2:
        errors.append(_err("warning", "contradiction", "risk_management.drawdown_warning_*",
                           "Drawdown warning levels should escalate",
                           f"L1={risk.drawdown_warning_level_1}, L2={risk.drawdown_warning_level_2}"))
    if risk.drawdown_warning_level_2 >= risk.portfolio_drawdown_halt_pct:
        errors.append(_err("critical", "contradiction", "risk_management.drawdown_*",
                           "Final warning must be < halt threshold",
                           f"L2={risk.drawdown_warning_level_2}, halt={risk.portfolio_drawdown_halt_pct}"))
    total_weight = scoring.price_weight + scoring.technical_weight + scoring.fundamental_weight
    if not (99.5 <= total_weight <= 100.5):
        errors.append(_err("critical", "contradiction", "scoring.*_weight",
                           "Scoring weights must sum to 100", f"{total_weight:.1f}", "100"))
    fund_total = (scoring.valuation_weight + scoring.growth_weight
                  + scoring.health_weight + scoring.sentiment_weight)
    if not (0.99 <= fund_total <= 1.01):
        errors.append(_err("critical", "contradiction", "scoring.fundamental_*_weight",
                           "Fundamental pillar weights must sum to 1.0", f"{fund_total:.3f}", "1.0"))
    return errors


def _check_position_sizing(rules: TradingRules) -> list[ValidationError]:
    """Validate position sizing math."""
    pos = rules.position_sizing
    typical_positions = 10
    max_total = pos.max_position_percent * typical_positions
    errors: list[ValidationError] = []
    if max_total > 1.0:
        errors.append(_err("warning", "position_sizing", "position_sizing.max_position_percent",
                           f"Max position {pos.max_position_percent:.1%} * {typical_positions} positions = {max_total:.1%} exposure (>100%)",
                           pos.max_position_percent))
    if pos.max_sector_exposure_pct > 1.0:
        errors.append(_err("critical", "position_sizing", "position_sizing.max_sector_exposure_pct",
                           "Max sector exposure >100%", pos.max_sector_exposure_pct, "0-1"))
    if pos.max_position_percent_adv > 0.05:
        errors.append(_err("warning", "position_sizing", "position_sizing.max_position_percent_adv",
                           "Position size >5% of ADV may cause slippage",
                           pos.max_position_percent_adv, "0-0.05"))
    return errors


def _check_fees(rules: TradingRules) -> list[ValidationError]:
    """Validate fee assumptions are realistic."""
    fees = rules.fees
    errors: list[ValidationError] = []
    if fees.commission_per_share == 0 and fees.commission_per_trade == 0:
        errors.append(_err("warning", "fee_assumptions", "fees.commission_*",
                           "Zero commission unrealistic for backtesting", "0"))
    if not (1.0 <= fees.slippage_bps <= 20.0):
        errors.append(_err("warning", "fee_assumptions", "fees.slippage_bps",
                           "Slippage outside typical range", fees.slippage_bps, "1-20 bps"))
    if fees.slippage_institutional_bps >= fees.slippage_bps:
        errors.append(_err("warning", "fee_assumptions", "fees.slippage_*_bps",
                           "Institutional slippage should be < retail",
                           f"inst={fees.slippage_institutional_bps}, retail={fees.slippage_bps}"))
    return errors


def _determine_status(errors: list[ValidationError]) -> Status:
    """Determine overall validation status from errors."""
    if any(e.severity == "critical" for e in errors):
        return "critical"
    if any(e.severity == "warning" for e in errors):
        return "warnings"
    return "valid"


def _generate_summary(errors: list[ValidationError]) -> str:
    """Generate human-readable summary."""
    if not errors:
        return "All validation checks passed. Rules configuration is valid."
    parts = []
    for sev, label in [("critical", "critical error(s)"), ("warning", "warning(s)"), ("info", "info message(s)")]:
        count = sum(1 for e in errors if e.severity == sev)
        if count:
            parts.append(f"{count} {label}")
    return "Found: " + ", ".join(parts)


class RulesValidatorAgent:
    """AI-powered rules validator with logical consistency checks."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.rules: TradingRules | None = None

    async def validate_rules(self, rules: TradingRules | None = None) -> ValidationReport:
        """Validate trading rules configuration; loads from file if rules is None."""
        if rules is None:
            rules = get_rules()
        self.rules = rules
        errors: list[ValidationError] = []
        for check in (_check_rsi, _check_percents, _check_drawdown_range,
                      _check_sentiment, _check_contradictions,
                      _check_position_sizing, _check_fees):
            errors.extend(check(rules))
        return ValidationReport(
            timestamp=datetime.now(UTC),
            rules_version=rules.version,
            overall_status=_determine_status(errors),
            errors=errors,
            recommendations=[],
            summary=_generate_summary(errors),
        )

    async def generate_optimization_recommendations(
        self, performance_data: dict[str, Any] | None = None
    ) -> list[Recommendation]:
        """Generate optimization recommendations based on performance data."""
        if not self.rules:
            return []
        recommendations: list[Recommendation] = []
        tech = self.rules.technical_thresholds
        pos = self.rules.position_sizing
        if tech.rsi_oversold < 25:
            recommendations.append(Recommendation(
                priority="medium", category="technical_thresholds",
                field_path="technical_thresholds.rsi_oversold",
                recommendation="Consider raising RSI oversold threshold",
                rationale=f"Current value {tech.rsi_oversold} may trigger too rarely. RSI < 25 is very oversold.",
                suggested_value=30,
            ))
        if pos.max_position_percent < 0.05:
            recommendations.append(Recommendation(
                priority="low", category="position_sizing",
                field_path="position_sizing.max_position_percent",
                recommendation="Max position size may be too conservative",
                rationale=f"Current {pos.max_position_percent:.1%} limits diversification benefits. Consider 5-10%.",
                suggested_value=0.10,
            ))
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
