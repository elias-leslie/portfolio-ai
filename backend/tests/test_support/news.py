from __future__ import annotations

from unittest.mock import MagicMock

from app.services import NewsBundle, NewsSummary


def build_empty_news_service() -> MagicMock:
    """Return a NewsService-shaped mock with deterministic empty responses."""
    news_service = MagicMock()
    news_service.get_watchlist_news.side_effect = lambda symbols, **_: {
        symbol: NewsBundle(
            symbol=symbol,
            summary=NewsSummary(
                symbol=symbol,
                score=None,
                score_change=None,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                article_count=0,
                latest_published_at=None,
            ),
            articles=[],
        )
        for symbol in symbols
    }
    news_service.get_news_intelligence.side_effect = lambda symbol, **_: NewsBundle(
        symbol=symbol,
        summary=NewsSummary(
            symbol=symbol,
            score=None,
            score_change=None,
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            article_count=0,
            latest_published_at=None,
        ),
        articles=[],
    )
    return news_service
