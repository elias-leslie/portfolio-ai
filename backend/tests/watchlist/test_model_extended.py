"""Test extended WatchlistSnapshot model with narrative intelligence fields."""

from datetime import UTC, datetime

from app.watchlist.models import WatchlistSnapshot


class TestExtendedWatchlistSnapshot:
    """Test extended WatchlistSnapshot model with all narrative fields."""

    def test_snapshot_with_narrative_fields(self):
        """Verify WatchlistSnapshot accepts all narrative intelligence fields."""
        now = datetime.now(UTC)

        snapshot = WatchlistSnapshot(
            item_id="test-item-1",
            fetched_at=now,
            overall_score=75.0,
            # Narrative intelligence fields
            signal_type="BUY",
            signal_strength=9,
            narrative_headline="STRONG BUY - Quality Company + Good Setup",
            narrative_why_bullets={"technical": ["Uptrend", "Good volume"]},
            narrative_company_health={"rating": "EXCELLENT", "bullets": []},
            narrative_technical={"bullets": ["Strong momentum"]},
            narrative_action_plan="BUY around $200",
            narrative_position_sizing="71 shares = $14,377",
            narrative_special_notes="Earnings in 3 weeks",
            # Trade calculations
            entry_price=202.0,
            stop_loss=195.0,
            profit_target=216.0,
            position_size_shares=71,
            # Trading style
            recommended_style="Trend",
            style_confidence=8,
            optimal_holding_period="8-12 weeks",
            risk_level="Medium",
            # Fundamentals & news
            company_health="EXCELLENT",
            earnings_date=datetime(2025, 11, 20, tzinfo=UTC),
            earnings_days_away=18,
            news_sentiment_score=0.35,
            recent_news_headlines={
                "summary": {
                    "symbol": "TEST",
                    "score": 0.35,
                    "score_change": 0.1,
                    "positive_count": 1,
                    "neutral_count": 0,
                    "negative_count": 0,
                    "article_count": 1,
                    "latest_published_at": now.isoformat(),
                    "model_breakdown": {"finbert": 1},
                },
                "articles": [
                    {
                        "symbol": "TEST",
                        "headline": "Beats earnings",
                        "url": "https://example.com/article",
                        "summary": "Shares rally after results",
                        "source": "Example",
                        "published_at": now.isoformat(),
                        "fetched_at": now.isoformat(),
                        "sentiment": {
                            "score": 0.6,
                            "label": "positive",
                            "confidence": 0.9,
                            "model": "finbert",
                            "probabilities": {
                                "positive": 0.9,
                                "neutral": 0.08,
                                "negative": 0.02,
                            },
                        },
                    }
                ],
            },
        )

        assert snapshot.signal_type == "BUY"
        assert snapshot.signal_strength == 9
        assert snapshot.narrative_headline is not None
        assert snapshot.entry_price == 202.0
        assert snapshot.stop_loss == 195.0
        assert snapshot.profit_target == 216.0
        assert snapshot.position_size_shares == 71
        assert snapshot.recommended_style == "Trend"
        assert snapshot.company_health == "EXCELLENT"
        assert snapshot.earnings_days_away == 18
        assert snapshot.news_sentiment_score == 0.35

    def test_snapshot_to_upsert_params_includes_narrative_fields(self):
        """Verify to_upsert_params() serializes all narrative fields."""
        now = datetime.now(UTC)

        snapshot = WatchlistSnapshot(
            item_id="test-item-2",
            fetched_at=now,
            signal_type="HOLD",
            signal_strength=5,
            narrative_headline="HOLD - Wait for better setup",
            narrative_why_bullets={"reasons": ["Overbought"]},
            entry_price=150.0,
            recommended_style="Value",
        )

        params = snapshot.to_upsert_params()

        assert params["signal_type"] == "HOLD"
        assert params["signal_strength"] == 5
        assert params["narrative_headline"] == "HOLD - Wait for better setup"
        assert params["narrative_why_bullets"] == {"reasons": ["Overbought"]}
        assert params["entry_price"] == 150.0
        assert params["recommended_style"] == "Value"

    def test_snapshot_with_none_narrative_fields(self):
        """Verify WatchlistSnapshot handles None for optional narrative fields."""
        now = datetime.now(UTC)

        snapshot = WatchlistSnapshot(
            item_id="test-item-3",
            fetched_at=now,
            signal_type=None,
            signal_strength=None,
            narrative_headline=None,
            entry_price=None,
            company_health=None,
        )

        assert snapshot.signal_type is None
        assert snapshot.signal_strength is None
        assert snapshot.narrative_headline is None
        assert snapshot.entry_price is None
        assert snapshot.company_health is None

        params = snapshot.to_upsert_params()
        assert params["signal_type"] is None
        assert params["entry_price"] is None
