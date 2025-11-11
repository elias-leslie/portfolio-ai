"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, ArrowUpDown, Newspaper } from "lucide-react";
import {
  formatSentimentScore,
  getSentimentBadgeVariant,
  formatNewsDate,
  formatVendorLabel,
  formatConfidence,
} from "@/lib/utils/news-formatting";

type SortOption = "recent" | "positive" | "negative";

// Common types
interface KeyEvent {
  icon: string;
  text: string;
  time_ago: string;
  is_material: boolean;
  event_category?: string | null;
  published_at?: string | null;
}

interface NewsArticle {
  ticker?: string;
  headline: string;
  url?: string | null;
  source?: string | null;
  vendor?: string | null;
  published_at?: string | null;
  sentiment_score?: number;
  sentiment_label?: string;
  sentiment?: {
    score: number;
    label: string;
  };
  plain_language_headline?: string | null;
  impact_summary?: string | null;
  actionable_insight?: string | null;
  content_hash?: string;
}

// Data structure types
interface TickerNewsIntelligence {
  headline: string;
  sentiment_score: number;
  sentiment_label: string;
  article_count_24h: number;
  key_events: KeyEvent[];
  recent_articles: NewsArticle[];
}

interface MarketNewsData {
  articles: NewsArticle[];
}

interface NewsSentimentDetail {
  score: number | null;
  score_change: number | null;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  article_count: number;
  latest_published_at?: string | null;
  model_breakdown: Record<string, number>;
}

interface RecentNewsPayload {
  summary?: NewsSentimentDetail;
  articles: NewsArticle[];
}

// Unified props interface
interface UnifiedNewsIntelligenceCardProps {
  // Context: If ticker provided, shows ticker-specific sections (header, scores)
  ticker?: string | null;

  // Data: One of these three structures
  newsIntelligence?: TickerNewsIntelligence | null;
  marketNewsData?: MarketNewsData | null;
  recentNews?: RecentNewsPayload | null;

  // Display options
  showHeader?: boolean;  // Show headline summary section (ticker-specific)
  showSentimentBreakdown?: boolean;  // Show sentiment counts and model coverage
  newsHidden?: boolean;  // Legacy from watchlist - hide entire card

  // Title customization
  title?: string;  // Default: "Market News" or "News Intelligence" or "News & Sentiment"
}

/**
 * Unified News Intelligence Card
 *
 * Supports two modes:
 * 1. Market News (dashboard): ticker=null, marketNewsData provided
 *    - Shows: Articles list, sorting, Show All, AI insights
 *    - Hides: Headline summary, key events, sentiment breakdown
 *
 * 2. Ticker News (watchlist): ticker="NVDA", newsIntelligence OR recentNews provided
 *    - Shows: All sections including headline summary, key events (if available), sentiment breakdown
 *    - Conditional: Header and scores based on props
 *
 * 3. Ticker Recent News (watchlist simple): ticker="NVDA", recentNews provided
 *    - Shows: Sentiment breakdown, articles with Show All
 *    - No key events (simpler data structure)
 *
 * @param ticker - If provided, enables ticker-specific sections
 * @param newsIntelligence - Ticker-specific news data structure (rich with key events)
 * @param marketNewsData - Market-wide news data structure
 * @param recentNews - Watchlist recent news structure (simpler, no key events)
 * @param showHeader - Show headline summary section (default: true for ticker, false for market)
 * @param showSentimentBreakdown - Show sentiment counts and model coverage (default: true for recentNews)
 * @param newsHidden - Hide the entire card (legacy from watchlist)
 * @param title - Custom title (default: context-based)
 */
