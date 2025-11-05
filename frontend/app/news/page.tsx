"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Loader2,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import {
  useMarketNews,
  useWatchlistNews,
} from "@/lib/hooks/useNews";
import type { NewsBundle } from "@/lib/api/news";
import type { SentimentArticle } from "@/lib/api/watchlist";
import { useWatchlist } from "@/lib/hooks/useWatchlist";
import { usePreferences } from "@/lib/hooks/usePreferences";

const DEFAULT_ACCOUNT_ID = "default";

function sanitizeText(input?: string | null): string {
  if (!input) return "";
  const value = input.trim();
  if (!value) return "";

  try {
    if (typeof window !== "undefined" && typeof window.DOMParser !== "undefined") {
      const parser = new window.DOMParser();
      const doc = parser.parseFromString(value, "text/html");
      const text = doc.body?.textContent ?? "";
      if (text) {
        return text.replace(/\s+/g, " ").trim();
      }
    }
  } catch {
    // Fall back to regex stripping below
  }

  return value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function formatSentimentScore(score?: number | null) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "—";
  }
  const rounded = score.toFixed(2);
  return score > 0 ? `+${rounded}` : rounded;
}

function getBadgeVariantFromScore(
  score?: number | null
): "gain" | "loss" | "neutral" {
  if (score === null || score === undefined) return "neutral";
  if (score > 0.1) return "gain";
  if (score < -0.1) return "loss";
  return "neutral";
}

function getBadgeVariantFromLabel(
  label?: string | null
): "gain" | "loss" | "neutral" {
  switch (label) {
    case "positive":
      return "gain";
    case "negative":
      return "loss";
    default:
      return "neutral";
  }
}

function formatScoreChange(change?: number | null) {
  if (change === null || change === undefined || Number.isNaN(change)) {
    return null;
  }
  const formatted = change.toFixed(2);
  return change >= 0 ? `+${formatted}` : formatted;
}

function formatConfidence(confidence?: number) {
  if (confidence === null || confidence === undefined || Number.isNaN(confidence)) {
    return "—";
  }
  return `${Math.round(confidence * 100)}%`;
}

