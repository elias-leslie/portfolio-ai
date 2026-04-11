"""Unit tests for news quality scoring service."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.news_quality_scoring import NewsQualityScorer


def test_score_articles_uses_heuristic_mode_when_model_is_missing() -> None:
    scorer = NewsQualityScorer()
    scorer.quality_model = None
    scorer.mode = "heuristic"

    articles = [
        SimpleNamespace(
            symbol="AAPL",
            headline="Apple raises revenue guidance after reporting $98.2B in quarterly sales",
            summary=(
                "Apple said gross margin expanded and management increased full-year outlook "
                "after earnings beat consensus estimates."
            ),
        ),
        SimpleNamespace(
            symbol="TSLA",
            headline="3 EV Stocks to Buy Now?",
            summary="Analysts say these names could soar as the market heats up.",
        )
    ]

    returned = scorer.score_articles(articles)

    assert returned is articles
    assert articles[0].quality_prediction is True
    assert articles[0].quality_confidence is not None
    assert articles[0].quality_confidence > 0.55
    assert articles[1].quality_prediction is False
    assert articles[1].quality_confidence is not None
    assert articles[1].quality_confidence > 0.55


def test_news_quality_scorer_reports_ml_mode_when_model_is_loaded() -> None:
    scorer = NewsQualityScorer()

    assert scorer.mode in {"ml", "heuristic"}
    assert scorer.is_available() is True
    assert scorer.is_model_available() is (scorer.mode == "ml")


def test_score_articles_rejects_personal_advice_and_non_market_policy_stories() -> None:
    scorer = NewsQualityScorer()
    scorer.quality_model = None
    scorer.mode = "heuristic"

    articles = [
        SimpleNamespace(
            symbol="__MARKET__",
            headline=(
                "I'm 71 and have $6 million after scrimping and saving. "
                "My son wants money for a house. Do I say yes?"
            ),
            summary=(
                "A personal-finance advice column about family money decisions "
                "and whether to help an adult child buy a house."
            ),
        ),
        SimpleNamespace(
            symbol="__MARKET__",
            headline="Battles brew over in-state tuition for undocumented students",
            summary=(
                "States are challenging tuition rules for undocumented students, "
                "but the article does not connect the issue to markets, rates, "
                "earnings, or portfolio exposures."
            ),
        ),
    ]

    returned = scorer.score_articles(articles)

    assert returned is articles
    assert articles[0].quality_prediction is False
    assert articles[0].quality_confidence is not None
    assert articles[0].quality_confidence > 0.55
    assert articles[1].quality_prediction is False
    assert articles[1].quality_confidence is not None
    assert articles[1].quality_confidence > 0.55
