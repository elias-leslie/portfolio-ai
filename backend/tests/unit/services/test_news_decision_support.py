"""Unit tests for structured news decision support."""

from __future__ import annotations

from types import SimpleNamespace

from app.constants import MARKET_SYMBOL
from app.services.news_decision_support import (
    assess_news_article,
    canonical_headline,
    market_context_topic,
    source_signal_tier,
)


def test_canonical_headline_strips_syndication_suffix() -> None:
    assert (
        canonical_headline(
            "Software stocks are plunging. Why that's a warning sign for the entire market - Yahoo Finance"
        )
        == "Software stocks are plunging. Why that's a warning sign for the entire market"
    )


def test_assess_news_article_flags_market_context_and_primary_source() -> None:
    article = SimpleNamespace(
        symbol=MARKET_SYMBOL,
        headline="Dow Jones Futures: U.S.-Iran Direct Talks Yet To Start; Google, Amazon, Nvidia In Buy Areas",
        summary=(
            "After big stock market gains, Iran talks and upcoming earnings are in focus. "
            "Google, Amazon and Nvidia are in buy areas."
        ),
        source="Investor's Business Daily",
        actionable_insight="News reported - read the details before acting",
        impact_summary="News reported - assess impact based on your strategy",
        quality_prediction=True,
        quality_confidence=0.66,
        is_material_event=False,
        story_id=None,
        is_primary_article=False,
        coverage_count=1,
        filing_type=None,
    )

    assessment = assess_news_article(article)

    assert assessment.market_context_topic in {"Geopolitics", "Risk", "Sector Leadership"}
    assert assessment.source_signal_tier == "primary"
    assert assessment.decision_value_score >= 0.55
    assert assessment.decision_value_label in {"medium", "high"}


def test_assess_news_article_rejects_personal_advice_story() -> None:
    article = SimpleNamespace(
        symbol=MARKET_SYMBOL,
        headline=(
            "I'm 71 and have $6 million after scrimping and saving. "
            "My son wants money for a house. Do I say yes?"
        ),
        summary=(
            "A personal-finance advice column about whether to help an adult child "
            "buy a house."
        ),
        source="MarketWatch",
        actionable_insight="Positive sentiment - worth investigating",
        impact_summary="Very positive news - may create short-term momentum",
        quality_prediction=True,
        quality_confidence=0.64,
        is_material_event=False,
        story_id=None,
        is_primary_article=False,
        coverage_count=1,
        filing_type=None,
    )

    assessment = assess_news_article(article)

    assert assessment.market_context_topic is None
    assert assessment.decision_value_label == "low"
    assert assessment.decision_value_score < 0.55
    assert assessment.decision_value_reason == "Not a portfolio decision signal."


def test_source_signal_tier_and_market_topic_helpers() -> None:
    assert source_signal_tier("Reuters") == "primary"
    assert source_signal_tier("Seeking Alpha") == "commentary"
    assert market_context_topic(
        "Fed minutes reinforce higher-for-longer rate outlook",
        "Treasury yields rose after the latest policy commentary.",
    ) == "Rates"