function formatTimestamp(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatModelCoverage(bundle: NewsBundle) {
  const breakdown = bundle.summary.model_breakdown ?? {};
  const total = Object.values(breakdown).reduce((sum, count) => sum + count, 0);
  const finbert = breakdown.finbert ?? 0;

  if (total === 0) {
    return "No articles scored";
  }
  if (finbert === total) {
    return "FinBERT coverage";
  }
  if (finbert === 0) {
    return "Fallback sentiment (VADER)";
  }
  return `FinBERT ${finbert}/${total}`;
}

function ArticleList({
  articles,
  maxArticles = 8,
}: {
  articles: SentimentArticle[];
  maxArticles?: number;
}) {
  const [expandedArticleId, setExpandedArticleId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"recent" | "sentiment" | "confidence">("recent");
  const [activeSentiments, setActiveSentiments] = useState<
    Array<"positive" | "neutral" | "negative">
  >([]);

  if (!articles.length) {
    return (
      <p className="text-xs text-text-muted" data-testid="no-headlines">
        No recent headlines.
      </p>
    );
  }

  const toggleArticle = (id: string) => {
    setExpandedArticleId((prev) => (prev === id ? null : id));
  };

  const toggleSentiment = (sentiment: "positive" | "neutral" | "negative") => {
    setActiveSentiments((prev) => {
      if (prev.includes(sentiment)) {
        return prev.filter((item) => item !== sentiment);
      }
      return [...prev, sentiment];
    });
  };

  const processedArticles = useMemo(() => {
    const filtered =
      activeSentiments.length === 0
        ? articles
        : articles.filter((article) =>
            activeSentiments.includes(article.sentiment.label)
          );

    const getTimestamp = (article: SentimentArticle) => {
      const value = article.published_at ?? article.fetched_at;
      return value ? new Date(value).getTime() : 0;
    };

    const sorted = [...filtered].sort((a, b) => {
      if (sortBy === "sentiment") {
        const aScore = a.sentiment.score ?? -Infinity;
        const bScore = b.sentiment.score ?? -Infinity;
        return bScore - aScore;
      }
      if (sortBy === "confidence") {
        const aConfidence = a.sentiment.confidence ?? -Infinity;
        const bConfidence = b.sentiment.confidence ?? -Infinity;
        return bConfidence - aConfidence;
      }
      return getTimestamp(b) - getTimestamp(a);
    });

    return sorted;
  }, [articles, activeSentiments, sortBy]);

  const visibleArticles = processedArticles.slice(0, maxArticles);
  const filteredCount = processedArticles.length;
  const filtersActive = activeSentiments.length > 0;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface-muted/20 px-3 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold uppercase tracking-wide text-[11px] text-text-muted">
            Sort
          </span>
          {[
            { key: "recent", label: "Latest" },
            { key: "sentiment", label: "Sentiment" },
            { key: "confidence", label: "Confidence" },
          ].map((option) => (
            <Button
              key={option.key}
              variant={sortBy === option.key ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setSortBy(option.key as typeof sortBy)}
            >
              {option.label}
            </Button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold uppercase tracking-wide text-[11px] text-text-muted">
            Filter
          </span>
          {(["positive", "neutral", "negative"] as const).map((sentiment) => {
            const isActive = activeSentiments.includes(sentiment);
            return (
              <Button
                key={sentiment}
                variant={isActive ? "default" : "outline"}
                size="sm"
                onClick={() => toggleSentiment(sentiment)}
                className="capitalize"
              >
                {sentiment}
              </Button>
            );
          })}
          {filtersActive && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setActiveSentiments([])}
              className="text-text-muted"
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {filteredCount === 0 && (
        <p className="text-xs text-text-muted">
          No headlines match the selected filters.
        </p>
      )}

      {visibleArticles.map((article) => {
        const articleId = `${article.content_hash}-${article.headline}`;
        const isExpanded = expandedArticleId === articleId;
        const sanitizedHeadline = sanitizeText(article.headline);
        return (
          <div
            key={articleId}
            className="rounded-md border border-border bg-surface-muted/30 p-3"
            data-testid="article-card"
          >
            <div className="flex items-start gap-2">
              <button
                type="button"
                onClick={() => toggleArticle(articleId)}
                aria-expanded={isExpanded}
                aria-controls={`${articleId}-details`}
                className="mt-1 inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border border-border bg-surface-muted text-text-muted transition hover:text-text focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                )}
                <span className="sr-only">
                  {isExpanded ? "Collapse headline details" : "Expand headline details"}
                </span>
              </button>

              <div className="flex-1 space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex-1 min-w-[200px] space-y-1">
                    {article.url ? (
                      <a
                        href={article.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
                      >
                        {sanitizedHeadline}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    ) : (
                      <p className="text-sm font-semibold text-text">{sanitizedHeadline}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
                      {article.source && <span>{article.source}</span>}
                      {(article.published_at || article.fetched_at) && (
                        <span>
                          {formatTimestamp(article.published_at ?? article.fetched_at)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 text-xs min-w-[120px]">
                    <Badge variant={getBadgeVariantFromLabel(article.sentiment.label)}>
                      {article.sentiment.label.toUpperCase()}
                    </Badge>
                    <span className="text-text font-semibold">
                      {formatSentimentScore(article.sentiment.score)}
                    </span>
                    <span className="text-text-muted">
                      Confidence {formatConfidence(article.sentiment.confidence)}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div
                    id={`${articleId}-details`}
                    className="space-y-2 text-xs text-text-muted leading-relaxed"
                  >
                    {article.summary && (
                      <p className="text-text-muted">{sanitizeText(article.summary)}</p>
                    )}
                    <div className="flex flex-wrap items-center gap-3">
                      <Badge
                        variant={
                          article.sentiment.model === "finbert" ? "secondary" : "loss"
                        }
                      >
                        {article.sentiment.model.toUpperCase()}
                      </Badge>
                      {article.author && <span>By {article.author}</span>}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {filteredCount > maxArticles ? (
        <p className="text-xs text-text-muted">
          Showing {maxArticles} of {filteredCount} headlines
        </p>
      ) : filteredCount > 0 ? (
        <p className="text-xs text-text-muted">
          Showing {filteredCount} {filteredCount === 1 ? "headline" : "headlines"}
        </p>
      ) : null}
    </div>
  );
}

function NewsBundleCard({ bundle, title }: { bundle: NewsBundle; title: string }) {
  const scoreChange = formatScoreChange(bundle.summary.score_change);
  const breakdown = bundle.summary.model_breakdown ?? {};
  const fallbackCount = Math.max(
    Object.values(breakdown).reduce((sum, count) => sum + count, 0) - (breakdown.finbert ?? 0),
    0
  );

  return (
    <Card className="border-border">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center justify-between">
          {title}
          <Badge variant={getBadgeVariantFromScore(bundle.summary.score)}>
            {formatSentimentScore(bundle.summary.score)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4 text-xs text-text-muted">
          <div>
            <p className="font-semibold text-text">Headline Mix</p>
            <p>
              Positive: <span className="text-gain font-medium">{bundle.summary.positive_count}</span>
            </p>
            <p>
              Neutral: <span className="font-medium text-text">{bundle.summary.neutral_count}</span>
            </p>
            <p>
              Negative: <span className="text-loss font-medium">{bundle.summary.negative_count}</span>
            </p>
          </div>
          <div className="space-y-1">
            <p className="font-semibold text-text">Model Coverage</p>
            <p>{formatModelCoverage(bundle)}</p>
            {fallbackCount > 0 && (
              <p className="text-xs text-text-muted">
                {fallbackCount} fallback headline{fallbackCount === 1 ? "" : "s"}
              </p>
            )}
            {scoreChange && (
              <p
                className={`inline-flex items-center gap-1 font-semibold ${
                  bundle.summary.score_change && bundle.summary.score_change >= 0
                    ? "text-gain"
                    : "text-loss"
                }`}
              >
                {bundle.summary.score_change && bundle.summary.score_change >= 0 ? (
                  <TrendingUp className="h-3 w-3" />
                ) : (
                  <TrendingDown className="h-3 w-3" />
                )}
                {scoreChange} vs prior window
              </p>
            )}
          </div>
          {bundle.summary.latest_published_at && (
            <div>
              <p className="font-semibold text-text">Latest</p>
              <p>{formatTimestamp(bundle.summary.latest_published_at)}</p>
            </div>
          )}
        </div>

        {bundle.summary.top_positive && (
          <div className="rounded-md border border-gain/40 bg-gain/10 p-3 text-xs">
            <p className="font-semibold text-gain flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              Top Positive
            </p>
            <p className="text-text">
              {sanitizeText(bundle.summary.top_positive.headline)}
            </p>
          </div>
        )}

        {bundle.summary.top_negative && (
          <div className="rounded-md border border-loss/40 bg-loss/10 p-3 text-xs">
            <p className="font-semibold text-loss flex items-center gap-1">
              <TrendingDown className="h-3 w-3" />
              Top Negative
            </p>
            <p className="text-text">
              {sanitizeText(bundle.summary.top_negative.headline)}
            </p>
          </div>
        )}

        <ArticleList articles={bundle.articles} maxArticles={8} />
      </CardContent>
    </Card>
  );
}

export default function NewsPage() {
  const [view, setView] = useState<"market" | "watchlist">("market");
  const [accountId] = useState(DEFAULT_ACCOUNT_ID);

  const marketQuery = useMarketNews();
  const watchlistQuery = useWatchlistNews(accountId);

  // Preload watchlist symbols (for messaging and context)
  const { data: watchlistData } = useWatchlist(accountId);
  const { data: preferences } = usePreferences();

  const activeQuery = view === "market" ? marketQuery : watchlistQuery;

  const handleRefresh = () => {
    if (view === "market") {
      marketQuery.refetch();
    } else {
      watchlistQuery.refetch();
    }
  };

  const marketBundles: NewsBundle[] = useMemo(() => {
    return marketQuery.data ? [marketQuery.data] : [];
  }, [marketQuery.data]);

  const watchlistBundles: NewsBundle[] = useMemo(() => {
    if (!watchlistQuery.data) return [];
    return watchlistQuery.data.items;
  }, [watchlistQuery.data]);

  const hasWatchlistSymbols = (watchlistData?.items.length ?? 0) > 0;
  const watchlistNewsHidden =
    preferences?.watchlist_show_news === false ||
    watchlistQuery.data?.status === "hidden";
  const shouldShowHiddenNotice =
    view === "watchlist" &&
    !watchlistQuery.isLoading &&
    !watchlistQuery.error &&
    hasWatchlistSymbols &&
    watchlistNewsHidden;

  return (
    <div className="bg-bg min-h-screen">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold text-text">News Intelligence</h1>
            <p className="mt-1 text-sm text-text-muted">
              FinBERT-scored headlines to inform trading decisions quickly and quantitatively.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 rounded-full bg-surface-muted/60 p-1">
              {([
                { key: "market", label: "Market" },
                { key: "watchlist", label: "My Watchlist" },
              ] as const).map(({ key, label }) => (
                <Button
                  key={key}
                  variant={view === key ? "default" : "ghost"}
                  size="sm"
                  className={`rounded-full px-4 py-1.5 text-sm ${
                    view === key ? "shadow-sm" : "text-text-muted"
                  }`}
                  onClick={() => setView(key)}
                >
                  {label}
                </Button>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={activeQuery.isFetching}
            >
              {activeQuery.isFetching ? (
                <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="mr-1 h-3 w-3" />
              )}
              Refresh
            </Button>
          </div>
        </div>

        {view === "market" && (
          <section className="space-y-4">
            {marketQuery.isLoading && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading market headlines...
              </div>
            )}
            {marketQuery.error && (
              <p className="text-sm text-loss">
                Failed to load market news: {marketQuery.error.message}
              </p>
            )}
            {!marketQuery.isLoading && !marketQuery.error && marketBundles.length === 0 && (
              <p className="text-sm text-text-muted">No market headlines available right now.</p>
            )}
            {marketBundles.map((bundle) => (
              <NewsBundleCard
                key={bundle.ticker}
                bundle={bundle}
                title="Market Overview"
              />
            ))}
          </section>
        )}

        {view === "watchlist" && (
          <section className="space-y-4">
            {watchlistQuery.isLoading && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading watchlist headlines...
              </div>
            )}
            {watchlistQuery.error && (
              <p className="text-sm text-loss">
                Failed to load watchlist news: {watchlistQuery.error.message}
              </p>
            )}
            {shouldShowHiddenNotice && (
              <p className="text-sm text-text-muted" data-testid="news-hidden">
                News hidden by preference. Enable watchlist news in Settings to restore headlines.
              </p>
            )}
            {!shouldShowHiddenNotice &&
              !watchlistQuery.isLoading &&
              !watchlistQuery.error &&
              watchlistBundles.length === 0 && (
                <p className="text-sm text-text-muted">
                  {hasWatchlistSymbols
                    ? "No recent headlines for your watchlist symbols."
                    : "Add tickers to your watchlist to see sentiment-scored headlines."}
                </p>
              )}
            {!shouldShowHiddenNotice &&
              watchlistBundles.map((bundle) => (
                <NewsBundleCard
                  key={bundle.ticker}
                  bundle={bundle}
                  title={`Symbol: ${bundle.ticker}`}
                />
              ))}
          </section>
        )}
      </div>
    </div>
  );
}
