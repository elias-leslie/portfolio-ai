"use client";

import { Card } from "@/components/ui/card";
import { TrendingUp, TrendingDown } from "lucide-react";
import type { PositionPerformance } from "@/lib/api/portfolio";

interface TopPerformersProps {
  topPerformers: PositionPerformance[];
  bottomPerformers: PositionPerformance[];
}

export function TopPerformers({ topPerformers, bottomPerformers }: TopPerformersProps) {
  const formatPercent = (value: number) => {
    return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);
  };

  return (
    <Card className="p-6">
      <h3 className="mb-4 text-sm font-semibold text-text">Top Performers</h3>
      <div className="space-y-6">
        {/* Winners */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-gain" />
            <span className="text-xs font-medium text-text-muted">Best Performers</span>
          </div>
          <div className="space-y-2">
            {topPerformers.length > 0 ? (
              topPerformers.map((position, index) => (
                <div key={`top-${index}-${position.symbol}`} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-text">{position.symbol}</span>
                    <span className="text-xs text-text-muted">
                      {position.weight_pct.toFixed(1)}% of portfolio
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-gain">
                      {formatPercent(position.gain_pct)}
                    </div>
                    <div className="text-xs text-text-muted">
                      {formatCurrency(position.gain_amount)}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-text-muted">No data available</div>
            )}
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Losers */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-loss" />
            <span className="text-xs font-medium text-text-muted">Worst Performers</span>
          </div>
          <div className="space-y-2">
            {bottomPerformers.length > 0 ? (
              bottomPerformers.map((position, index) => (
                <div key={`bottom-${index}-${position.symbol}`} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-text">{position.symbol}</span>
                    <span className="text-xs text-text-muted">
                      {position.weight_pct.toFixed(1)}% of portfolio
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-loss">
                      {formatPercent(position.gain_pct)}
                    </div>
                    <div className="text-xs text-text-muted">
                      {formatCurrency(position.gain_amount)}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-sm text-text-muted">No data available</div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
