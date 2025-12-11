/**
 * MarketIntelligence Component
 *
 * Visual-first market conditions display:
 * - Market Sentiment trend chart (Fear & Greed + News + P/C Ratio)
 * - Key Indicators trend chart (S&P 500, VIX, 10Y, Dollar)
 * - Sector Performance chart
 * - Today's movers summary
 */

"use client";

import { useMarketIntelligence } from "@/lib/hooks/useMarketIntelligence";
import { Card } from "@/components/ui/card";
import { SentimentTrendChart } from "./SentimentTrendChart";
import { IndicatorsTrendChart } from "./IndicatorsTrendChart";
import { SectorPerformanceChart } from "./SectorPerformanceChart";
import { formatRelativeTime } from "@/lib/utils";

// Sector colors matching SectorPerformanceChart
const SECTOR_COLORS: Record<string, string> = {
  XLK: "#8B5CF6", // Purple - Technology
  XLF: "#3B82F6", // Blue - Financials
  XLE: "#F97316", // Orange - Energy
  XLV: "#10B981", // Green - Healthcare
  XLY: "#EC4899", // Pink - Consumer Discretionary
  XLP: "#6366F1", // Indigo - Consumer Staples
  XLI: "#EAB308", // Yellow - Industrials
  XLU: "#14B8A6", // Teal - Utilities
  XLRE: "#F43F5E", // Rose - Real Estate
  XLB: "#84CC16", // Lime - Materials
  XLC: "#06B6D4", // Cyan - Communication Services
};

export function MarketIntelligence() {
  const { data, isLoading, error } = useMarketIntelligence();

  if (isLoading) {
    return (
      <Card className="p-6 shadow-lg">
        <div className="space-y-6 animate-pulse">
          <div className="h-24 bg-surface-muted/60 rounded" />
          <div className="h-48 bg-surface-muted/60 rounded" />
          <div className="h-48 bg-surface-muted/60 rounded" />
          <div className="h-64 bg-surface-muted/60 rounded" />
        </div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="p-6 shadow-lg">
        <div className="text-sm text-text-muted py-4">
          Failed to load market intelligence. Please try again later.
        </div>
      </Card>
    );
  }

  const { fear_greed, sector_rotation, last_updated } = data;

  // Build today's movers from sector rotation
  const leadingSectors = sector_rotation.leading.slice(0, 3);
  const laggingSectors = sector_rotation.lagging.slice(0, 3);
  const neutralSectors = sector_rotation.neutral.slice(0, 4);

  return (
    <Card className="p-6 shadow-lg">
      {/* Header with last updated */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-text bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          Market Conditions
        </h2>
        <span className="text-xs text-text-muted">
          Updated {formatRelativeTime(last_updated)}
        </span>
      </div>

      {/* Fear & Greed Alert if stale */}
      {fear_greed.is_stale && (
        <div className="mb-4 px-3 py-2 bg-warning/10 border border-warning/30 rounded-lg text-xs text-warning">
          Fear & Greed data is {fear_greed.age_days} days old. Market may have changed.
        </div>
      )}

      {/* Charts Section */}
      <div className="space-y-8">
        {/* Sentiment Trend */}
        <div className="relative">
          <SentimentTrendChart />
        </div>

        {/* Key Indicators */}
        <div>
          <IndicatorsTrendChart />
        </div>

        {/* Sector Performance */}
        <div>
          <SectorPerformanceChart />
        </div>
      </div>

      {/* Today's Movers */}
      <div className="mt-8 pt-4 border-t border-border/50">
        <h3 className="text-sm font-semibold text-text mb-3">Today&apos;s Movers</h3>
        <div className="space-y-2 text-xs">
          {/* Leading */}
          {leadingSectors.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-success font-medium w-16">▲ Leading</span>
              <div className="flex flex-wrap gap-x-2">
                {leadingSectors.map((s, i) => (
                  <span key={s.symbol}>
                    <span style={{ color: SECTOR_COLORS[s.symbol] || "#888" }} className="font-medium">
                      {s.name}
                    </span>
                    {s.change_pct !== null && (
                      <span className={s.change_pct >= 0 ? "text-gain" : "text-loss"}>
                        {` ${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`}
                      </span>
                    )}
                    {i < leadingSectors.length - 1 && <span className="text-text-muted"> │</span>}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Neutral */}
          {neutralSectors.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-text-muted font-medium w-16">→ Neutral</span>
              <div className="flex flex-wrap gap-x-2">
                {neutralSectors.map((s, i) => (
                  <span key={s.symbol}>
                    <span style={{ color: SECTOR_COLORS[s.symbol] || "#888" }} className="font-medium">
                      {s.name}
                    </span>
                    {s.change_pct !== null && (
                      <span className={s.change_pct >= 0 ? "text-gain" : "text-loss"}>
                        {` ${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`}
                      </span>
                    )}
                    {i < neutralSectors.length - 1 && <span className="text-text-muted"> │</span>}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Lagging */}
          {laggingSectors.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-destructive font-medium w-16">▼ Lagging</span>
              <div className="flex flex-wrap gap-x-2">
                {laggingSectors.map((s, i) => (
                  <span key={s.symbol}>
                    <span style={{ color: SECTOR_COLORS[s.symbol] || "#888" }} className="font-medium">
                      {s.name}
                    </span>
                    {s.change_pct !== null && (
                      <span className={s.change_pct >= 0 ? "text-gain" : "text-loss"}>
                        {` ${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`}
                      </span>
                    )}
                    {i < laggingSectors.length - 1 && <span className="text-text-muted"> │</span>}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
