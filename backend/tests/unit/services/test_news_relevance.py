"""Unit tests for symbol-specific news relevance filtering."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.news_models import NewsArticle, SentimentScore
from app.services.news_relevance import filter_symbol_relevant_articles


def _article(*, symbol: str, headline: str, source: str, summary: str, raw: dict) -> NewsArticle:
    return NewsArticle(
        symbol=symbol,
        headline=headline,
        summary=summary,
        source=source,
        url=raw.get("url"),
        fetched_at=datetime(2026, 4, 18, 20, 0, tzinfo=UTC),
        published_at=datetime(2026, 4, 18, 19, 0, tzinfo=UTC),
        sentiment=SentimentScore(
            score=0.1,
            label="neutral",
            confidence=0.9,
            model="finbert",
            probabilities={"neutral": 0.9},
        ),
        content_hash=f"{symbol}-{headline}",
        raw=raw,
        vendor=raw.get("vendor"),
    )


def test_filter_symbol_relevant_articles_drops_incidental_multi_ticker_mentions() -> None:
    incidental = _article(
        symbol="TSLA",
        headline="An Alphabet Stock Deep Dive",
        source="The Motley Fool",
        summary=(
            "Motley Fool contributors analyze Alphabet's diverse business portfolio, "
            "including Waymo, SpaceX, Anthropic, and cloud growth."
        ),
        raw={
            "vendor": "polygon",
            "vendor_payload": {
                "tickers": ["GOOG", "GOOGL", "NFLX", "MSFT", "NVDA", "TSLA", "DIS"],
                "insights": [
                    {"ticker": "TSLA", "sentiment": "neutral"},
                    {"ticker": "GOOG", "sentiment": "positive"},
                ],
                "article_url": "https://www.fool.com/investing/2026/04/18/an-alphabet-stock-deep-dive/",
            },
        },
    )
    direct = _article(
        symbol="TSLA",
        headline="Tesla rolls out robotaxis in Dallas and Houston",
        source="Reuters",
        summary="Tesla said on Saturday it is rolling out robotaxis in Dallas and Houston.",
        raw={
            "vendor": "finnhub",
            "vendor_payload": {
                "related": "TSLA",
                "headline": "Tesla rolls out robotaxis in Dallas and Houston",
                "url": "https://example.com/tesla-robotaxi",
            },
            "url": "https://example.com/tesla-robotaxi",
        },
    )

    filtered = filter_symbol_relevant_articles("TSLA", [incidental, direct])

    assert [article.headline for article in filtered] == [direct.headline]


def test_filter_symbol_relevant_articles_keeps_alias_mentions_after_learning_symbol_alias() -> None:
    direct = _article(
        symbol="TSLA",
        headline="Tesla rolls out robotaxis in Dallas and Houston",
        source="Yahoo",
        summary="Tesla is opening robotaxi service in Texas.",
        raw={
            "vendor": "finnhub",
            "vendor_payload": {
                "related": "TSLA",
                "headline": "Tesla rolls out robotaxis in Dallas and Houston",
            },
        },
    )
    alias_only = _article(
        symbol="TSLA",
        headline="How Will Dow Jones Futures, Oil Prices React As Iran, Hormuz News Turns?",
        source="Investor's Business Daily",
        summary="How will markets react as Iran news turns? Tesla earnings loom.",
        raw={
            "vendor": "yfinance",
            "url": "https://www.investors.com/market-trend/stock-market-today/dow-jones-futures-oil-prices-strait-of-hormuz-tesla-earnings/",
        },
    )

    filtered = filter_symbol_relevant_articles("TSLA", [direct, alias_only])

    assert [article.headline for article in filtered] == [direct.headline, alias_only.headline]


def test_filter_symbol_relevant_articles_keeps_explicit_ticker_mentions_without_vendor_metadata() -> None:
    explicit_ticker = _article(
        symbol="TSLA",
        headline="Tesla (TSLA) gains after robotaxi update",
        source="Reuters",
        summary="Tesla shares rose after the company shared a robotaxi update.",
        raw={
            "vendor": "polygon",
            "url": "https://example.com/stocks/tsla-robotaxi-update",
        },
    )

    filtered = filter_symbol_relevant_articles("TSLA", [explicit_ticker])

    assert [article.headline for article in filtered] == [explicit_ticker.headline]
