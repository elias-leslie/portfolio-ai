"use client";

import { useState, useMemo } from "react";
import { useMarketNews } from "@/lib/hooks/useNews";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Newspaper, ExternalLink, Loader2, ArrowUpDown } from "lucide-react";
import {
  formatSentimentScore,
  formatVendorLabel,
  getSentimentBadgeVariant,
  formatConfidence,
  formatNewsDate,
} from "@/lib/utils/news-formatting";

type SortOption = "recent" | "positive" | "negative";

export function MarketNewsCard() {
  const [showAll, setShowAll] = useState(false);
  const [sortBy, setSortBy] = useState<SortOption>("recent");
  const { data: newsData, isLoading, error } = useMarketNews({ maxResults: 50 });

  const articles = newsData?.articles ?? [];

  // Sort articles based on selected option (must be before any conditional returns)
  const sortedArticles = useMemo(() => {
    const sorted = [...articles];
    if (sortBy === "positive") {
      return sorted.sort((a, b) => b.sentiment.score - a.sentiment.score);
    } else if (sortBy === "negative") {
      return sorted.sort((a, b) => a.sentiment.score - b.sentiment.score);
    }
    // "recent" - keep original order (already sorted by published_at from backend)
    return sorted;
  }, [articles, sortBy]);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Newspaper className="h-5 w-5 text-text-muted" />
          <h3 className="text-sm font-semibold text-text">Market News</h3>
        </div>
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-accent" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Newspaper className="h-5 w-5 text-text-muted" />
          <h3 className="text-sm font-semibold text-text">Market News</h3>
        </div>
        <div className="text-sm text-text-muted py-4">
          Failed to load market news
        </div>
      </Card>
    );
  }

  const displayCount = showAll ? sortedArticles.length : 10;
  const displayedArticles = sortedArticles.slice(0, displayCount);
  const hasMore = sortedArticles.length > 10;

  return (
    <Card className="p-6 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Newspaper className="h-5 w-5 text-accent" />
          <h3 className="text-lg font-semibold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Market News
          </h3>
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

      {articles.length === 0 ? (
        <div className="text-sm text-text-muted py-4">
          No recent market news available
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {displayedArticles.map((article, idx) => {
              const timeAgo = formatNewsDate(article.published_at);
              const source = article.source && article.source.trim().length > 0
                ? article.source.trim()
                : formatVendorLabel(article.vendor);

              const plainLanguageHeadline = (article as any).plain_language_headline;
              const impactSummary = (article as any).impact_summary;
              const actionableInsight = (article as any).actionable_insight;

              // Use original headline if AI hasn't processed it yet
              const displayHeadline = plainLanguageHeadline || article.headline;
              // Show indicator if AI processing is pending (no plain language version)
              const aiPending = !plainLanguageHeadline;

              return (
                <div
                  key={`article-${idx}-${article.content_hash || article.headline}`}
                  className="rounded-md border border-border bg-surface-muted/20 p-2 space-y-1"
                >
                  {article.url ? (
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      {aiPending && <span className="text-[10px]" title="AI processing pending">⏳</span>}
                      {displayHeadline}
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                  ) : (
                    <p className="text-xs font-medium text-text">
                      {aiPending && <span className="text-[10px]" title="AI processing pending">⏳</span>}
                      {displayHeadline}
                    </p>
                  )}

                  {/* AI Insights */}
                  {impactSummary && (
                    <p className="text-[10px] text-text-muted italic">
                      💡 {impactSummary}
                    </p>
                  )}
                  {actionableInsight && (
                    <p className="text-[10px] text-primary font-medium">
                      💡 {actionableInsight}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-2 text-[10px] text-text-muted">
                    {source && <span>{source}</span>}
                    {timeAgo && (
                      <>
                        <span>·</span>
                        <span>{timeAgo}</span>
                      </>
                    )}
                    {article.sentiment.label && (
                      <>
                        <span>·</span>
                        <Badge
                          variant={getSentimentBadgeVariant(article.sentiment.label)}
                          className="text-[9px] px-1.5 py-0"
                        >
                          {article.sentiment.label}
                        </Badge>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

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
    </Card>
  );
}
