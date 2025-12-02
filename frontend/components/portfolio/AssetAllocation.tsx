"use client";

import { Card } from "@/components/ui/card";
import { PieChart } from "lucide-react";
import type { PositionPerformance } from "@/lib/api/portfolio";

interface AssetAllocationProps {
  topPerformers: PositionPerformance[];
}

export function AssetAllocation({ topPerformers }: AssetAllocationProps) {
  // Sort by weight to show largest holdings
  const topHoldings = [...topPerformers].sort((a, b) => b.weight_pct - a.weight_pct).slice(0, 5);

  const formatPercent = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const getBarColor = (index: number) => {
    const colors = [
      "bg-primary",
      "bg-accent",
      "bg-purple-500",
      "bg-blue-500",
      "bg-green-500",
    ];
    return colors[index % colors.length];
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2">
        <PieChart className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-text">Top Holdings</h3>
      </div>

      <div className="space-y-4">
        {topHoldings.length > 0 ? (
          topHoldings.map((position, index) => (
            <div key={`holding-${index}-${position.symbol}`}>
              <div className="mb-1 flex items-center justify-between">
                <span className="font-medium text-text">{position.symbol}</span>
                <span className="text-sm text-text-muted">
                  {formatPercent(position.weight_pct)}
                </span>
              </div>
              <div className="mb-1 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                <div
                  className={`h-full transition-all duration-500 ${getBarColor(index)}`}
                  style={{ width: `${position.weight_pct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>{formatCurrency(position.current_value)}</span>
                <span
                  className={position.gain_pct >= 0 ? "text-gain" : "text-loss"}
                >
                  {position.gain_pct >= 0 ? "+" : ""}
                  {position.gain_pct.toFixed(1)}%
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="py-8 text-center text-sm text-text-muted">
            No holdings data available
          </div>
        )}
      </div>
    </Card>
  );
}
