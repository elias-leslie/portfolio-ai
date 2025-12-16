"use client";

import Link from "next/link";
import { ArrowRight, BarChart3 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useBacktestRuns } from "@/lib/hooks/useBacktest";

function BacktestSkeleton() {
  return (
    <Card>
      <CardHeader>
        <div className="space-y-2">
          <div className="h-5 w-32 animate-pulse rounded-md bg-surface-muted/60" />
          <div className="h-3 w-52 animate-pulse rounded-md bg-surface-muted/40" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {[0, 1, 2].map((item) => (
            <div key={`skeleton-${item}`} className="space-y-1">
              <div className="h-3 w-24 animate-pulse rounded bg-surface-muted/60" />
              <div className="h-5 w-16 animate-pulse rounded bg-surface-muted/80" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function getStatusBadgeVariant(
  status: string
): "default" | "secondary" | "destructive" | "success" {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "secondary";
    case "pending":
      return "secondary";
    case "failed":
      return "destructive";
    default:
      return "default";
  }
}

export function BacktestCard() {
  const { data: runs, isLoading, error } = useBacktestRuns();

  if (isLoading) {
    return <BacktestSkeleton />;
  }

  if (error || !runs) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backtests</CardTitle>
          <CardDescription>Strategy validation with historical data</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-text-muted">
            Failed to load backtests. Please try again.
          </div>
        </CardContent>
      </Card>
    );
  }

  // Get recent runs (limit to 3)
  const recentRuns = runs.slice(0, 3);
  const latestRun = runs.length > 0 ? runs[0] : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Backtests</CardTitle>
            <CardDescription>Strategy validation with historical data</CardDescription>
          </div>
          <BarChart3 className="h-5 w-5 text-primary" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Total Backtests */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-text-muted">Total Runs</p>
              <p className="text-2xl font-bold text-text mt-1">{runs.length}</p>
            </div>
          </div>

          {/* Latest Run Status */}
          {latestRun && (
            <div className="rounded-lg border border-border/50 bg-surface/40 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text-muted">Latest Run</p>
                  <p className="text-sm font-medium text-text mt-1 truncate">
                    {latestRun.symbol}
                  </p>
                  <p className="text-xs text-text-muted mt-1">
                    {new Date(latestRun.createdAt).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </p>
                </div>
                <Badge variant={getStatusBadgeVariant(latestRun.status)}>
                  {latestRun.status}
                </Badge>
              </div>

              {/* Latest Run Metrics */}
              {latestRun.status === "completed" && latestRun.sharpeRatio !== undefined && latestRun.sharpeRatio !== null && (
                <div className="mt-3 pt-3 border-t border-border/30 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-muted">Sharpe Ratio:</span>
                    <span className="font-medium text-text">
                      {typeof latestRun.sharpeRatio === "number"
                        ? latestRun.sharpeRatio.toFixed(2)
                        : parseFloat(String(latestRun.sharpeRatio)).toFixed(2)}
                    </span>
                  </div>
                  {latestRun.maxDrawdownPct !== undefined && latestRun.maxDrawdownPct !== null && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-muted">Max Drawdown:</span>
                      <span className="font-medium text-loss">
                        {typeof latestRun.maxDrawdownPct === "number"
                          ? latestRun.maxDrawdownPct.toFixed(2)
                          : parseFloat(String(latestRun.maxDrawdownPct)).toFixed(2)}
                        %
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Recent Runs List */}
          {recentRuns.length > 1 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-text-muted uppercase">
                Recent Runs
              </p>
              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                {recentRuns.slice(1).map((run) => (
                  <div
                    key={run.id}
                    className="flex items-center justify-between rounded-lg border border-border/30 bg-surface/20 px-3 py-2"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-text truncate">
                        {run.symbol}
                      </p>
                      <p className="text-xs text-text-muted">
                        {new Date(run.createdAt).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                    </div>
                    <Badge
                      variant={getStatusBadgeVariant(run.status)}
                      className="text-xs"
                    >
                      {run.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty State */}
          {runs.length === 0 && (
            <div className="text-center py-4">
              <p className="text-sm text-text-muted">
                No backtests yet. Start your first backtest to analyze strategy performance.
              </p>
            </div>
          )}

          {/* View Details Link */}
          <Link href="/backtest">
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-2"
            >
              View All Backtests
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
