"""Story clustering utilities for market and symbol news."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .news_decision_support import canonical_headline, source_signal_tier

_MAX_STORY_GAP = timedelta(hours=72)
_HEADLINE_SIMILARITY_THRESHOLD = 0.84
_TEXT_SIMILARITY_THRESHOLD = 0.74


@dataclass(frozen=True)
class NewsArticle:
    """Minimal article shape for clustering."""

    id: str
    symbol: str
    headline: str
    summary: str | None
    vendor: str
    published_at: datetime
    sentiment_score: float | None
    is_material_event: bool
    filing_type: str | None


@dataclass(frozen=True)
class StoryCluster:
    """Clustered news story metadata."""

    story_id: str
    article_ids: tuple[str, ...]
    primary_article_id: str
    coverage_count: int


class StoryClusterMetadata(TypedDict):
    """Per-article clustering metadata for cached news records."""

    story_id: str
    is_primary_article: bool
    coverage_count: int


class _UnionFind:
    """Minimal union-find for pairwise clustering."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\u2019", "'").replace("\u2018", "'")).strip()


def _headline_key(article: NewsArticle) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", canonical_headline(article.headline).lower()).strip()


def _summary_key(article: NewsArticle) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", _clean_text(article.summary).lower()).strip()


def _build_text(article: NewsArticle) -> str:
    headline = canonical_headline(article.headline)
    summary = _clean_text(article.summary)
    return " ".join(part for part in (headline, summary) if part).strip()


def _published_at(article: NewsArticle) -> datetime:
    published_at = article.published_at
    return published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)


def _source_rank(source: str) -> int:
    tier = source_signal_tier(source)
    if tier == "primary":
        return 3
    if tier == "secondary":
        return 2
    if tier == "commentary":
        return 0
    return 1


def _primary_sort_key(article: NewsArticle) -> tuple[int, int, int, datetime]:
    return (
        _source_rank(article.vendor),
        int(article.is_material_event),
        len(_clean_text(article.summary)),
        _published_at(article),
    )


class StoryClusterer:
    """Cluster related stories using canonical headlines plus TF-IDF similarity."""

    def cluster_articles(
        self,
        articles: list[NewsArticle],
        *,
        min_coverage_for_story: int = 1,
    ) -> list[StoryCluster]:
        if not articles:
            return []

        clusters: list[StoryCluster] = []
        for symbol_articles in self._group_by_symbol(articles).values():
            clusters.extend(
                self._cluster_symbol_articles(
                    symbol_articles, min_coverage_for_story=min_coverage_for_story
                )
            )
        return clusters

    def update_article_clustering_metadata(
        self,
        stories: list[StoryCluster],
    ) -> dict[str, StoryClusterMetadata]:
        metadata: dict[str, StoryClusterMetadata] = {}
        for story in stories:
            for article_id in story.article_ids:
                metadata[article_id] = {
                    "story_id": story.story_id,
                    "is_primary_article": article_id == story.primary_article_id,
                    "coverage_count": story.coverage_count,
                }
        return metadata

    def _group_by_symbol(self, articles: list[NewsArticle]) -> dict[str, list[NewsArticle]]:
        grouped: dict[str, list[NewsArticle]] = defaultdict(list)
        for article in articles:
            grouped[article.symbol].append(article)
        return grouped

    def _cluster_symbol_articles(
        self,
        articles: list[NewsArticle],
        *,
        min_coverage_for_story: int,
    ) -> list[StoryCluster]:
        if len(articles) == 1:
            article = articles[0]
            return [
                StoryCluster(
                    story_id=self._story_id((article,)),
                    article_ids=(article.id,),
                    primary_article_id=article.id,
                    coverage_count=1,
                )
            ]

        union_find = _UnionFind(len(articles))
        headline_keys = [_headline_key(article) for article in articles]
        summary_keys = [_summary_key(article) for article in articles]
        text_values = [_build_text(article) for article in articles]
        headline_similarity = self._cosine_matrix(headline_keys)
        text_similarity = self._cosine_matrix(text_values)

        for left in range(len(articles)):
            for right in range(left + 1, len(articles)):
                if not self._within_story_window(articles[left], articles[right]):
                    continue
                if headline_keys[left] and headline_keys[left] == headline_keys[right]:
                    union_find.union(left, right)
                    continue
                if (
                    summary_keys[left]
                    and summary_keys[left] == summary_keys[right]
                    and len(summary_keys[left]) >= 80
                ):
                    union_find.union(left, right)
                    continue
                if headline_similarity[left, right] >= _HEADLINE_SIMILARITY_THRESHOLD:
                    union_find.union(left, right)
                    continue
                if text_similarity[left, right] >= _TEXT_SIMILARITY_THRESHOLD:
                    union_find.union(left, right)

        grouped_indexes: dict[int, list[int]] = defaultdict(list)
        for index in range(len(articles)):
            grouped_indexes[union_find.find(index)].append(index)

        stories: list[StoryCluster] = []
        for member_indexes in grouped_indexes.values():
            member_articles = tuple(articles[index] for index in sorted(member_indexes))
            if len(member_articles) < min_coverage_for_story:
                for article in member_articles:
                    stories.append(
                        StoryCluster(
                            story_id=self._story_id((article,)),
                            article_ids=(article.id,),
                            primary_article_id=article.id,
                            coverage_count=1,
                        )
                    )
                continue

            primary_article = max(member_articles, key=_primary_sort_key)
            stories.append(
                StoryCluster(
                    story_id=self._story_id(member_articles),
                    article_ids=tuple(article.id for article in member_articles),
                    primary_article_id=primary_article.id,
                    coverage_count=len(member_articles),
                )
            )

        return stories

    def _within_story_window(self, left: NewsArticle, right: NewsArticle) -> bool:
        return abs(_published_at(left) - _published_at(right)) <= _MAX_STORY_GAP

    def _cosine_matrix(self, texts: list[str]) -> np.ndarray:
        cleaned = [text if text else "__empty__" for text in texts]
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(cleaned)
        return cosine_similarity(matrix)

    def _story_id(self, articles: tuple[NewsArticle, ...]) -> str:
        seed = "||".join(sorted(_headline_key(article) or article.id for article in articles))
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
        return f"story_{digest}"
