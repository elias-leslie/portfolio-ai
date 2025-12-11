"""Unit tests for watchlist dual-provider LLM review endpoint (FEAT-127)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.agents.multi_reviewer import (
    DisagreementSeverity,
    DualReviewResult,
    ProviderReview,
)
from app.api.watchlist import review_strategy_signal


class TestReviewStrategySignalDualMode:
    """Tests for POST /api/watchlist/{item_id}/review with dual=True (FEAT-127)."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage instance."""
        return MagicMock()

    @pytest.fixture
    def sample_watchlist_item(self) -> list[dict]:
        """Sample watchlist item data."""
        return [
            {
                "id": "item-123",
                "symbol": "AAPL",
                "note": "Test item",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]

    @pytest.fixture
    def sample_snapshot(self) -> list[dict]:
        """Sample watchlist snapshot data."""
        return [
            {
                "id": "snap-456",
                "item_id": "item-123",
                "fetched_at": datetime.now(UTC),
                "signal_type": "BUY",
                "signal_strength": 8,
                "recommended_style": "swing",
                "risk_level": "MEDIUM",
                "rationale": "Strong momentum with volume confirmation",
                "current_score": json.dumps(
                    {
                        "overall": 75,
                        "price": {"score": 80},
                        "technical": {"score": 70},
                    }
                ),
                "news_sentiment_score": 0.6,
            }
        ]

    @pytest.fixture
    def sample_dual_review_result(self) -> DualReviewResult:
        """Sample dual review result."""
        return DualReviewResult(
            symbol="AAPL",
            review_pair_id="pair-789",
            gemini_review=ProviderReview(
                provider="gemini",
                review_text="Strong buy signal with positive momentum indicators.",
                is_valid=True,
                disagreement=False,
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            ),
            claude_review=ProviderReview(
                provider="claude",
                review_text="Positive setup with favorable risk/reward ratio.",
                is_valid=True,
                disagreement=False,
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            ),
            agreement_score=0.85,
            disagreement_severity=DisagreementSeverity.NONE,
            provider_disagreement=False,
            consensus_summary="Both reviewers agree on the assessment",
        )

    @pytest.mark.asyncio
    async def test_returns_dual_review_result(
        self,
        mock_storage: MagicMock,
        sample_watchlist_item: list[dict],
        sample_snapshot: list[dict],
        sample_dual_review_result: DualReviewResult,
    ) -> None:
        """Test that dual review returns structured result from both providers."""
        # Mock database queries
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        # Mock MultiReviewer
        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.return_value = sample_dual_review_result

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ), patch.object(mock_storage, "connection"):
            result = await review_strategy_signal(item_id="item-123", dual=True)

            # Verify response structure
            assert result["symbol"] == "AAPL"
            assert result["review_pair_id"] == "pair-789"
            assert result["gemini_review"] is not None
            assert result["claude_review"] is not None
            assert result["agreement_score"] == 0.85
            assert result["disagreement_severity"] == "none"
            assert result["provider_disagreement"] is False
            assert result["consensus_summary"] == "Both reviewers agree on the assessment"

    @pytest.mark.asyncio
    async def test_stores_both_reviews_in_database(
        self,
        mock_storage: MagicMock,
        sample_watchlist_item: list[dict],
        sample_snapshot: list[dict],
        sample_dual_review_result: DualReviewResult,
    ) -> None:
        """Test that both provider reviews are stored in strategy_reviews table."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.return_value = sample_dual_review_result

        mock_conn = MagicMock()
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ):
            await review_strategy_signal(item_id="item-123", dual=True)

            # Verify that execute was called twice (once for each review)
            assert mock_conn.execute.call_count == 2

            # Verify both calls were to strategy_reviews table
            for call in mock_conn.execute.call_args_list:
                sql = call[0][0]
                assert "INSERT INTO strategy_reviews" in sql
                assert "review_pair_id" in sql
                assert "disagreement_severity" in sql
                assert "provider_disagreement" in sql
                assert "agreement_score" in sql

    @pytest.mark.asyncio
    async def test_raises_404_when_item_not_found(self, mock_storage: MagicMock) -> None:
        """Test that 404 is raised when watchlist item doesn't exist."""
        item_df = MagicMock()
        item_df.is_empty.return_value = True

        mock_storage.query.return_value = item_df

        with patch("app.api.watchlist.storage", mock_storage), pytest.raises(
            HTTPException
        ) as exc_info:
            await review_strategy_signal(item_id="nonexistent-id", dual=True)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_404_when_no_snapshot(
        self, mock_storage: MagicMock, sample_watchlist_item: list[dict]
    ) -> None:
        """Test that 404 is raised when no snapshot exists for item."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = True

        mock_storage.query.side_effect = [item_df, snapshot_df]

        with patch("app.api.watchlist.storage", mock_storage), pytest.raises(
            HTTPException
        ) as exc_info:
            await review_strategy_signal(item_id="item-123", dual=True)

        assert exc_info.value.status_code == 404
        assert "No snapshot found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_handles_disagreement_between_providers(
        self,
        mock_storage: MagicMock,
        sample_watchlist_item: list[dict],
        sample_snapshot: list[dict],
    ) -> None:
        """Test that provider disagreement is correctly reported."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        # Create result with major disagreement
        disagreement_result = DualReviewResult(
            symbol="AAPL",
            review_pair_id="pair-disagreement",
            gemini_review=ProviderReview(
                provider="gemini",
                review_text="Strong buy signal with bullish indicators.",
                is_valid=True,
                disagreement=False,
                usage={},
            ),
            claude_review=ProviderReview(
                provider="claude",
                review_text="Bearish setup with downside risk.",
                is_valid=True,
                disagreement=False,
                usage={},
            ),
            agreement_score=0.3,
            disagreement_severity=DisagreementSeverity.MAJOR,
            provider_disagreement=True,
            consensus_summary="ALERT: Reviewers significantly disagree - manual review recommended",
        )

        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.return_value = disagreement_result

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ), patch.object(mock_storage, "connection"):
            result = await review_strategy_signal(item_id="item-123", dual=True)

            assert result["disagreement_severity"] == "major"
            assert result["provider_disagreement"] is True
            assert result["agreement_score"] == 0.3
            assert "ALERT" in result["consensus_summary"]

    @pytest.mark.asyncio
    async def test_handles_provider_errors_gracefully(
        self,
        mock_storage: MagicMock,
        sample_watchlist_item: list[dict],
        sample_snapshot: list[dict],
    ) -> None:
        """Test that provider errors are handled gracefully in dual mode."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        # Create result where one provider failed
        partial_result = DualReviewResult(
            symbol="AAPL",
            review_pair_id="pair-partial",
            gemini_review=ProviderReview(
                provider="gemini",
                review_text="Analysis complete.",
                is_valid=True,
                disagreement=False,
                usage={},
            ),
            claude_review=ProviderReview(
                provider="claude",
                review_text="Review unavailable",
                is_valid=False,
                disagreement=False,
                usage={},
                error="Provider timeout",
            ),
            agreement_score=1.0,
            disagreement_severity=DisagreementSeverity.NONE,
            provider_disagreement=False,
            consensus_summary="Only Gemini review available",
        )

        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.return_value = partial_result

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ), patch.object(mock_storage, "connection"):
            result = await review_strategy_signal(item_id="item-123", dual=True)

            assert result["gemini_review"] is not None
            assert result["claude_review"]["error"] == "Provider timeout"

    @pytest.mark.asyncio
    async def test_dual_mode_default_behavior(
        self,
        mock_storage: MagicMock,
        sample_watchlist_item: list[dict],
        sample_snapshot: list[dict],
        sample_dual_review_result: DualReviewResult,
    ) -> None:
        """Test that dual mode is the default (dual=True by default)."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.return_value = sample_dual_review_result

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ), patch.object(mock_storage, "connection"):
            # Call without dual parameter (should default to True)
            result = await review_strategy_signal(item_id="item-123")

            # Should receive dual review result
            assert "review_pair_id" in result
            assert "gemini_review" in result
            assert "claude_review" in result

    @pytest.mark.asyncio
    async def test_review_data_includes_all_signal_fields(
        self,
        mock_storage: MagicMock,
        sample_watchlist_item: list[dict],
        sample_snapshot: list[dict],
        sample_dual_review_result: DualReviewResult,
    ) -> None:
        """Test that review receives all necessary signal data fields."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.return_value = sample_dual_review_result

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ), patch.object(mock_storage, "connection"):
            await review_strategy_signal(item_id="item-123", dual=True)

            # Verify signal_data passed to reviewer
            call_args = mock_reviewer.review_signal_dual.call_args
            signal_data = call_args[0][0]

            assert signal_data["symbol"] == "AAPL"
            assert signal_data["signal_type"] == "BUY"
            assert signal_data["signal_strength"] == 8
            assert signal_data["recommended_style"] == "swing"
            assert signal_data["risk_level"] == "MEDIUM"
            assert signal_data["rationale"] == "Strong momentum with volume confirmation"
            assert "current_score" in signal_data
            assert signal_data["news_sentiment_score"] == 0.6

    @pytest.mark.asyncio
    async def test_raises_500_on_review_failure(
        self, mock_storage: MagicMock, sample_watchlist_item: list[dict], sample_snapshot: list[dict]
    ) -> None:
        """Test that 500 error is raised when review fails."""
        item_df = MagicMock()
        item_df.is_empty.return_value = False
        item_df.to_dicts.return_value = sample_watchlist_item

        snapshot_df = MagicMock()
        snapshot_df.is_empty.return_value = False
        snapshot_df.to_dicts.return_value = sample_snapshot

        mock_storage.query.side_effect = [item_df, snapshot_df]

        mock_reviewer = AsyncMock()
        mock_reviewer.review_signal_dual.side_effect = Exception("Review failed")

        with patch("app.api.watchlist.storage", mock_storage), patch(
            "app.api.watchlist.multi_reviewer", mock_reviewer
        ), pytest.raises(HTTPException) as exc_info:
            await review_strategy_signal(item_id="item-123", dual=True)

        assert exc_info.value.status_code == 500
        assert "Review failed" in exc_info.value.detail
