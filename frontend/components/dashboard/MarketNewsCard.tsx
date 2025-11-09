"use client";

import { useMarketNews } from "@/lib/hooks/useNews";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Newspaper, ExternalLink, Loader2 } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

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

  // Helper to get sentiment badge variant (matches watchlist)
  const getBadgeVariant = (label: string) => {
    const normalized = label.toLowerCase();
    if (normalized === "positive") return "gain";
    if (normalized === "negative") return "loss";
    return "outline";
  };

  // Helper to format sentiment score
  const formatSentimentScore = (score: number | null | undefined) => {
    if (score === null || score === undefined) return "N/A";
    return score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
  };

  // Helper to format confidence
  const formatConfidence = (confidence: number | null | undefined) => {
    if (confidence === null || confidence === undefined) return "N/A";
    return `${(confidence * 100).toFixed(0)}%`;
  };

  // Vendor label formatting (matches watchlist)
  const formatVendorLabel = (vendor?: string | null): string => {
    if (!vendor) return "Unknown Source";
    const VENDOR_LABELS: Record<string, string> = {
      polygon: "Polygon",
      finnhub: "Finnhub",
      fmp: "FMP",
      google_news: "Google News",
      yfinance: "Yahoo Finance",
    };
    const normalized = vendor.toLowerCase();
    return VENDOR_LABELS[normalized] || vendor.trim();
  };

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
            const publishedAt = article.published_at ? new Date(article.published_at) : null;
            const timeAgo = publishedAt ? formatDistanceToNow(publishedAt, { addSuffix: true }) : null;
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
                    <Badge variant={getBadgeVariant(article.sentiment.label)}>
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
