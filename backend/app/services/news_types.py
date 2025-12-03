"""TypedDict definitions for news service layer.

This module centralizes all dictionary structure definitions used across
the news processing pipeline. Following the pattern from resource_monitor.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class VendorRuntimeDict(TypedDict, total=False):
    """Runtime tracking for news vendor sources."""

    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
    articles_last_fetch: int
    articles_last_fetch_post: int


class FallbackMetricsDict(TypedDict, total=False):
    """Sentiment analyzer fallback metrics for health reporting."""

    fallback_count: int
    total_count: int
    fallback_rate: float
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    last_fallback_at: datetime | None


class ArticleMixMetricsDict(TypedDict, total=False):
    """Pre/post deduplication article counts by vendor."""

    total_pre: int
    total_post: int
    vendor_pre: dict[str, int]
    vendor_post: dict[str, int]
    last_timestamp: datetime | None


class VendorStatsDict(TypedDict):
    """Per-vendor statistics from last 24 hours."""

    articles_last_24h: int
    last_article_at: datetime


class VendorHealthStatusDict(TypedDict, total=False):
    """Vendor health status with config and runtime info."""

    configured: bool
    enabled: bool
    active: bool
    last_attempt_at: str | None
    last_success_at: str | None
    last_error_at: str | None
    last_error: str | None
    articles_last_fetch: int
    articles_last_fetch_post_dedupe: int
    articles_last_24h: int
    last_article_at: str | None
    notes: str | None
    reason: str | None


class NormalizedArticleEntryDict(TypedDict, total=False):
    """Standard article entry after vendor normalization."""

    headline: str
    summary: str | None
    description: str | None
    url: str | None
    link: str | None
    source: str
    news_source_name: str
    author: str | None
    image_url: str | None
    published: str | None
    published_at: str | None
    vendor: str
    ticker: str
    vendor_payload: dict[str, object] | None


class VendorFetchMetadataDict(TypedDict):
    """Metadata from vendor fetch operation."""

    counts: dict[str, int]
    errors: dict[str, list[str] | str]


class TickerMixSummaryDict(TypedDict):
    """Article mix statistics for a ticker."""

    timestamp: datetime
    total_pre: int
    total_post: int
    per_vendor_pre: dict[str, int]
    per_vendor_post: dict[str, int]


class FallbackDetailsDict(TypedDict, total=False):
    """Fallback sentiment analyzer error details."""

    reason: str  # "unavailable" | "error"
    latency_ms: float
    error: str | None
    rate: float | None
    article_count: int | None


class PlainLanguageTranslationDict(TypedDict, total=False):
    """Plain language translation of financial news."""

    plain_language_headline: str | None
    event_category: str
    actionable_insight: str
    impact_summary: str


class ArticleDbRowDict(TypedDict, total=False):
    """Database insert row for news articles."""

    symbol: str
    headline: str
    url: str | None
    summary: str | None
    news_source_name: str | None
    author: str | None
    image_url: str | None
    published_at: datetime | None
    sentiment_score: float
    sentiment_label: str
    sentiment_confidence: float
    sentiment_model: str
    raw_payload: str
    content_hash: str
    fetched_at: datetime
    created_at: datetime
    updated_at: datetime
    filing_type: str | None
    is_material_event: bool
    plain_language_headline: str | None
    story_id: str | None
    is_primary_article: bool
    coverage_count: int
    impact_summary: str | None
    actionable_insight: str | None
    quality_prediction: str | None
    quality_confidence: float | None


class NewsHealthReportDict(TypedDict, total=False):
    """News service health check response."""

    finbert_available: bool
    cache_ttl_minutes: int
    fallback_metrics: FallbackMetricsDict
    article_mix_metrics: ArticleMixMetricsDict
    vendor_health: dict[str, VendorHealthStatusDict]
    last_refresh_at: str | None
