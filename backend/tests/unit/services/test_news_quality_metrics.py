"""Unit tests for news quality metrics calculation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.services.news_quality_metrics import (
    QualityWeights,
    SourceMetrics,
    _token_overlap_similarity,
    _tokenize,
    calculate_all_metrics,
    calculate_avg_confidence,
    calculate_duplicate_rate,
    calculate_freshness_score,
    calculate_quality_score,
    calculate_user_useful_rate,
)


class TestTokenize:
    """Test _tokenize() helper function."""

    def test_simple_sentence(self) -> None:
        """Tokenize simple sentence."""
        tokens = _tokenize("The quick brown fox")
        assert tokens == ["The", "quick", "brown", "fox"]

    def test_removes_punctuation(self) -> None:
        """Remove punctuation from text."""
        tokens = _tokenize("Hello, world! How are you?")
        assert "Hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_filters_short_tokens(self) -> None:
        """Filter tokens shorter than 3 characters."""
        tokens = _tokenize("I am a big dog")
        assert "big" in tokens
        assert "dog" in tokens
        assert "I" not in tokens
        assert "am" not in tokens
        assert "a" not in tokens

    def test_empty_string(self) -> None:
        """Handle empty string."""
        tokens = _tokenize("")
        assert tokens == []


class TestTokenOverlapSimilarity:
    """Test _token_overlap_similarity() helper function."""

    def test_identical_texts(self) -> None:
        """Identical texts return 1.0."""
        similarity = _token_overlap_similarity("The quick brown fox", "The quick brown fox")
        assert similarity == 1.0

    def test_no_overlap(self) -> None:
        """No overlapping tokens returns 0.0."""
        similarity = _token_overlap_similarity("Apple banana cherry", "Dog elephant frog")
        assert similarity == 0.0

    def test_partial_overlap(self) -> None:
        """Partial overlap returns value between 0 and 1."""
        similarity = _token_overlap_similarity("Apple banana cherry", "Apple banana dog")
        # Jaccard: intersection / union = 2 / 4 = 0.5
        assert similarity == pytest.approx(0.5, abs=0.01)

    def test_empty_texts(self) -> None:
        """Empty texts return 0.0."""
        similarity = _token_overlap_similarity("", "")
        assert similarity == 0.0


class TestCalculateDuplicateRate:
    """Test calculate_duplicate_rate() function."""

    def test_no_duplicates(self) -> None:
        """All unique articles returns 0.0."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (10, 10)  # total, unique
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_duplicate_rate(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert rate == 0.0

    def test_all_duplicates(self) -> None:
        """All duplicate articles returns 1.0."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (10, 1)  # total, unique
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_duplicate_rate(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert rate == 0.9  # (10 - 1) / 10 = 0.9

    def test_partial_duplicates(self) -> None:
        """Some duplicates returns value between 0 and 1."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (10, 8)  # total, unique
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_duplicate_rate(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert rate == pytest.approx(0.2, abs=0.01)  # (10 - 8) / 10 = 0.2

    def test_no_articles(self) -> None:
        """No articles returns 0.0."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (0, 0)  # total, unique
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_duplicate_rate(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert rate == 0.0


class TestCalculateAvgConfidence:
    """Test calculate_avg_confidence() function."""

    def test_high_confidence(self) -> None:
        """High average confidence."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (0.9,)  # avg_confidence
        storage.connection.return_value.__enter__.return_value = conn_mock

        conf = calculate_avg_confidence(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert conf == 0.9

    def test_no_articles(self) -> None:
        """No articles returns 0.0."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (None,)  # avg_confidence
        storage.connection.return_value.__enter__.return_value = conn_mock

        conf = calculate_avg_confidence(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 2, tzinfo=UTC),
        )
        assert conf == 0.0


class TestCalculateFreshnessScore:
    """Test calculate_freshness_score() function."""

    def test_very_fresh_articles(self) -> None:
        """Articles < 24h old return 1.0."""
        now = datetime(2025, 1, 2, 12, 0, tzinfo=UTC)
        published_at = datetime(2025, 1, 2, 6, 0, tzinfo=UTC)  # 6 hours old

        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchall.return_value = [
            (published_at,),
            (published_at,),
            (published_at,),
        ]
        storage.connection.return_value.__enter__.return_value = conn_mock

        freshness = calculate_freshness_score(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 3, tzinfo=UTC),
            now=now,
        )
        assert freshness == 1.0

    def test_stale_articles(self) -> None:
        """Articles > 7d old return 0.0."""
        now = datetime(2025, 1, 10, 12, 0, tzinfo=UTC)
        published_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)  # 9 days old

        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchall.return_value = [(published_at,)]
        storage.connection.return_value.__enter__.return_value = conn_mock

        freshness = calculate_freshness_score(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 11, tzinfo=UTC),
            now=now,
        )
        assert freshness == 0.0

    def test_medium_fresh_articles(self) -> None:
        """Articles between 24h and 7d return value between 0 and 1."""
        now = datetime(2025, 1, 4, 12, 0, tzinfo=UTC)
        published_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)  # 3 days (72h) old

        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchall.return_value = [(published_at,)]
        storage.connection.return_value.__enter__.return_value = conn_mock

        freshness = calculate_freshness_score(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 5, tzinfo=UTC),
            now=now,
        )
        # avg_age = 72h
        # freshness = 1 - ((72 - 24) / (168 - 24)) = 1 - (48/144) = 1 - 0.333 = 0.667
        assert freshness == pytest.approx(0.667, abs=0.01)


class TestCalculateUserUsefulRate:
    """Test calculate_user_useful_rate() function."""

    def test_all_useful(self) -> None:
        """All articles rated useful returns 1.0."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (10, 10)  # useful, total
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_user_useful_rate(storage, "test_vendor", "default")
        assert rate == 1.0

    def test_none_useful(self) -> None:
        """No articles rated useful returns 0.0."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (0, 10)  # useful, total
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_user_useful_rate(storage, "test_vendor", "default")
        assert rate == 0.0

    def test_partial_useful(self) -> None:
        """Some articles useful returns value between 0 and 1."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (7, 10)  # useful, total
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_user_useful_rate(storage, "test_vendor", "default")
        assert rate == 0.7

    def test_no_feedback(self) -> None:
        """No feedback returns None."""
        storage = MagicMock()
        conn_mock = MagicMock()
        conn_mock.execute.return_value.fetchone.return_value = (0, 0)  # useful, total
        storage.connection.return_value.__enter__.return_value = conn_mock

        rate = calculate_user_useful_rate(storage, "test_vendor", "default")
        assert rate is None


class TestCalculateQualityScore:
    """Test calculate_quality_score() function."""

    def test_perfect_quality(self) -> None:
        """Perfect metrics returns 1.0."""
        metrics = SourceMetrics(
            vendor="test",
            duplicate_rate=0.0,
            diversity_score=1.0,
            confidence_avg=1.0,
            freshness_score=1.0,
            user_useful_rate=1.0,
            quality_score=0.0,  # Will be calculated
            article_count=100,
            sample_period_start=datetime(2025, 1, 1, tzinfo=UTC),
        )
        weights = QualityWeights()

        score = calculate_quality_score(metrics, weights)
        assert score == 1.0

    def test_poor_quality(self) -> None:
        """Poor metrics returns low score."""
        metrics = SourceMetrics(
            vendor="test",
            duplicate_rate=1.0,  # All duplicates
            diversity_score=0.0,  # No diversity
            confidence_avg=0.0,  # No confidence
            freshness_score=0.0,  # Stale
            user_useful_rate=0.0,  # Not useful
            quality_score=0.0,
            article_count=100,
            sample_period_start=datetime(2025, 1, 1, tzinfo=UTC),
        )
        weights = QualityWeights()

        score = calculate_quality_score(metrics, weights)
        assert score == 0.0

    def test_no_user_feedback_redistributes_weight(self) -> None:
        """When user_useful_rate is None, weight is redistributed."""
        metrics = SourceMetrics(
            vendor="test",
            duplicate_rate=0.0,
            diversity_score=1.0,
            confidence_avg=1.0,
            freshness_score=1.0,
            user_useful_rate=None,  # No feedback
            quality_score=0.0,
            article_count=100,
            sample_period_start=datetime(2025, 1, 1, tzinfo=UTC),
        )
        weights = QualityWeights(
            duplicate_penalty=0.3,
            diversity=0.3,
            confidence=0.2,
            freshness=0.1,
            user_feedback=0.1,  # This will be redistributed
        )

        score = calculate_quality_score(metrics, weights)
        # With perfect metrics and no user feedback, should still be 1.0
        assert score == 1.0


class TestQualityWeights:
    """Test QualityWeights model."""

    def test_default_weights(self) -> None:
        """Default weights are correct."""
        weights = QualityWeights()
        assert weights.duplicate_penalty == 0.30
        assert weights.diversity == 0.25
        assert weights.confidence == 0.20
        assert weights.freshness == 0.15
        assert weights.user_feedback == 0.10

    def test_normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        # Use weights within valid range (0-1) that don't sum to 1
        weights = QualityWeights(
            duplicate_penalty=0.5,
            diversity=0.3,
            confidence=0.1,
            freshness=0.05,
            user_feedback=0.05,
        )
        normalized = weights.normalize()
        # Sum = 1.0, weights should stay the same
        assert normalized.duplicate_penalty == pytest.approx(0.5, abs=0.01)
        assert normalized.diversity == pytest.approx(0.3, abs=0.01)
        assert normalized.confidence == pytest.approx(0.1, abs=0.01)
        assert normalized.freshness == pytest.approx(0.05, abs=0.01)
        assert normalized.user_feedback == pytest.approx(0.05, abs=0.01)


class TestCalculateAllMetrics:
    """Test calculate_all_metrics() integration function."""

    def test_calculates_all_metrics(self) -> None:
        """Calculate all metrics for a vendor - integration test."""
        # This is a smoke test - just verify it runs without error
        # with mocked storage. Full integration tests will use real DB.
        storage = MagicMock()
        conn_mock = MagicMock()

        # Setup sequential return values for multiple queries
        fetch_results = [
            (10, 8),  # duplicate_rate query (total, unique)
            [],  # diversity_score query (headlines) - fetchall
            (0.85,),  # confidence_avg query
            [],  # freshness_score query - fetchall
            (7, 10),  # user_useful_rate query
            (10,),  # article_count query
        ]

        call_count = [0]

        def side_effect_execute(*args: object, **kwargs: object) -> MagicMock:
            result = MagicMock()
            idx = call_count[0]
            call_count[0] += 1

            if idx in [1, 3]:  # fetchall queries
                result.fetchall.return_value = fetch_results[idx]
            else:  # fetchone queries
                result.fetchone.return_value = fetch_results[idx]

            return result

        conn_mock.execute.side_effect = side_effect_execute
        storage.connection.return_value.__enter__.return_value = conn_mock

        # For simplicity, test that function runs without error
        metrics = calculate_all_metrics(
            storage,
            "test_vendor",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 3, tzinfo=UTC),
        )

        assert metrics.vendor == "test_vendor"
        assert 0.0 <= metrics.quality_score <= 1.0
        assert metrics.article_count >= 0
