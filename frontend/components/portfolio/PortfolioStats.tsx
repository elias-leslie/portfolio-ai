"use client";

import { Card } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";
import type { PortfolioAnalytics } from "@/lib/api/portfolio";

interface PortfolioStatsProps {
  analytics: PortfolioAnalytics;
}

export function PortfolioStats({ analytics }: PortfolioStatsProps) {
  // Calculate average position size
  const avgPositionSize =
    analytics.top_performers.length > 0
      ? analytics.total_value / analytics.top_performers.length
      : 0;

  // Find largest position
  const largestPosition =
    analytics.top_performers.length > 0
      ? Math.max(...analytics.top_performers.map((p) => p.weight_pct))
      : 0;

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-text">Portfolio Stats</h3>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Total Positions</span>
          <span className="text-sm font-medium text-text">
            {analytics.top_performers.length + analytics.bottom_performers.length}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Avg Position Size</span>
          <span className="text-sm font-medium text-text">
            {formatCurrency(avgPositionSize)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Largest Position</span>
          <span className="text-sm font-medium text-text">
            {largestPosition.toFixed(1)}%
          </span>
        </div>
        {analytics.sharpe_ratio !== null && (
          <div className="flex justify-between items-center border-t border-border pt-3">
            <span className="text-sm text-text-muted">Sharpe Ratio</span>
            <span
              className={`text-sm font-medium ${
                analytics.sharpe_ratio >= 1
                  ? "text-gain"
                  : analytics.sharpe_ratio >= 0
                  ? "text-accent"
                  : "text-loss"
              }`}
            >
              {analytics.sharpe_ratio.toFixed(2)}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}
