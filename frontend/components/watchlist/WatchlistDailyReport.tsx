"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";

interface SymbolAdded {
  symbol: string;
  added_at: string;
  source: string;
}

interface SymbolRemoved {
  symbol: string;
  removed_at: string;
}

interface ScoreChange {
  symbol: string;
  old_score: number;
  new_score: number;
  change_pct: number;
}

interface DailyReport {
  report_date: string | null;
  generated_at: string | null;
  symbols_added: SymbolAdded[];
  symbols_removed: SymbolRemoved[];
  score_changes: ScoreChange[];
  is_stale: boolean;
}

async function fetchDailyReport(): Promise<DailyReport> {
  return apiRequest<DailyReport>("/api/watchlist/daily-report");
}

export function WatchlistDailyReport() {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: report, isLoading } = useQuery({
    queryKey: ["watchlist-daily-report"],
    queryFn: fetchDailyReport,
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4 shadow-sm">
        <div className="animate-pulse space-y-2">
          <div className="h-5 w-48 bg-surface-muted rounded" />
          <div className="h-4 w-64 bg-surface-muted rounded" />
        </div>
      </div>
    );
  }

  if (!report || !report.generated_at) {
    // Show placeholder when no report exists yet
    return (
      <div className="rounded-lg border border-border/50 bg-surface/50 p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <Clock className="h-5 w-5 text-text-muted" />
          <div>
            <h3 className="text-base font-semibold text-text">
              Daily Watchlist Report
            </h3>
            <p className="text-sm text-text-muted">
              First report will be generated at 09:00 UTC
            </p>
          </div>
        </div>
      </div>
    );
  }

  const hasActivity =
    report.symbols_added.length > 0 ||
    report.symbols_removed.length > 0 ||
    report.score_changes.length > 0;

  const generatedDate = new Date(report.generated_at);
  const now = new Date();
  const hoursAgo = Math.floor((now.getTime() - generatedDate.getTime()) / (1000 * 60 * 60));

  let timeLabel = "";
  if (hoursAgo < 1) {
    timeLabel = "Updated just now";
  } else if (hoursAgo < 24) {
    timeLabel = `Updated ${hoursAgo}h ago`;
  } else {
    const daysAgo = Math.floor(hoursAgo / 24);
    timeLabel = `Updated ${daysAgo}d ago`;
  }

  return (
    <div className="rounded-lg border border-border bg-surface shadow-sm">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 text-left hover:bg-surface-hover transition-colors"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-text-muted" />
            <div>
              <h3 className="text-base font-semibold text-text">
                Daily Watchlist Report
              </h3>
              <p className={cn(
                "text-sm",
                report.is_stale ? "text-yellow-500" : "text-text-muted"
              )}>
                {report.is_stale ? `⚠ Stale (${timeLabel})` : timeLabel}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {hasActivity && !isExpanded && (
              <div className="flex items-center gap-2 text-sm text-text-muted">
                {report.symbols_added.length > 0 && (
                  <span className="text-green-500">+{report.symbols_added.length}</span>
                )}
                {report.symbols_removed.length > 0 && (
                  <span className="text-red-500">-{report.symbols_removed.length}</span>
                )}
                {report.score_changes.length > 0 && (
                  <span className="text-blue-500">~{report.score_changes.length}</span>
                )}
              </div>
            )}
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-text-muted" />
            ) : (
              <ChevronDown className="h-5 w-5 text-text-muted" />
            )}
          </div>
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-border px-4 py-3 space-y-4">
          {!hasActivity && (
            <p className="text-sm text-text-muted">
              No changes in the last 24 hours
            </p>
          )}

          {/* Symbols Added */}
          {report.symbols_added.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text mb-2 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                Symbols Added ({report.symbols_added.length})
              </h4>
              <div className="flex flex-wrap gap-2">
                {report.symbols_added.map((item) => (
                  <div
                    key={item.symbol}
                    className="inline-flex items-center gap-1.5 rounded-md bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-500"
                  >
                    <span>{item.symbol}</span>
                    {item.source && item.source !== "manual" && (
                      <span className="text-green-500/60">({item.source})</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Symbols Removed */}
          {report.symbols_removed.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text mb-2 flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-red-500" />
                Symbols Removed ({report.symbols_removed.length})
              </h4>
              <div className="flex flex-wrap gap-2">
                {report.symbols_removed.map((item) => (
                  <div
                    key={item.symbol}
                    className="inline-flex items-center gap-1.5 rounded-md bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-500"
                  >
                    {item.symbol}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Significant Score Changes */}
          {report.score_changes.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-text mb-2">
                Significant Score Changes ({report.score_changes.length})
              </h4>
              <div className="space-y-2">
                {report.score_changes.map((change) => {
                  const isPositive = change.new_score > change.old_score;
                  return (
                    <div
                      key={change.symbol}
                      className="flex items-center justify-between rounded-md border border-border bg-surface-muted px-3 py-2"
                    >
                      <span className="text-sm font-medium text-text">
                        {change.symbol}
                      </span>
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-text-muted">
                          {change.old_score.toFixed(1)}
                        </span>
                        <span className="text-text-muted">→</span>
                        <span className={cn(
                          "font-medium",
                          isPositive ? "text-green-500" : "text-red-500"
                        )}>
                          {change.new_score.toFixed(1)}
                        </span>
                        <span className={cn(
                          "text-xs font-medium",
                          isPositive ? "text-green-500" : "text-red-500"
                        )}>
                          ({isPositive ? "+" : ""}{change.change_pct.toFixed(1)}%)
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
