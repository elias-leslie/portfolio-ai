"use client";

import { useState } from "react";
import { useMarketNews } from "@/lib/hooks/useNews";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Newspaper, ExternalLink, Loader2 } from "lucide-react";
import {
  formatSentimentScore,
  formatVendorLabel,
  getSentimentBadgeVariant,
  formatConfidence,
  formatNewsDate,
} from "@/lib/utils/news-formatting";

export function MarketNewsCard() {
  const [showAll, setShowAll] = useState(false);
  const { data: newsData, isLoading, error } = useMarketNews({ maxResults: 20 });

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

  const articles = newsData?.articles ?? [];
  const displayCount = showAll ? 20 : 6;
  const displayedArticles = articles.slice(0, displayCount);
  const hasMore = articles.length > 6;

  return (
    <Card className="p-6 shadow-lg">
      <div className="flex items-center gap-2 mb-4">
        <Newspaper className="h-5 w-5 text-accent" />
        <h3 className="text-lg font-semibold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          Market News
        </h3>
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
                      {article.headline}
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                  ) : (
                    <p className="text-xs font-medium text-text">
                      {article.headline}
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
                {showAll ? "Show Less" : `Show More (${articles.length - 6} more)`}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
