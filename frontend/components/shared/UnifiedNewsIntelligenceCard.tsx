"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, ArrowUpDown, Newspaper, ChevronDown } from "lucide-react";
import {
  formatSentimentScore,
  getSentimentBadgeVariant,
} from "@/lib/utils/news-formatting";
import { NewsArticleCard } from "./NewsArticleCard";

type SortOption = "recent" | "positive" | "negative";

// Common types
interface KeyEvent {
  icon: string;
  text: string;
  timeAgo: string;
  isMaterial: boolean;
  event_category?: string | null;
  published_at?: string | null;
}

interface NewsArticle {
  symbol?: string;
  headline: string;
  url?: string | null;
  source?: string | null;
  vendor?: string | null;
  publishedAt?: string | null;
  sentimentScore?: number;
  sentimentLabel?: string;
  sentiment?: {
    score: number;
    label: string;
    confidence?: number;
    model?: string;
  };
  impactSummary?: string | null;
  actionableInsight?: string | null;
  contentHash?: string;
  qualityPrediction?: boolean | null;
  qualityConfidence?: number | null;
  // Story clustering metadata
  storyId?: string | null;
  isPrimaryArticle?: boolean;
  coverageCount?: number;
}

// Data structure types
interface SymbolNewsIntelligence {
  headline: string;
  sentimentScore: number;
  sentimentLabel: string;
  articleCount24H: number;
  keyEvents: KeyEvent[];
  recentArticles: NewsArticle[];
  summary?: NewsSentimentDetail | null;
}

interface MarketNewsData {
  articles: NewsArticle[];
  summary?: NewsSentimentDetail | null;
}

interface NewsSentimentDetail {
  score: number | null;
  scoreChange: number | null;
  positiveCount: number;
  neutralCount: number;
  negativeCount: number;
  articleCount: number;
  latest_published_at?: string | null;
  modelBreakdown: Record<string, number>;
}

interface RecentNewsPayload {
  summary?: NewsSentimentDetail;
  articles: NewsArticle[];
}

// Unified props interface
interface UnifiedNewsIntelligenceCardProps {
  // Context: If symbol provided, shows symbol-specific sections (header, scores)
  symbol?: string | null;

  // Data: One of these three structures
  newsIntelligence?: SymbolNewsIntelligence | null;
  marketNewsData?: MarketNewsData | null;
  recentNews?: RecentNewsPayload | null;

  // Display options
  showHeader?: boolean;  // Show headline summary section (symbol-specific)
  showSentimentBreakdown?: boolean;  // Show sentiment counts and model coverage
  newsHidden?: boolean;  // Legacy from watchlist - hide entire card

  // Title customization
  title?: string;  // Default: "Market News" or "News Intelligence" or "News & Sentiment"

  // Callbacks/state
  onRequestExpanded?: () => void;
  isLoadingMore?: boolean;

  // Collapsibility
  defaultCollapsed?: boolean;  // Start collapsed (default: false)
}

/**
 * Unified News Intelligence Card
 *
 * Supports two modes:
 * 1. Market News (dashboard): symbol=null, marketNewsData provided
 *    - Shows: Articles list, sorting, Show All, AI insights
 *    - Hides: Headline summary, key events, sentiment breakdown
 *
 * 2. Symbol News (watchlist): symbol="NVDA", newsIntelligence OR recentNews provided
 *    - Shows: All sections including headline summary, key events (if available), sentiment breakdown
 *    - Conditional: Header and scores based on props
 *
 * 3. Symbol Recent News (watchlist simple): symbol="NVDA", recentNews provided
 *    - Shows: Sentiment breakdown, articles with Show All
 *    - No key events (simpler data structure)
 *
 * @param symbol - If provided, enables symbol-specific sections
 * @param newsIntelligence - Symbol-specific news data structure (rich with key events)
 * @param marketNewsData - Market-wide news data structure
 * @param recentNews - Watchlist recent news structure (simpler, no key events)
 * @param showHeader - Show headline summary section (default: true for symbol, false for market)
 * @param showSentimentBreakdown - Show sentiment counts and model coverage (default: true for recentNews)
 * @param newsHidden - Hide the entire card (legacy from watchlist)
 * @param title - Custom title (default: context-based)
 */
