/**
 * MarketIntelligence Component
 *
 * Visual-first market conditions display:
 * - Market Movers (top gainers/losers) + Sector Movers at top
 * - Market Sentiment trend chart (Fear & Greed + News + P/C Ratio)
 * - Key Indicators trend chart (S&P 500, VIX, 10Y, Dollar)
 * - Sector Performance chart
 */

"use client";

import { useMarketIntelligence } from "@/lib/hooks/useMarketIntelligence";
import { Card } from "@/components/ui/card";
import { SentimentTrendChart } from "./SentimentTrendChart";
import { IndicatorsTrendChart } from "./IndicatorsTrendChart";
import { SectorPerformanceChart } from "./SectorPerformanceChart";
import { MarketMoversTable } from "./MarketMoversTable";
import { SectorMoversTable } from "./SectorMoversTable";

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

  const { fear_greed, sector_rotation } = data;

  return (
    <Card className="p-6 shadow-lg">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-text bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          Market Conditions
        </h2>
      </div>

      {/* Fear & Greed Alert if stale */}
      {fear_greed.is_stale && (
        <div className="mb-4 px-3 py-2 bg-warning/10 border border-warning/30 rounded-lg text-xs text-warning">
          Fear & Greed data is {fear_greed.age_days} days old. Market may have changed.
        </div>
      )}

      {/* Top Section: Market Movers (Stocks) + Sector Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Stock Movers */}
        <div className="bg-surface-muted/30 rounded-xl p-4 border border-border/30">
          <MarketMoversTable />
        </div>

        {/* Sector Movers */}
        <div className="bg-surface-muted/30 rounded-xl p-4 border border-border/30">
          <SectorMoversTable
            leading={sector_rotation.leading}
            neutral={sector_rotation.neutral}
            lagging={sector_rotation.lagging}
          />
        </div>
      </div>

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
    </Card>
  );
}
