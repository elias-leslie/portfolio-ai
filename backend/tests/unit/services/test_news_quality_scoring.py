"""Unit tests for news quality scoring service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from app.services.news_quality_scoring import NewsQualityScorer


def test_score_articles_skips_without_warning_when_model_is_missing(
    monkeypatch,
) -> None:
    scorer = NewsQualityScorer()
    scorer.quality_model = None

    warning = Mock()
    debug = Mock()
    monkeypatch.setattr("app.services.news_quality_scoring.logger.warning", warning)
    monkeypatch.setattr("app.services.news_quality_scoring.logger.debug", debug)

    articles = [
        SimpleNamespace(
            symbol="AAPL",
            headline="Apple files updated earnings release",
            summary="Revenue and margin guidance changed.",
        )
    ]

    returned = scorer.score_articles(articles)

    assert returned is articles
    warning.assert_not_called()
    debug.assert_called_once()
