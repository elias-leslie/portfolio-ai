from __future__ import annotations

from datetime import UTC, datetime

from app.services.story_clusterer import NewsArticle, StoryClusterer


def _article(
    article_id: str,
    *,
    headline: str,
    summary: str,
    vendor: str,
    minute: int,
) -> NewsArticle:
    return NewsArticle(
        id=article_id,
        symbol="MARKET",
        headline=headline,
        summary=summary,
        vendor=vendor,
        published_at=datetime(2026, 4, 11, 14, minute, tzinfo=UTC),
        sentiment_score=0.0,
        is_material_event=False,
        filing_type=None,
    )


def test_cluster_articles_groups_syndicated_market_story_under_one_primary() -> None:
    clusterer = StoryClusterer()
    summary = (
        "Jerome Powell said the Federal Reserve can stay patient before cutting rates "
        "while inflation remains elevated and Treasury yields stay volatile."
    )
    articles = [
        _article(
            "primary",
            headline="Powell says the Fed can wait longer before cutting rates",
            summary=summary,
            vendor="Reuters",
            minute=0,
        ),
        _article(
            "follow_up",
            headline="Powell says the Fed can wait longer before cutting rates - Seeking Alpha",
            summary=summary,
            vendor="Seeking Alpha",
            minute=12,
        ),
    ]

    stories = clusterer.cluster_articles(articles)

    assert len(stories) == 1
    story = stories[0]
    assert story.coverage_count == 2
    assert story.primary_article_id == "primary"

    metadata = clusterer.update_article_clustering_metadata(stories)
    assert metadata["primary"]["is_primary_article"] is True
    assert metadata["follow_up"]["is_primary_article"] is False
    assert metadata["follow_up"]["coverage_count"] == 2


def test_cluster_articles_groups_matching_summaries_even_when_headlines_differ() -> None:
    clusterer = StoryClusterer()
    summary = (
        "Jerome Powell said the Federal Reserve can stay patient before cutting rates "
        "while inflation remains elevated and Treasury yields stay volatile."
    )
    articles = [
        _article(
            "marketwatch",
            headline="Powell says the Fed can wait longer before cutting rates",
            summary=summary,
            vendor="MarketWatch",
            minute=0,
        ),
        _article(
            "yahoo",
            headline="Federal Reserve can stay patient on rate cuts, Powell says",
            summary=summary,
            vendor="Yahoo Finance",
            minute=6,
        ),
    ]

    stories = clusterer.cluster_articles(articles)

    assert len(stories) == 1
    assert stories[0].coverage_count == 2


def test_cluster_articles_keeps_unrelated_market_stories_separate() -> None:
    clusterer = StoryClusterer()
    articles = [
        _article(
            "oil",
            headline="Oil climbs after Gulf shipping risk rises",
            summary="Crude prices rose after shipping risk in the Gulf increased and traders repriced supply disruption odds.",
            vendor="Reuters",
            minute=0,
        ),
        _article(
            "inflation",
            headline="Core CPI slows as shelter inflation cools",
            summary="Core CPI eased as shelter inflation cooled, supporting expectations for slower price growth in coming months.",
            vendor="Bloomberg",
            minute=15,
        ),
    ]

    stories = clusterer.cluster_articles(articles)

    assert len(stories) == 2
    assert all(story.coverage_count == 1 for story in stories)
