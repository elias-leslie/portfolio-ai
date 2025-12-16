"use client";

import Link from "next/link";
import { ArrowRight, TrendingUp } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { usePaperTradeSummary } from "@/lib/hooks/usePaperTrades";

function PaperTradingSkeleton() {
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

export function PaperTradingCard() {
  const { data: summary, isLoading, error } = usePaperTradeSummary();

  if (isLoading) {
    return <PaperTradingSkeleton />;
  }

  if (error || !summary) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Paper Trading</CardTitle>
          <CardDescription>Real-time trading simulation</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-text-muted">
            Failed to load paper trading summary. Please try again.
          </div>
        </CardContent>
      </Card>
    );
  }

  const pnlValue = typeof summary.totalPnlPct === "number"
    ? summary.totalPnlPct
    : parseFloat(String(summary.totalPnlPct));
  const pnlColor = pnlValue >= 0 ? "text-gain" : "text-loss";
  const pnlBgColor = pnlValue >= 0 ? "bg-gain/10" : "bg-loss/10";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Paper Trading</CardTitle>
            <CardDescription>Real-time trading simulation</CardDescription>
          </div>
          <TrendingUp className="h-5 w-5 text-primary" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Open Positions */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-text-muted">Open Positions</p>
              <p className="text-2xl font-bold text-text mt-1">
                {summary.totalOpen}
              </p>
            </div>
          </div>

          {/* Total P&L */}
          <div className={`rounded-lg ${pnlBgColor} p-3`}>
            <p className="text-sm text-text-muted">Total P&L</p>
            <p className={`text-2xl font-bold ${pnlColor} mt-1`}>
              {pnlValue >= 0 ? "+" : ""}
              {typeof summary.totalPnlPct === "number"
                ? summary.totalPnlPct.toFixed(2)
                : parseFloat(String(summary.totalPnlPct)).toFixed(2)}
              %
            </p>
          </div>

          {/* Win Rate */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm text-text-muted">Win Rate</p>
              <p className="text-2xl font-bold text-text mt-1">
                {typeof summary.winRate === "number"
                  ? summary.winRate.toFixed(0)
                  : parseFloat(String(summary.winRate)).toFixed(0)}
                %
              </p>
            </div>
            <div className="text-xs text-text-muted text-right">
              <p>{summary.totalClosed} closed trades</p>
            </div>
          </div>

          {/* Additional Stats */}
          {summary.avgReturnPct !== undefined && summary.avgReturnPct !== null && (
            <div className="border-t border-border/50 pt-3 mt-3">
              <p className="text-xs text-text-muted">Average Return</p>
              <p className="text-sm font-medium text-text mt-1">
                {typeof summary.avgReturnPct === "number"
                  ? summary.avgReturnPct >= 0
                    ? "+"
                    : ""
                  : parseFloat(String(summary.avgReturnPct)) >= 0
                    ? "+"
                    : ""}
                {typeof summary.avgReturnPct === "number"
                  ? summary.avgReturnPct.toFixed(2)
                  : parseFloat(String(summary.avgReturnPct)).toFixed(2)}
                %
              </p>
            </div>
          )}

          {/* View Details Link */}
          <Link href="/trading">
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-2"
            >
              View Details
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
