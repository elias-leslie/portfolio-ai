"""Select only news with an explicit subject or named business connection."""

from __future__ import annotations

from collections.abc import Sequence

from .news_entities import identify_news_relationship
from .news_models import NewsArticle


def filter_symbol_relevant_articles(
    symbol: str, articles: Sequence[NewsArticle], *, company_name: str | None = None
) -> list[NewsArticle]:
    selected = []
    for article in articles:
        relationship = identify_news_relationship(
            symbol, article.headline, article.summary, company_name
        )
        if relationship.kind == "unverified":
            continue
        selected.append(
            article.model_copy(
                update={
                    "company_name": company_name,
                    "relationship": relationship.kind,
                    "relationship_reason": relationship.reason,
                }
            )
        )
    return selected
