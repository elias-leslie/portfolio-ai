"""Unit tests for AI Rules Validation Agent (FEAT-008).

Tests cover:
1. Rule integrity checks (threshold ranges, contradictions)
2. Validation scheduling (daily validation task)
3. Error detection (critical, warning, info severities)
4. Report generation (summary, recommendations)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.agents.rules_validator_agent import (
    Recommendation,
    RulesValidatorAgent,
    ValidationError,
    ValidationReport,
)
from app.rules.models import (
    FeeRules,
    PositionSizingRules,
    RiskManagementRules,
    ScoringRules,
    SignalThresholds,
    TechnicalThresholds,
    TradingRules,
)


@pytest.fixture
def validator() -> RulesValidatorAgent:
    """Create a RulesValidatorAgent instance."""
    return RulesValidatorAgent()


@pytest.fixture
def valid_rules() -> TradingRules:
    """Create valid trading rules for testing."""
    return TradingRules(
        version="1.0.0",
        updated="2025-12-11",
        updated_by="Test",
        position_sizing=PositionSizingRules(
            default_risk_percent=0.015,
            min_risk_percent=0.005,
            max_risk_percent=0.05,
            max_position_percent=0.10,  # 10% - reasonable
            max_sector_exposure_pct=0.20,
            max_position_percent_adv=0.01,
        ),
        risk_management=RiskManagementRules(
            portfolio_drawdown_halt_pct=25.0,
            drawdown_warning_level_1=10.0,
            drawdown_warning_level_2=15.0,
        ),
        technical_thresholds=TechnicalThresholds(
            rsi_oversold=30,
            rsi_overbought=70,
        ),
        scoring=ScoringRules(
            price_weight=33.0,
            technical_weight=33.0,
            fundamental_weight=34.0,
            valuation_weight=0.25,
            growth_weight=0.35,
            health_weight=0.25,
            sentiment_weight=0.15,
        ),
        signals=SignalThresholds(
            news_sentiment_positive=0.2,
            news_sentiment_negative=-0.3,
        ),
        fees=FeeRules(
            commission_per_share=0.005,
            commission_per_trade=1.00,
            slippage_bps=5.0,
            slippage_institutional_bps=2.0,
        ),
    )


class TestValidationReport:
    """Test ValidationReport dataclass."""

    def test_validation_report_structure(self) -> None:
        """ValidationReport should have expected fields."""
        report = ValidationReport(
            timestamp=datetime.now(UTC),
            rules_version="1.0.0",
            overall_status="valid",
            errors=[],
            recommendations=[],
            summary="All checks passed",
        )
        assert report.timestamp is not None
        assert report.rules_version == "1.0.0"
        assert report.overall_status == "valid"
        assert isinstance(report.errors, list)
        assert isinstance(report.recommendations, list)

    def test_validation_error_structure(self) -> None:
        """ValidationError should have expected fields."""
        error = ValidationError(
            severity="critical",
            category="threshold_range",
            field_path="technical_thresholds.rsi_oversold",
            message="RSI oversold out of range",
            current_value=150,
            expected_range="0-100",
        )
        assert error.severity == "critical"
        assert error.category == "threshold_range"
        assert error.field_path == "technical_thresholds.rsi_oversold"
        assert error.current_value == 150

    def test_recommendation_structure(self) -> None:
        """Recommendation should have expected fields."""
        rec = Recommendation(
            priority="high",
            category="technical_thresholds",
            field_path="technical_thresholds.rsi_oversold",
            recommendation="Raise RSI oversold threshold",
            rationale="Current value too extreme",
            suggested_value=30,
        )
        assert rec.priority == "high"
        assert rec.suggested_value == 30


class TestThresholdRangeValidation:
    """Test threshold range validation checks."""

    @pytest.mark.asyncio
    async def test_valid_rules_pass_validation(
        self, validator: RulesValidatorAgent, valid_rules: TradingRules
    ) -> None:
        """Valid rules should pass all validation checks."""
        report = await validator.validate_rules(valid_rules)
        assert report.overall_status == "valid"
        assert len(report.errors) == 0

    @pytest.mark.asyncio
    async def test_rsi_oversold_out_of_range(
        self, validator: RulesValidatorAgent, valid_rules: TradingRules
    ) -> None:
        """RSI oversold > 100 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=150,  # Invalid: > 100
                rsi_overbought=70,
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            e.field_path == "technical_thresholds.rsi_oversold"
            and e.severity == "critical"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_rsi_overbought_out_of_range(
        self, validator: RulesValidatorAgent
    ) -> None:
        """RSI overbought < 0 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=30,
                rsi_overbought=-10,  # Invalid: < 0
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            e.field_path == "technical_thresholds.rsi_overbought"
            and e.severity == "critical"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_rsi_oversold_gte_overbought(
        self, validator: RulesValidatorAgent
    ) -> None:
        """RSI oversold >= overbought should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=70,  # Same as overbought
                rsi_overbought=70,
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            "oversold must be < overbought" in e.message for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_risk_percent_out_of_range(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Risk percent > 1.0 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                default_risk_percent=1.5,  # Invalid: > 1.0 (should be 0-1)
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            e.field_path == "position_sizing.default_risk_percent"
            and e.severity == "critical"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_max_position_percent_out_of_range(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Max position percent > 1.0 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                max_position_percent=1.5,  # Invalid: > 1.0
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            e.field_path == "position_sizing.max_position_percent"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_drawdown_halt_out_of_range(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Drawdown halt > 100 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            risk_management=RiskManagementRules(
                portfolio_drawdown_halt_pct=150.0,  # Invalid: > 100
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            e.field_path == "risk_management.portfolio_drawdown_halt_pct"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_news_sentiment_out_of_range(
        self, validator: RulesValidatorAgent
    ) -> None:
        """News sentiment > 1.0 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            signals=SignalThresholds(
                news_sentiment_positive=1.5,  # Invalid: > 1.0
                news_sentiment_negative=-1.5,  # Invalid: < -1.0
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        critical_errors = [e for e in report.errors if e.severity == "critical"]
        assert len(critical_errors) >= 2  # Both positive and negative


class TestContradictionValidation:
    """Test logical contradiction validation checks."""

    @pytest.mark.asyncio
    async def test_min_risk_greater_than_max_risk(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Min risk > max risk should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                min_risk_percent=0.10,  # 10%
                max_risk_percent=0.05,  # 5% - contradicts min
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            "Min risk percent > max risk percent" in e.message for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_drawdown_warnings_not_escalating(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Drawdown warnings not escalating should produce warning."""
        invalid_rules = TradingRules(
            version="1.0.0",
            risk_management=RiskManagementRules(
                drawdown_warning_level_1=15.0,  # Higher than level 2
                drawdown_warning_level_2=10.0,
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "warnings"
        assert any(
            "should escalate" in e.message and e.severity == "warning"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_warning_level_2_exceeds_halt(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Warning level 2 >= halt threshold should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            risk_management=RiskManagementRules(
                drawdown_warning_level_1=10.0,
                drawdown_warning_level_2=30.0,  # >= halt
                portfolio_drawdown_halt_pct=25.0,
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            "Final warning must be < halt threshold" in e.message
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_scoring_weights_dont_sum_to_100(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Scoring weights not summing to 100 should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            scoring=ScoringRules(
                price_weight=30.0,
                technical_weight=30.0,
                fundamental_weight=30.0,  # Total = 90, not 100
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            "Scoring weights must sum to 100" in e.message for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_fundamental_weights_dont_sum_to_1(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Fundamental pillar weights not summing to 1.0 should fail."""
        invalid_rules = TradingRules(
            version="1.0.0",
            scoring=ScoringRules(
                valuation_weight=0.25,
                growth_weight=0.25,
                health_weight=0.25,
                sentiment_weight=0.10,  # Total = 0.85, not 1.0
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            "Fundamental pillar weights must sum to 1.0" in e.message
            for e in report.errors
        )


class TestPositionSizingValidation:
    """Test position sizing validation checks."""

    @pytest.mark.asyncio
    async def test_max_position_excessive_exposure(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Max position * typical positions > 100% should produce warning."""
        invalid_rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                max_position_percent=0.30,  # 30% * 10 positions = 300% exposure
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "warnings"
        assert any(
            ">100%" in e.message and e.severity == "warning" for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_sector_exposure_exceeds_100(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Sector exposure > 100% should fail validation."""
        invalid_rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                max_sector_exposure_pct=1.5,  # 150%
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "critical"
        assert any(
            "Max sector exposure >100%" in e.message for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_position_percent_adv_excessive(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Position > 5% of ADV should produce warning."""
        invalid_rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                max_position_percent_adv=0.10,  # 10% of ADV - may cause slippage
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "warnings"
        assert any(
            "5% of ADV may cause slippage" in e.message for e in report.errors
        )


class TestFeeAssumptionsValidation:
    """Test fee assumptions validation checks."""

    @pytest.mark.asyncio
    async def test_zero_commission_unrealistic(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Zero commission should produce warning."""
        invalid_rules = TradingRules(
            version="1.0.0",
            fees=FeeRules(
                commission_per_share=0.0,
                commission_per_trade=0.0,  # Both zero = unrealistic
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "warnings"
        assert any(
            "Zero commission unrealistic" in e.message and e.severity == "warning"
            for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_slippage_out_of_typical_range(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Slippage outside 1-20 bps should produce warning."""
        invalid_rules = TradingRules(
            version="1.0.0",
            fees=FeeRules(
                slippage_bps=50.0,  # 50 bps - very high
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "warnings"
        assert any(
            "Slippage outside typical range" in e.message for e in report.errors
        )

    @pytest.mark.asyncio
    async def test_institutional_slippage_higher_than_retail(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Institutional slippage >= retail should produce warning."""
        invalid_rules = TradingRules(
            version="1.0.0",
            fees=FeeRules(
                slippage_bps=5.0,
                slippage_institutional_bps=10.0,  # Should be lower than retail
            ),
        )
        report = await validator.validate_rules(invalid_rules)
        assert report.overall_status == "warnings"
        assert any(
            "Institutional slippage should be < retail" in e.message
            for e in report.errors
        )


class TestReportGeneration:
    """Test validation report generation."""

    @pytest.mark.asyncio
    async def test_overall_status_valid(
        self, validator: RulesValidatorAgent, valid_rules: TradingRules
    ) -> None:
        """Report should be 'valid' when no errors."""
        report = await validator.validate_rules(valid_rules)
        assert report.overall_status == "valid"
        assert report.summary == "All validation checks passed. Rules configuration is valid."

    @pytest.mark.asyncio
    async def test_overall_status_warnings(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Report should be 'warnings' when only warnings exist."""
        rules_with_warnings = TradingRules(
            version="1.0.0",
            fees=FeeRules(
                commission_per_share=0.0,
                commission_per_trade=0.0,  # Produces warning
                slippage_bps=5.0,
                slippage_institutional_bps=2.0,
            ),
        )
        report = await validator.validate_rules(rules_with_warnings)
        assert report.overall_status == "warnings"
        assert "warning" in report.summary.lower()

    @pytest.mark.asyncio
    async def test_overall_status_critical(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Report should be 'critical' when critical errors exist."""
        rules_with_critical = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=150,  # Critical error
            ),
        )
        report = await validator.validate_rules(rules_with_critical)
        assert report.overall_status == "critical"
        assert "critical" in report.summary.lower()

    @pytest.mark.asyncio
    async def test_summary_includes_counts(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Summary should include error counts."""
        rules_with_errors = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=150,  # Critical
                rsi_overbought=-10,  # Critical
            ),
            fees=FeeRules(
                commission_per_share=0.0,
                commission_per_trade=0.0,  # Warning
            ),
        )
        report = await validator.validate_rules(rules_with_errors)
        assert "critical error" in report.summary.lower()
        assert "warning" in report.summary.lower()

    @pytest.mark.asyncio
    async def test_report_includes_rules_version(
        self, validator: RulesValidatorAgent, valid_rules: TradingRules
    ) -> None:
        """Report should include rules version from input."""
        valid_rules.version = "2.5.3"
        report = await validator.validate_rules(valid_rules)
        assert report.rules_version == "2.5.3"

    @pytest.mark.asyncio
    async def test_report_includes_timestamp(
        self, validator: RulesValidatorAgent, valid_rules: TradingRules
    ) -> None:
        """Report should include current timestamp."""
        before = datetime.now(UTC)
        report = await validator.validate_rules(valid_rules)
        after = datetime.now(UTC)
        assert before <= report.timestamp <= after


class TestOptimizationRecommendations:
    """Test optimization recommendation generation."""

    @pytest.mark.asyncio
    async def test_rsi_oversold_too_extreme(
        self, validator: RulesValidatorAgent
    ) -> None:
        """RSI oversold < 25 should produce recommendation."""
        rules = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=20,  # Too extreme
                rsi_overbought=70,
            ),
        )
        validator.rules = rules
        recommendations = await validator.generate_optimization_recommendations()
        assert any(
            r.field_path == "technical_thresholds.rsi_oversold"
            and r.suggested_value == 30
            for r in recommendations
        )

    @pytest.mark.asyncio
    async def test_max_position_too_conservative(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Max position < 5% should produce recommendation."""
        rules = TradingRules(
            version="1.0.0",
            position_sizing=PositionSizingRules(
                max_position_percent=0.03,  # 3% - too conservative
            ),
        )
        validator.rules = rules
        recommendations = await validator.generate_optimization_recommendations()
        assert any(
            r.field_path == "position_sizing.max_position_percent"
            and r.suggested_value == 0.10
            for r in recommendations
        )

    @pytest.mark.asyncio
    async def test_recommendations_have_priorities(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Recommendations should have priority levels."""
        rules = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=20,
                rsi_overbought=70,
            ),
        )
        validator.rules = rules
        recommendations = await validator.generate_optimization_recommendations()
        if recommendations:
            for rec in recommendations:
                assert rec.priority in ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_recommendations_have_rationale(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Recommendations should include rationale."""
        rules = TradingRules(
            version="1.0.0",
            technical_thresholds=TechnicalThresholds(
                rsi_oversold=20,
                rsi_overbought=70,
            ),
        )
        validator.rules = rules
        recommendations = await validator.generate_optimization_recommendations()
        if recommendations:
            for rec in recommendations:
                assert len(rec.rationale) > 0
                assert len(rec.recommendation) > 0


class TestValidationWithDefaultRules:
    """Test validation with default rules loaded from file."""

    @pytest.mark.asyncio
    async def test_validate_without_rules_param(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Validation without rules param should load from file."""
        # This will load actual rules from config/trading_rules/v1.0.0/rules.yaml
        report = await validator.validate_rules()
        assert report is not None
        assert report.rules_version is not None
        # Default rules should be valid
        assert report.overall_status in ["valid", "warnings"]

    @pytest.mark.asyncio
    async def test_validate_loads_rules_from_file(
        self, validator: RulesValidatorAgent
    ) -> None:
        """Validator should use get_rules() when no rules provided."""
        with patch("app.agents.rules_validator_agent.get_rules") as mock_get_rules:
            mock_get_rules.return_value = TradingRules(version="mocked")
            report = await validator.validate_rules()
            mock_get_rules.assert_called_once()
            assert report.rules_version == "mocked"
