"""Apply entity checks to old embedded headlines without rewriting cached evidence."""

from __future__ import annotations

from typing import Any

from .news_entities import identify_news_relationship


def filter_cached_news(
    symbol: str, payload: dict[str, Any] | None, company_name: str | None = None
) -> dict[str, Any] | None:
    if not payload:
        return payload
    key = "recent_articles" if "recent_articles" in payload else "articles"
    articles = payload.get(key) or []
    selected = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        relation = identify_news_relationship(
            symbol, str(article.get("headline") or ""), article.get("summary"), company_name
        )
        if relation.kind == "unverified":
            continue
        selected.append(
            {
                **article,
                "relationship": relation.kind,
                "relationship_reason": relation.reason,
                "decision_value_reason": relation.reason,
            }
        )
    result = {**payload, key: selected}
    if key == "recent_articles":
        # Generated events/headlines can refer to rejected source articles.
        result["key_events"] = [
            event
            for event in payload.get("key_events", [])
            if isinstance(event, dict)
            and identify_news_relationship(
                symbol, str(event.get("text") or ""), company_name=company_name
            ).kind
            != "unverified"
        ]
        result["headline"] = (
            selected[0]["headline"] if selected else "No relevant company news in this saved batch."
        )
    if len(selected) != len(articles) or not articles:
        result.pop("sentiment_score", None)
        result.pop("sentiment_label", None)
        result["article_count_24h"] = len(selected)
        if isinstance(payload.get("summary"), dict):
            result["summary"] = {
                **payload["summary"],
                "score": None,
                "score_change": None,
                "article_count": len(selected),
                "top_positive": None,
                "top_negative": None,
                "positive_count": 0,
                "neutral_count": 0,
                "negative_count": 0,
                "model_breakdown": {},
                "evidence_note": "Sentiment withheld: source batch included unmatched stories.",
            }
    return result
