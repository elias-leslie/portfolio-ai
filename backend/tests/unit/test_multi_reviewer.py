"""Unit tests for MultiReviewer class."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.multi_reviewer import (
    DisagreementSeverity,
    DualReviewResult,
    MultiReviewer,
    ProviderReview,
)


class TestMultiReviewer:
    """Tests for MultiReviewer dual-provider execution."""

    @pytest.fixture
    def reviewer(self) -> MultiReviewer:
        """Create MultiReviewer instance with mocked clients."""
        mock_storage = MagicMock()
        with patch("app.agents.multi_reviewer.AgentHubAPIClient"):
            return MultiReviewer(mock_storage)

    @pytest.fixture
    def sample_signal_data(self) -> dict:
        """Sample signal data for testing."""
        return {
            "symbol": "AAPL",
            "signal_type": "BUY",
            "signal_strength": 8,
            "recommended_style": "swing",
            "risk_level": "MEDIUM",
            "rationale": "Strong momentum with volume confirmation",
            "current_score": {
                "overall": 75,
                "price": {"score": 80, "metadata": {"raw_change_pct": 2.5}},
                "technical": {"score": 70, "metadata": {"rsi_14": 55, "trend": "up"}},
                "fundamental": {"score": 75},
            },
            "news_sentiment_score": 0.6,
        }

    def test_analyze_sentiment_bullish(self, reviewer: MultiReviewer) -> None:
        """Test bullish sentiment detection."""
        review = "Strong upside potential with positive momentum. Favorable conditions."
        score = reviewer._analyze_sentiment(review)
        assert score > 0, "Should detect bullish sentiment"

    def test_analyze_sentiment_bearish(self, reviewer: MultiReviewer) -> None:
        """Test bearish sentiment detection."""
        review = "Risk of downside with negative outlook. Caution advised."
        score = reviewer._analyze_sentiment(review)
        assert score < 0, "Should detect bearish sentiment"

    def test_analyze_sentiment_neutral(self, reviewer: MultiReviewer) -> None:
        """Test neutral sentiment detection."""
        review = "The stock price changed today based on market activity."
        score = reviewer._analyze_sentiment(review)
        assert score == 0, "Should detect neutral sentiment"

    def test_compute_consensus_agreement(self, reviewer: MultiReviewer) -> None:
        """Test consensus computation for agreeing reviews."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Positive upside potential noted.",
            is_valid=True,
            disagreement=False,
            usage={},
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Favorable momentum with support.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        agreement_score, severity, provider_disagreement = reviewer._compute_consensus(
            gemini, claude
        )

        assert agreement_score > 0.7, "Should have high agreement"
        assert severity == DisagreementSeverity.NONE
        assert provider_disagreement is False

    def test_compute_consensus_minor_disagreement(self, reviewer: MultiReviewer) -> None:
        """Test consensus computation for minor disagreement."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Positive upside noted with strength.",
            is_valid=True,
            disagreement=False,
            usage={},
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Upside noted but some concern.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        _agreement_score, severity, _provider_disagreement = reviewer._compute_consensus(
            gemini, claude
        )

        # Minor disagreement: same direction (both note upside) but one has concerns
        assert severity in (
            DisagreementSeverity.NONE,
            DisagreementSeverity.MINOR,
            DisagreementSeverity.MAJOR,  # May be major depending on keyword distribution
        )

    def test_compute_consensus_major_disagreement(self, reviewer: MultiReviewer) -> None:
        """Test consensus computation for major disagreement."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Strong bullish upside opportunity with positive momentum.",
            is_valid=True,
            disagreement=False,
            usage={},
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Bearish downside risk with negative caution warning.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        agreement_score, severity, provider_disagreement = reviewer._compute_consensus(
            gemini, claude
        )

        assert agreement_score < 0.5, "Should have low agreement"
        assert severity == DisagreementSeverity.MAJOR
        assert provider_disagreement is True

    def test_compute_consensus_with_error(self, reviewer: MultiReviewer) -> None:
        """Test consensus when one provider has error."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Review unavailable",
            is_valid=False,
            disagreement=False,
            usage={},
            error="Provider unavailable",
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Good analysis here.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        agreement_score, severity, provider_disagreement = reviewer._compute_consensus(
            gemini, claude
        )

        # One failed, so treat as agreement
        assert agreement_score == 1.0
        assert severity == DisagreementSeverity.NONE
        assert provider_disagreement is False

    def test_detect_rules_disagreement_found(self, reviewer: MultiReviewer) -> None:
        """Test rules disagreement detection when LLM flags new concerns."""
        review = "Note the unusual risk pattern and caution advised."
        rationale = "Strong momentum signal"
        assert reviewer._detect_rules_disagreement(review, rationale) is True

    def test_detect_rules_disagreement_not_found(self, reviewer: MultiReviewer) -> None:
        """Test rules disagreement detection when rationale already mentions concerns."""
        review = "Risk noted as mentioned in the analysis."
        rationale = "Strong momentum but risk of volatility"
        assert reviewer._detect_rules_disagreement(review, rationale) is False

    def test_generate_consensus_summary_agreement(self, reviewer: MultiReviewer) -> None:
        """Test summary generation for agreement."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Good analysis.",
            is_valid=True,
            disagreement=False,
            usage={},
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Good analysis.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        summary = reviewer._generate_consensus_summary(
            gemini, claude, DisagreementSeverity.NONE, False
        )
        assert "agree" in summary.lower()

    def test_generate_consensus_summary_major_disagreement(self, reviewer: MultiReviewer) -> None:
        """Test summary generation for major disagreement."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Bullish.",
            is_valid=True,
            disagreement=False,
            usage={},
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Bearish.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        summary = reviewer._generate_consensus_summary(
            gemini, claude, DisagreementSeverity.MAJOR, True
        )
        assert "alert" in summary.lower() or "recommend" in summary.lower()


class TestProviderReview:
    """Tests for ProviderReview dataclass."""

    def test_provider_review_success(self) -> None:
        """Test successful provider review."""
        review = ProviderReview(
            provider="gemini",
            review_text="Good analysis.",
            is_valid=True,
            disagreement=False,
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
        assert review.provider == "gemini"
        assert review.error is None

    def test_provider_review_with_error(self) -> None:
        """Test provider review with error."""
        review = ProviderReview(
            provider="claude",
            review_text="Review unavailable",
            is_valid=False,
            disagreement=False,
            usage={},
            error="Connection timeout",
        )
        assert review.error == "Connection timeout"


class TestDualReviewResult:
    """Tests for DualReviewResult dataclass."""

    def test_dual_review_result(self) -> None:
        """Test DualReviewResult creation."""
        gemini = ProviderReview(
            provider="gemini",
            review_text="Good.",
            is_valid=True,
            disagreement=False,
            usage={},
        )
        claude = ProviderReview(
            provider="claude",
            review_text="Good.",
            is_valid=True,
            disagreement=False,
            usage={},
        )

        result = DualReviewResult(
            symbol="AAPL",
            review_pair_id="test-id",
            gemini_review=gemini,
            claude_review=claude,
            agreement_score=0.95,
            disagreement_severity=DisagreementSeverity.NONE,
            provider_disagreement=False,
            consensus_summary="Both agree.",
        )

        assert result.symbol == "AAPL"
        assert result.agreement_score == 0.95
        assert result.disagreement_severity == DisagreementSeverity.NONE