export function UnifiedNewsIntelligenceCard({
  ticker,
  newsIntelligence,
  marketNewsData,
  recentNews,
  showHeader = !!ticker,
  showSentimentBreakdown = true,  // Always show sentiment breakdown when available
  newsHidden = false,
  title,
}: UnifiedNewsIntelligenceCardProps) {
  const [showAll, setShowAll] = useState(false);
  const [sortBy, setSortBy] = useState<SortOption>("recent");

  // Normalize articles and summary from any data structure (MUST be before early returns)
  const articles = useMemo(() => {
    if (newsIntelligence) {
      return newsIntelligence.recent_articles || [];
    }
    if (marketNewsData) {
      return marketNewsData.articles || [];
    }
    if (recentNews) {
      return recentNews.articles || [];
    }
    return [];
  }, [newsIntelligence, marketNewsData, recentNews]);

  // Normalize summary from any data structure
  const summary = useMemo(() => {
    if (newsIntelligence?.summary) {
      return newsIntelligence.summary;
    }
    if (marketNewsData?.summary) {
      return marketNewsData.summary;
    }
    if (recentNews?.summary) {
      return recentNews.summary;
    }
    return null;
  }, [newsIntelligence, marketNewsData, recentNews]);

  // Sort articles based on selected option
  const sortedArticles = useMemo(() => {
    const sorted = [...articles];
    if (sortBy === "positive") {
      return sorted.sort((a, b) => {
        const scoreA = a.sentiment_score ?? a.sentiment?.score ?? 0;
        const scoreB = b.sentiment_score ?? b.sentiment?.score ?? 0;
        return scoreB - scoreA;
      });
    } else if (sortBy === "negative") {
      return sorted.sort((a, b) => {
        const scoreA = a.sentiment_score ?? a.sentiment?.score ?? 0;
        const scoreB = b.sentiment_score ?? b.sentiment?.score ?? 0;
        return scoreA - scoreB;
      });
    }
    // "recent" - keep original order (already sorted by published_at from backend)
    return sorted;
  }, [articles, sortBy]);

  // Balanced view: Top 3 positive + top 3 negative (6 total)
  const balancedArticles = useMemo(() => {
    if (sortBy !== "recent") {
      // User manually selected sorting, use that
      return sortedArticles;
    }

    // Default balanced view: show extremes
    const withScores = articles.map(a => ({
      article: a,
      score: a.sentiment_score ?? a.sentiment?.score ?? 0
    }));

    // Sort by score to find extremes
    const byScore = [...withScores].sort((a, b) => b.score - a.score);

    const positive = byScore.filter(x => x.score > 0).slice(0, 3);
    const negative = byScore.filter(x => x.score < 0).slice(-3).reverse(); // Most negative first

    // Positive first, then negative
    return [...positive, ...negative].map(x => x.article);
  }, [articles, sortedArticles, sortBy]);

  const displayCount = showAll ? sortedArticles.length : 6;
  const displayedArticles = showAll ? sortedArticles : balancedArticles.slice(0, displayCount);
  const hasMore = sortedArticles.length > 6;

  // Determine title
  const cardTitle = title || (ticker ? "📰 News Intelligence" : "Market News");

  // Determine if we should show gradient styling (market news) or standard (ticker news)
  const isMarketNews = !ticker;

  // Early returns AFTER all hooks
  if (newsHidden) return null;
  if (!newsIntelligence && !marketNewsData && !recentNews) return null;

  return (
    <Card className={isMarketNews ? "p-6 shadow-lg" : "border-border"}>
      <CardHeader className={isMarketNews ? "p-0 pb-4" : "pb-3 flex flex-row items-center justify-between space-y-0"}>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            {isMarketNews && <Newspaper className="h-5 w-5 text-accent" />}
            <CardTitle className={isMarketNews
              ? "text-lg font-semibold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent"
              : "text-base"}>
              {cardTitle}
            </CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <ArrowUpDown className="h-3 w-3 text-text-muted" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="text-xs border border-border rounded px-2 py-1 bg-surface text-text focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="recent">Recent</option>
              <option value="positive">Most Positive</option>
              <option value="negative">Most Negative</option>
            </select>
          </div>
        </div>
      </CardHeader>

      <CardContent className={isMarketNews ? "p-0" : "space-y-4"}>
        {/* Headline Summary (ticker-specific only, when showHeader=true) */}
        {ticker && showHeader && newsIntelligence && (
          <div>
            <h4 className="text-sm font-semibold text-text mb-2">
              {newsIntelligence.headline}
            </h4>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div>
                <span className="text-text-muted">Sentiment: </span>
                <Badge variant={getSentimentBadgeVariant(newsIntelligence.sentiment_label)}>
                  {newsIntelligence.sentiment_label}{" "}
                  ({formatSentimentScore(newsIntelligence.sentiment_score)})
                </Badge>
              </div>
              <div className="text-text-muted">
                {newsIntelligence.article_count_24h} articles in 24h
              </div>
            </div>
          </div>
        )}

        {/* Key Events (ticker-specific only) */}
        {ticker && newsIntelligence && newsIntelligence.key_events && newsIntelligence.key_events.length > 0 && (
          <div>
            <h5 className="text-xs font-semibold text-text mb-2">Key Events:</h5>
            <div className="space-y-2">
              {newsIntelligence.key_events.map((event, idx) => (
                <div
                  key={`event-${idx}-${event.text.substring(0, 20)}`}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className="text-base flex-shrink-0">{event.icon}</span>
                  <div className="flex-1">
                    <span className="text-text">{event.text}</span>
                    <span className="text-text-muted ml-2">({event.time_ago})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sentiment Breakdown (all sections) */}
        {showSentimentBreakdown && summary && (
          <div className="flex flex-wrap items-start justify-between gap-4 pb-3 border-b border-border">
            <div>
              <p className="text-xs uppercase tracking-wide text-text-muted">Sentiment Score</p>
              <div className="mt-1 flex items-center gap-2">
                <Badge variant={getSentimentBadgeVariant(summary.score)}>
                  {formatSentimentScore(summary.score)}
                </Badge>
                {summary.score_change !== null && summary.score_change !== undefined && (
                  <span
                    className={`inline-flex items-center text-xs font-medium ${
                      summary.score_change >= 0 ? "text-gain" : "text-loss"
                    }`}
                  >
                    {summary.score_change >= 0 ? "▲" : "▼"}
                    {Math.abs(summary.score_change).toFixed(2)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-6 text-xs text-text-muted">
              <div>
                <p className="font-semibold text-text">Headline Mix</p>
                <p>
                  Positive: <span className="font-medium text-gain">{summary.positive_count}</span>
                </p>
                <p>
                  Neutral: <span className="font-medium text-text">{summary.neutral_count}</span>
                </p>
                <p>
                  Negative: <span className="font-medium text-loss">{summary.negative_count}</span>
                </p>
              </div>
              <div>
                <p className="font-semibold text-text">Model Coverage</p>
                {(() => {
                  const totalCoverage = Object.values(summary.model_breakdown || {}).reduce(
                    (sum, val) => sum + val,
                    0
                  );
                  const finbertCoverage = summary.model_breakdown?.finbert ?? 0;
                  const fallbackCoverage = Math.max(totalCoverage - finbertCoverage, 0);

                  if (totalCoverage === 0) {
                    return <p>No articles scored</p>;
                  }
                  if (finbertCoverage === totalCoverage) {
                    return <p>FinBERT coverage</p>;
                  }
                  if (finbertCoverage === 0) {
                    return <p>Fallback sentiment (VADER)</p>;
                  }
                  return (
                    <>
                      <p>FinBERT {finbertCoverage}/{totalCoverage}</p>
                      {fallbackCoverage > 0 && (
                        <p className="text-xs text-text-muted">
                          {fallbackCoverage} fallback
                        </p>
                      )}
                    </>
                  );
                })()}
              </div>
            </div>
          </div>
        )}

        {/* Recent Articles (always shown) */}
        {articles.length === 0 ? (
          <div className="text-sm text-text-muted py-4">
            {ticker ? "No recent articles available" : "No recent market news available"}
          </div>
        ) : (
          <>
            {!showAll && sortBy === "recent" && (
              <p className="text-xs text-text-muted mb-3">
                Showing top 3 positive + top 3 negative articles ({displayedArticles.length} of {sortedArticles.length})
              </p>
            )}
            {!showAll && sortBy !== "recent" && (
              <p className="text-xs text-text-muted mb-3">
                Showing {displayedArticles.length} of {sortedArticles.length} articles
              </p>
            )}
            <div className="space-y-2">
              {displayedArticles.map((article, idx) => {
                // Normalize article data from either structure
                const sentimentScore = article.sentiment_score ?? article.sentiment?.score;
                const sentimentLabel = article.sentiment_label ?? article.sentiment?.label;
                const sentimentConfidence = article.sentiment?.confidence;
                const sentimentModel = article.sentiment?.model;

                const timeAgo = formatNewsDate(article.published_at);
                const source = article.source && article.source.trim().length > 0
                  ? article.source.trim()
                  : formatVendorLabel(article.vendor);

                const impactSummary = article.impact_summary;
                const actionableInsight = article.actionable_insight;

                // ALWAYS use original headline (plain_language_headline is disabled due to broken transformation)
                const displayHeadline = article.headline;

                // Generate unique key
                const articleKey = article.content_hash || article.url || `article-${idx}-${article.headline.substring(0, 30)}`;

                // Watchlist-style detailed layout (when recentNews provided)
                // Unified detailed layout for all news (market and ticker)
                  return (
                    <div
                      key={articleKey}
                      className="rounded-md border border-border bg-surface-muted/30 p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex-1 space-y-1">
                          {article.url ? (
                            <a
                              href={article.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
                            >
                              {displayHeadline}
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : (
                            <p className="text-sm font-semibold text-text">
                              {displayHeadline}
                            </p>
                          )}
                          <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
                            {article.vendor && (
                              <Badge
                                variant="outline"
                                className="text-[10px] font-semibold uppercase tracking-wide"
                              >
                                {formatVendorLabel(article.vendor)}
                              </Badge>
                            )}
                            {source && (
                              <span className="text-text">
                                Publisher: {source}
                              </span>
                            )}
                            {timeAgo && <span>{timeAgo}</span>}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-2 text-xs">
                          {sentimentLabel && (
                            <Badge variant={getSentimentBadgeVariant(sentimentLabel)}>
                              {sentimentLabel.toUpperCase()}
                            </Badge>
                          )}
                          {sentimentScore !== undefined && sentimentScore !== null && (
                            <span className="text-text font-semibold">
                              {formatSentimentScore(sentimentScore)}
                            </span>
                          )}
                          {sentimentConfidence !== undefined && sentimentConfidence !== null && (
                            <span className="text-text-muted">
                              Confidence {formatConfidence(sentimentConfidence)}
                            </span>
                          )}
                          {sentimentModel && (
                            <Badge variant={sentimentModel === "finbert" ? "secondary" : "loss"}>
                              {sentimentModel.toUpperCase()}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  );

              })}
            </div>

            {/* Show All button */}
            {hasMore && (
              <div className="mt-3 flex justify-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAll(!showAll)}
                  className="text-xs"
                >
                  {showAll ? "Show Less" : `Show All (${sortedArticles.length} total)`}
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
