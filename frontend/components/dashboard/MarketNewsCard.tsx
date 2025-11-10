"use client";

import { useMarketNews } from "@/lib/hooks/useNews";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Newspaper, ExternalLink, Loader2 } from "lucide-react";
import {
  formatSentimentScore,
  formatVendorLabel,
  getSentimentBadgeVariant,
  formatConfidence,
  formatNewsDate,
} from "@/lib/utils/news-formatting";

export function MarketNewsCard() {
  const { data: newsData, isLoading, error } = useMarketNews({ maxResults: 5 });

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
        <div className="space-y-2">
          {articles.slice(0, 5).map((article, idx) => {
            const timeAgo = formatNewsDate(article.published_at);
            const vendorLabel = formatVendorLabel(article.vendor);
            const publisherLabel = article.source && article.source.trim().length > 0
              ? article.source.trim()
              : "Publisher Unknown";

            return (
              <div
                key={`article-${idx}-${article.content_hash || article.headline}`}
                className="rounded-md border border-border bg-surface-muted/30 p-3 hover:bg-surface-muted/50 transition-colors"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex-1 space-y-1">
                    {article.url ? (
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline group"
                      >
                        {article.headline}
                        <ExternalLink className="h-3 w-3 opacity-60 group-hover:opacity-100 transition-opacity" />
                      </a>
                    ) : (
                      <p className="text-sm font-semibold text-text">
                        {article.headline}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
                      <Badge
                        variant="outline"
                        className="text-[10px] font-semibold uppercase tracking-wide"
                      >
                        {vendorLabel}
                      </Badge>
                      <span className="text-text">
                        Publisher: {publisherLabel}
                      </span>
                      {timeAgo && <span>{timeAgo}</span>}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-2 text-xs">
                    <Badge variant={getSentimentBadgeVariant(article.sentiment.label)}>
                      {article.sentiment.label.toUpperCase()}
                    </Badge>
                    <span className="text-text font-semibold">
                      {formatSentimentScore(article.sentiment.score)}
                    </span>
                    <span className="text-text-muted">
                      Confidence {formatConfidence(article.sentiment.confidence)}
                    </span>
                    <Badge
                      variant={article.sentiment.model === "finbert" ? "secondary" : "loss"}
                    >
                      {article.sentiment.model.toUpperCase()}
                    </Badge>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
