"""Unit tests for symbol intelligence response builders."""

from __future__ import annotations

import math

from app.api.symbols.builders import build_market_section, build_news_section_from_watchlist


def test_build_market_section_drops_nan_sp500_change() -> None:
    section = build_market_section(
        {
            "fear_greed": {"score": 28, "label": "Fear"},
            "vix": 25.78,
            "sp500_change": math.nan,
        }
    )

    assert section is not None
    assert section.fear_greed_score == 28
    assert section.fear_greed_label == "Fear"
    assert section.vix == 25.78
    assert section.sp500_change is None


def test_build_news_section_from_watchlist_uses_recent_news_fallback() -> None:
    section = build_news_section_from_watchlist(
        {
            "news_intelligence": {"article_count_24h": 200},
            "recent_news": {
                "summary": {"article_count": 2},
                "articles": [
                    {
                        "headline": "NVIDIA supplier demand stays elevated",
                        "source": "Reuters",
                        "published_at": "2026-03-10T14:00:00Z",
                    }
                ],
            },
        }
    )

    assert section is not None
    assert section.article_count_24h == 200
    assert section.headline == "NVIDIA supplier demand stays elevated"
    assert len(section.recent_articles) == 1
    assert section.recent_articles[0].source == "Reuters"
