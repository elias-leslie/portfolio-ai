"""Tests for cross-validation service.

Tests the CrossValidationService for multi-agent output verification.
"""

from __future__ import annotations

from app.services.cross_validation import (
    CrossValidationService,
    CrossValidationSettings,
    DisagreementReason,
    ValidationResult,
    ValidationStatus,
)


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_default_values(self) -> None:
        """Test ValidationResult has sensible defaults."""
        result = ValidationResult()
        assert result.generator_provider == "gemini"
        assert result.validator_provider == "claude"
        assert result.status == ValidationStatus.PENDING
        assert result.has_disagreement is False
        assert result.disagreement_reasons == []

    def test_id_generation(self) -> None:
        """Test ValidationResult generates unique IDs."""
        result1 = ValidationResult()
        result2 = ValidationResult()
        assert result1.id != result2.id
        assert len(result1.id) == 36  # UUID format


class TestCrossValidationSettings:
    """Tests for CrossValidationSettings TypedDict."""

    def test_default_settings(self) -> None:
        """Test default settings are sensible."""
        from app.services.cross_validation import DEFAULT_SETTINGS

        assert DEFAULT_SETTINGS["enabled"] is True
        assert DEFAULT_SETTINGS["require_human_review"] is True
        assert DEFAULT_SETTINGS["full_auto_mode"] is False
        assert DEFAULT_SETTINGS["auto_apply_threshold"] == 0.9


class TestCrossValidationService:
    """Tests for CrossValidationService."""

    def test_init_with_defaults(self) -> None:
        """Test service initializes with default settings."""
        service = CrossValidationService()
        assert service.settings["enabled"] is True
        assert service._generator is None
        assert service._validator is None

    def test_init_with_custom_settings(self) -> None:
        """Test service initializes with custom settings."""
        settings: CrossValidationSettings = {
            "enabled": False,
            "require_human_review": False,
            "full_auto_mode": True,
            "notify_on_disagreement": False,
            "auto_apply_threshold": 0.5,
        }
        service = CrossValidationService(settings=settings)
        assert service.settings["enabled"] is False
        assert service.settings["full_auto_mode"] is True

    def test_validate_disabled(self) -> None:
        """Test validation when disabled returns auto-approved result."""
        settings: CrossValidationSettings = {
            "enabled": False,
            "require_human_review": True,
            "full_auto_mode": False,
            "notify_on_disagreement": True,
            "auto_apply_threshold": 0.9,
        }
        service = CrossValidationService(settings=settings)

        result = service.validate(
            generator_output="Test output",
            context_type="insight",
            context_symbol="AAPL",
        )

        assert result.validator_approved is True
        assert result.status == ValidationStatus.AUTO_APPLIED
        assert result.final_output == "Test output"
        assert result.validator_review == "Cross-validation disabled"

    def test_parse_review_response_json(self) -> None:
        """Test parsing JSON review response."""
        service = CrossValidationService()

        # Test clean JSON
        content = '{"approved": true, "confidence": 0.95, "review_summary": "Looks good"}'
        result = service._parse_review_response(content)
        assert result["approved"] is True
        assert result["confidence"] == 0.95

    def test_parse_review_response_markdown_json(self) -> None:
        """Test parsing JSON in markdown code block."""
        service = CrossValidationService()

        content = """Here is my review:
```json
{"approved": false, "confidence": 0.3, "issues_found": ["factual error"]}
```
"""
        result = service._parse_review_response(content)
        assert result["approved"] is False
        assert "factual error" in result["issues_found"]

    def test_parse_review_response_invalid_json(self) -> None:
        """Test parsing invalid JSON returns fallback."""
        service = CrossValidationService()

        content = "This is not JSON at all"
        result = service._parse_review_response(content)
        assert result["approved"] is False
        assert result["review_summary"] == content

    def test_determine_status_rejected(self) -> None:
        """Test status determination when validator rejects."""
        service = CrossValidationService()

        result = ValidationResult(validator_approved=False)
        status = service._determine_status(result)
        assert status == ValidationStatus.PENDING

    def test_determine_status_approved_require_review(self) -> None:
        """Test status when approved but human review required."""
        settings: CrossValidationSettings = {
            "enabled": True,
            "require_human_review": True,
            "full_auto_mode": False,
            "notify_on_disagreement": True,
            "auto_apply_threshold": 0.9,
        }
        service = CrossValidationService(settings=settings)

        result = ValidationResult(validator_approved=True)
        status = service._determine_status(result)
        assert status == ValidationStatus.PENDING

    def test_determine_status_full_auto_high_confidence(self) -> None:
        """Test status in full auto mode with high confidence."""
        settings: CrossValidationSettings = {
            "enabled": True,
            "require_human_review": False,
            "full_auto_mode": True,
            "notify_on_disagreement": True,
            "auto_apply_threshold": 0.9,
        }
        service = CrossValidationService(settings=settings)

        result = ValidationResult(
            validator_approved=True,
            validator_confidence=0.95,
        )
        status = service._determine_status(result)
        assert status == ValidationStatus.AUTO_APPLIED

    def test_determine_status_full_auto_low_confidence(self) -> None:
        """Test status in full auto mode with low confidence."""
        settings: CrossValidationSettings = {
            "enabled": True,
            "require_human_review": False,
            "full_auto_mode": True,
            "notify_on_disagreement": True,
            "auto_apply_threshold": 0.9,
        }
        service = CrossValidationService(settings=settings)

        result = ValidationResult(
            validator_approved=True,
            validator_confidence=0.5,
        )
        status = service._determine_status(result)
        assert status == ValidationStatus.PENDING


class TestDisagreementReason:
    """Tests for DisagreementReason enum."""

    def test_all_reasons(self) -> None:
        """Test all disagreement reasons exist."""
        assert DisagreementReason.FACTUAL.value == "factual"
        assert DisagreementReason.LOGICAL.value == "logical"
        assert DisagreementReason.RISK_ASSESSMENT.value == "risk_assessment"
        assert DisagreementReason.CONFIDENCE.value == "confidence"
        assert DisagreementReason.OTHER.value == "other"


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_all_statuses(self) -> None:
        """Test all validation statuses exist."""
        assert ValidationStatus.PENDING.value == "pending"
        assert ValidationStatus.APPROVED.value == "approved"
        assert ValidationStatus.REJECTED.value == "rejected"
        assert ValidationStatus.AUTO_APPLIED.value == "auto_applied"
        assert ValidationStatus.MODIFIED.value == "modified"