export function UnifiedNewsIntelligenceCard({
  symbol,
  newsIntelligence,
  marketNewsData,
  recentNews,
  showHeader = !!symbol,
  showSentimentBreakdown = true,  // Always show sentiment breakdown when available
  newsHidden = false,
  title,
  onRequestExpanded,
  isLoadingMore = false,
  defaultCollapsed = false,
}: UnifiedNewsIntelligenceCardProps) {
  const [showAll, setShowAll] = useState(false);
  const [sortBy, setSortBy] = useState<SortOption>("recent");
  const [isExpanded, setIsExpanded] = useState(!defaultCollapsed);

  // Normalize articles and summary from any data structure (MUST be before early returns)
  const articles = useMemo(() => {
    if (newsIntelligence) {
      return newsIntelligence.recentArticles || [];
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
        const scoreA = a.sentimentScore ?? a.sentiment?.score ?? 0;
        const scoreB = b.sentimentScore ?? b.sentiment?.score ?? 0;
        return scoreB - scoreA;
      });
    } else if (sortBy === "negative") {
      return sorted.sort((a, b) => {
        const scoreA = a.sentimentScore ?? a.sentiment?.score ?? 0;
        const scoreB = b.sentimentScore ?? b.sentiment?.score ?? 0;
        return scoreA - scoreB;
      });
    }
    // "recent" - keep original order (already sorted by publishedAt from backend)
    return sorted;
  }, [articles, sortBy]);

  // Balanced view: Top 3 positive + top 3 negative (up to 6 total)
  const { balancedArticles, positiveCount, negativeCount } = useMemo(() => {
    if (sortBy !== "recent") {
      // User manually selected sorting, use that
      return { balancedArticles: sortedArticles, positiveCount: 0, negativeCount: 0 };
    }

    // Default balanced view: show extremes
    const withScores = articles.map(a => ({
      article: a,
      score: a.sentimentScore ?? a.sentiment?.score ?? 0
    }));

    // Sort by score to find extremes
    const byScore = [...withScores].sort((a, b) => b.score - a.score);

    const positive = byScore.filter(x => x.score > 0).slice(0, 3);
    const negative = byScore.filter(x => x.score < 0).slice(-3).reverse(); // Most negative first

    // Positive first, then negative
    return {
      balancedArticles: [...positive, ...negative].map(x => x.article),
      positiveCount: positive.length,
      negativeCount: negative.length,
    };
  }, [articles, sortedArticles, sortBy]);

  const DEFAULT_DISPLAY_COUNT = 6;
  const displayCount = showAll ? sortedArticles.length : DEFAULT_DISPLAY_COUNT;
  const displayedArticles = showAll ? sortedArticles : balancedArticles.slice(0, displayCount);
  const showToggleButton =
    Boolean(onRequestExpanded) || sortedArticles.length > DEFAULT_DISPLAY_COUNT;

  // Determine title
  const cardTitle = title || (symbol ? "📰 News Intelligence" : "Market News");

  // Determine if we should show gradient styling (market news) or standard (symbol news)
  const isMarketNews = !symbol;

  const handleToggleShowAll = () => {
    if (!showAll) {
      onRequestExpanded?.();
      setShowAll(true);
      return;
    }
    setShowAll(false);
  };

  // Early returns AFTER all hooks
  if (newsHidden) return null;
  if (!newsIntelligence && !marketNewsData && !recentNews) return null;

  return (
    <Card className={isMarketNews ? "p-6 shadow-lg" : "border-border"}>
      <CardHeader className={isMarketNews ? "p-0 pb-4" : "pb-3 flex flex-row items-center justify-between space-y-0"}>
        <div className="flex items-center justify-between w-full">
          <button
            type="button"
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            onClick={() => setIsExpanded((prev) => !prev)}
          >
            {isMarketNews && <Newspaper className="h-5 w-5 text-accent" />}
            <CardTitle className={isMarketNews
              ? "text-lg font-semibold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent"
              : "text-base"}>
              {cardTitle}
            </CardTitle>
            <ChevronDown
              className={`h-4 w-4 text-text-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
            />
            {!isExpanded && summary && (
              <Badge variant="outline" className="ml-2 text-xs">
                {articles.length} articles
              </Badge>
            )}
          </button>
          {isExpanded && (
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
          )}
        </div>
      </CardHeader>

      {/* Sentiment Breakdown - ALWAYS VISIBLE when summary exists */}
      {showSentimentBreakdown && summary && (
        <div className={`flex flex-wrap items-start justify-between gap-4 px-6 py-3 ${isExpanded ? "border-b border-border" : ""}`}>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Sentiment Score</p>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={getSentimentBadgeVariant(summary.score)}>
                {formatSentimentScore(summary.score)}
              </Badge>
              {summary.scoreChange !== null && summary.scoreChange !== undefined && (
                <span
                  className={`inline-flex items-center text-xs font-medium ${
                    summary.scoreChange >= 0 ? "text-gain" : "text-loss"
                  }`}
                >
                  {summary.scoreChange >= 0 ? "▲" : "▼"}
                  {Math.abs(summary.scoreChange).toFixed(2)}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-xs text-text-muted">
            <div>
              <p className="font-semibold text-text">Headline Mix</p>
              <p>
                Positive: <span className="font-medium text-gain">{summary.positiveCount}</span>
              </p>
              <p>
                Neutral: <span className="font-medium text-text">{summary.neutralCount}</span>
              </p>
              <p>
                Negative: <span className="font-medium text-loss">{summary.negativeCount}</span>
              </p>
            </div>
            <div>
              <p className="font-semibold text-text">Model Coverage</p>
              {(() => {
                const totalCoverage = Object.values(summary.modelBreakdown || {}).reduce(
                  (sum, val) => sum + val,
                  0
                );
                const finbertCoverage = summary.modelBreakdown?.finbert ?? 0;
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

      {isExpanded && (
      <CardContent className={isMarketNews ? "p-0" : "space-y-4"}>
        {/* Headline Summary (symbol-specific only, when showHeader=true) */}
        {symbol && showHeader && newsIntelligence && (
          <div>
            <h4 className="text-sm font-semibold text-text mb-2">
              {newsIntelligence.headline}
            </h4>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div>
                <span className="text-text-muted">Sentiment: </span>
                <Badge variant={getSentimentBadgeVariant(newsIntelligence.sentimentLabel)}>
                  {newsIntelligence.sentimentLabel}{" "}
                  ({formatSentimentScore(newsIntelligence.sentimentScore)})
                </Badge>
              </div>
              <div className="text-text-muted">
                {newsIntelligence.articleCount24H} articles in 24h
              </div>
            </div>
          </div>
        )}

        {/* Key Events (symbol-specific only) */}
        {symbol && newsIntelligence && newsIntelligence.keyEvents && newsIntelligence.keyEvents.length > 0 && (
          <div>
            <h5 className="text-xs font-semibold text-text mb-2">Key Events:</h5>
            <div className="space-y-2">
              {newsIntelligence.keyEvents.map((event, idx) => (
                <div
                  key={`event-${idx}-${event.text.substring(0, 20)}`}
                  className="flex items-start gap-2 text-xs"
                >
                  <span className="text-base flex-shrink-0">{event.icon}</span>
                  <div className="flex-1">
                    <span className="text-text">{event.text}</span>
                    <span className="text-text-muted ml-2">({event.timeAgo})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Articles (always shown) */}
        {articles.length === 0 ? (
          <div className="text-sm text-text-muted py-4">
            {symbol ? "No recent articles available" : "No recent market news available"}
          </div>
        ) : (
          <>
            {!showAll && sortBy === "recent" && (
              <p className="text-xs text-text-muted mb-3">
                {positiveCount > 0 && negativeCount > 0
                  ? `Showing ${positiveCount} positive + ${negativeCount} negative articles`
                  : positiveCount > 0
                  ? `Showing ${positiveCount} most positive articles`
                  : negativeCount > 0
                  ? `Showing ${negativeCount} most negative articles`
                  : `Showing ${displayedArticles.length} articles`}
                {" "}({displayedArticles.length} of {sortedArticles.length})
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
                const sentimentScore = article.sentimentScore ?? article.sentiment?.score;
                const sentimentLabel = article.sentimentLabel ?? article.sentiment?.label;
                const sentimentConfidence = article.sentiment?.confidence;
                const sentimentModel = article.sentiment?.model;

                const timeAgo = formatNewsDate(article.publishedAt);
                const source = article.source && article.source.trim().length > 0
                  ? article.source.trim()
                  : formatVendorLabel(article.vendor);

                // Reserved for future display: article.impactSummary, article.actionableInsight
                const displayHeadline = article.headline;

                // Generate unique key
                const articleKey = article.contentHash || article.url || `article-${idx}-${article.headline.substring(0, 30)}`;

                // Unified detailed layout for all news (market and symbol)
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
                          {article.qualityConfidence !== undefined && article.qualityConfidence !== null && (
                            <Badge
                              variant={article.qualityConfidence >= 0.7 ? "success" : article.qualityConfidence >= 0.5 ? "warning" : "secondary"}
                              className="text-[10px]"
                            >
                              Quality {Math.round(article.qualityConfidence * 100)}%
                            </Badge>
                          )}
                          {article.isPrimaryArticle && (
                            <Badge variant="success" className="text-[10px]">
                              Primary
                            </Badge>
                          )}
                          {article.coverageCount && article.coverageCount > 1 && (
                            <Badge variant="secondary" className="text-[10px]">
                              {article.coverageCount} sources
                            </Badge>
                          )}
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
            {showToggleButton && (
              <div className="mt-3 flex justify-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleToggleShowAll}
                  className="text-xs"
                  disabled={isLoadingMore}
                >
                  {isLoadingMore
                    ? "Loading headlines..."
                    : showAll
                    ? "Show Less"
                    : onRequestExpanded
                    ? "Load More..."
                    : `Show All (${sortedArticles.length} total)`}
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
      )}
    </Card>
  );
}
