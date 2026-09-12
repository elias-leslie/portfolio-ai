"""Labeled selection cases from the review plus close positive/negative controls.

Observed titles are short excerpts; summaries below are synthetic test evidence.
"""

from datetime import UTC, datetime

import pytest

from app.constants import MARKET_SYMBOL
from app.services.news_cached_evidence import filter_cached_news
from app.services.news_decision_support import assess_news_article
from app.services.news_entities import identify_news_relationship
from app.services.news_models import NewsArticle, SentimentScore
from app.services.news_relevance import filter_symbol_relevant_articles

# symbol, headline, synthetic summary, expected relationship
CASES = [
    (
        "AAPL",
        "Should Qualcomm Stockholders Worry About Its Shrinking Revenue?",
        "Qualcomm revenue fell.",
        "unverified",
    ),
    (
        "MSFT",
        "Is UiPath Stock A Buy After Falling Despite A Raised Outlook?",
        "UiPath raised its outlook for automation software.",
        "unverified",
    ),
    (
        "ETN",
        "BigBear.ai Stock Dives 29% in the Past 3 Months: Hold or Fold?",
        "BigBear.ai supplies defense software.",
        "unverified",
    ),
    (
        MARKET_SYMBOL,
        "Should You Buy Rocket Companies Stock?",
        "Rocket Companies shares rose as the stock market rallied.",
        "unverified",
    ),
    (
        "AAPL",
        "Apple reduces reliance on Qualcomm in new iPhones",
        "Apple announced a new modem.",
        "direct",
    ),
    (
        "MSFT",
        "Microsoft raises cloud revenue outlook",
        "Microsoft expects higher revenue.",
        "direct",
    ),
    (
        "ETN",
        "Eaton reports stronger electrical equipment sales",
        "Eaton reported a new order backlog.",
        "direct",
    ),
    (
        "AAPL",
        "Qualcomm cuts its revenue outlook",
        "Qualcomm is a modem supplier to Apple; the new forecast cites lower orders from that customer.",
        "peer",
    ),
    (
        "MSFT",
        "UiPath expands automation distribution",
        "UiPath signed a distribution partnership with Microsoft.",
        "peer",
    ),
    (
        "AAPL",
        "Qualcomm cuts its revenue outlook",
        "Coverage list: AAPL, MSFT, ETN. Qualcomm expects fewer orders.",
        "unverified",
    ),
    (
        "AI",
        "AI powers a new wave of earnings growth",
        "Artificial intelligence improves factory operations.",
        "unverified",
    ),
    ("AI", "$AI lowers revenue guidance", "The company cut guidance.", "direct"),
    ("ON", "On the road to higher earnings", "The company raised its outlook.", "unverified"),
    ("F", "Ford (F) updates its production plan", "Ford reported new factory targets.", "direct"),
    (
        MARKET_SYMBOL,
        "Fed holds interest rates steady",
        "The policy decision affects borrowing costs across the economy.",
        "market",
    ),
    (
        MARKET_SYMBOL,
        "US jobs report shows payroll slowdown",
        "National employment growth slowed.",
        "market",
    ),
    (
        "AAPL",
        "Orchard output rises",
        "Appleton supplies fruit juice to grocery stores.",
        "unverified",
    ),
    ("TSLA", "Markets await policy update", "Tesla earnings are due this week.", "direct"),
]


@pytest.mark.parametrize("symbol,headline,summary,expected", CASES)
def test_labeled_relationship(symbol, headline, summary, expected):
    assert identify_news_relationship(symbol, headline, summary).kind == expected


def test_selected_precision_and_vendor_tags_cannot_promote_false_positives():
    true_selected = false_selected = missed = 0
    for symbol, headline, summary, expected in CASES:
        article = NewsArticle(
            symbol=symbol,
            headline=headline,
            summary=summary,
            source="Reuters",
            fetched_at=datetime.now(UTC),
            sentiment=SentimentScore(score=0.9, label="positive", confidence=0.99, model="finbert"),
            content_hash=headline,
            raw={"vendor_payload": {"related": symbol, "tickers": [symbol]}},
            quality_prediction=True,
            quality_confidence=0.99,
            is_material_event=True,
        )
        selected = filter_symbol_relevant_articles(symbol, [article])
        should_select = expected != "unverified"
        true_selected += bool(selected) and should_select
        false_selected += bool(selected) and not should_select
        missed += not selected and should_select
        if not should_select:
            assessment = assess_news_article(article)
            assert assessment.relationship == "unverified"
            assert assessment.decision_value_score <= 0.2
    assert true_selected == 10
    assert false_selected == 0
    assert missed == 0


def test_embedded_cache_filters_source_and_withholds_contaminated_aggregate():
    payload = {
        "summary": {"score": 0.8, "article_count": 2},
        "articles": [
            {"headline": CASES[0][1], "summary": CASES[0][2]},
            {
                "headline": "Apple raises earnings guidance",
                "summary": "Apple expects stronger sales.",
            },
        ],
    }
    clean = filter_cached_news("AAPL", payload, "Apple Inc.")
    assert clean
    assert len(clean["articles"]) == 1
    assert clean["articles"][0]["relationship"] == "direct"
    assert clean["summary"]["score"] is None
    assert len(payload["articles"]) == 2 and payload["summary"]["score"] == 0.8


def test_canonical_registry_name_is_supported_without_headline_learning():
    relationship = identify_news_relationship(
        "XYZ", "Example Devices announces new factory", company_name="Example Devices, Inc."
    )
    assert relationship.kind == "direct"
    unrelated = identify_news_relationship(
        "XYZ", "Other Business announces new factory", company_name="Example Devices, Inc."
    )
    assert unrelated.kind == "unverified"
