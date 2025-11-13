/**
 * MarketIntelligence Component
 *
 * Consolidated market intelligence view with:
 * - Plain-language narrative at top
 * - Dual health scoring (Market Health + Fear & Greed)
 * - Split-view layout: indicators left, sectors right
 * - Zero technical jargon
 */

"use client";

import { useMarketIntelligence } from "@/lib/hooks/useMarketIntelligence";
import { Card } from "@/components/ui/card";
import { MarketNarrative } from "./MarketNarrative";
import { LabeledIndicator } from "./LabeledIndicator";
import { SectorRotationSummary } from "./SectorRotationSummary";
import { MarketTrendChart } from "./MarketTrendChart";
import { formatRelativeTime } from "@/lib/utils";
import { fetchMarketTrends, MarketTrendsResponse } from "@/lib/api/market";
import { useState, useEffect } from "react";

// Helper function to render trend arrow
const getTrendArrow = (trend?: "up" | "down" | "flat" | null, trendChange?: number | null) => {
  if (!trend || !trendChange) return null;

  if (trend === "up") {
    return <span className="text-gain ml-1" title={`+${trendChange} over 7 days`}>↑</span>;
  } else if (trend === "down") {
    return <span className="text-loss ml-1" title={`${trendChange} over 7 days`}>↓</span>;
  }
  return null; // flat - no arrow
};

export function MarketIntelligence() {
  const { data, isLoading, error } = useMarketIntelligence();
  const [trendData, setTrendData] = useState<MarketTrendsResponse | null>(null);
  const [trendLoading, setTrendLoading] = useState(true);

  // Fetch trend data
  useEffect(() => {
    async function loadTrends() {
      try {
        const trends = await fetchMarketTrends(30);
        setTrendData(trends);
      } catch (err) {
        console.error("Failed to load market trends:", err);
      } finally {
        setTrendLoading(false);
      }
    }
    loadTrends();
  }, []);

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="space-y-6 animate-pulse">
          <div className="h-32 bg-surface-muted/60 rounded" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="h-64 bg-surface-muted/60 rounded" />
            <div className="h-64 bg-surface-muted/60 rounded" />
          </div>
        </div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="p-6">
        <div className="text-sm text-text-muted py-4">
          Failed to load market intelligence. Please try again later.
        </div>
      </Card>
    );
  }

  const { narrative, market_health, fear_greed, indicators, sector_rotation, options_activity } = data;

  // Extract indicators in order
  const vixIndicator = indicators.vix;
  const sp500Indicator = indicators.sp500;
  const tnxIndicator = indicators.tnx;
  const dxyIndicator = indicators.dxy;
  const putcallIndicator = indicators.putcall;

  return (
    <Card className="p-6 shadow-lg">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-text bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          Market Conditions
        </h2>
      </div>

      {/* Narrative */}
      <div className="mb-6">
        <MarketNarrative
          narrative={narrative}
          healthScore={market_health.overall_score}
          fearGreedScore={fear_greed.score}
        />
      </div>

      {/* Staleness Warning */}
      {fear_greed.is_stale && (
        <div className="mb-6 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-start gap-3">
            <span className="text-xl">⚠️</span>
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-600 dark:text-yellow-400">
                Fear & Greed data is {fear_greed.age_days} day{fear_greed.age_days > 1 ? 's' : ''} old
              </p>
              <p className="text-xs text-yellow-600/80 dark:text-yellow-400/80 mt-1">
                Next update scheduled at 03:00 UTC daily
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Split View: Indicators (left) + Sector Rotation (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Key Indicators */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text mb-4 uppercase tracking-wide">
            Key Indicators
          </h3>

          {/* Dual Scores */}
          <div className="grid grid-cols-2 gap-4 p-4 rounded-lg bg-surface-muted/20">
            <div className="flex items-center gap-1">
              <LabeledIndicator
                label="Market Health"
                value={market_health.overall_score}
                signal={
                  market_health.overall_score >= 60
                    ? "bullish"
                    : market_health.overall_score >= 40
                    ? "neutral"
                    : "bearish"
                }
                size="md"
              />
              {getTrendArrow(market_health.trend, market_health.trend_change)}
            </div>
            <div className="flex items-center gap-1">
              <LabeledIndicator
                label="Fear & Greed"
                value={fear_greed.score}
                signal={
                  fear_greed.score >= 60
                    ? "bullish"
                    : fear_greed.score >= 40
                    ? "neutral"
                    : "bearish"
                }
                size="md"
              />
              {getTrendArrow(fear_greed.trend, fear_greed.trend_change)}
            </div>
          </div>

          {/* 30-Day Sparkline */}
          {!trendLoading && trendData && trendData.dates.length > 0 && (
            <div className="p-4 rounded-lg bg-surface-muted/20">
              <h4 className="text-xs font-semibold text-text-muted mb-2 uppercase tracking-wide">
                30-Day Trend
              </h4>
              <div className="w-full h-[60px]">
                <MarketTrendChart data={trendData} height={60} />
              </div>
            </div>
          )}

          {/* Market Indicators */}
          <div className="space-y-4">
            {vixIndicator && (
              <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
                <LabeledIndicator
                  label={vixIndicator.label}
                  value={vixIndicator.value.toFixed(2)}
                  changePct={vixIndicator.change_pct}
                  tooltip={vixIndicator.tooltip}
                  signal={
                    vixIndicator.signal === "Bullish"
                      ? "bullish"
                      : vixIndicator.signal === "Bearish"
                      ? "bearish"
                      : "neutral"
                  }
                  emoji={vixIndicator.emoji}
                  size="sm"
                />
              </div>
            )}

            {sp500Indicator && (
              <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
                <LabeledIndicator
                  label={sp500Indicator.label}
                  value={sp500Indicator.value.toFixed(2)}
                  changePct={sp500Indicator.change_pct}
                  tooltip={sp500Indicator.tooltip}
                  signal={
                    sp500Indicator.signal === "Bullish"
                      ? "bullish"
                      : sp500Indicator.signal === "Bearish"
                      ? "bearish"
                      : "neutral"
                  }
                  emoji={sp500Indicator.emoji}
                  size="sm"
                />
              </div>
            )}

            {tnxIndicator && (
              <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
                <LabeledIndicator
                  label={tnxIndicator.label}
                  value={`${tnxIndicator.value.toFixed(2)}%`}
                  changePct={tnxIndicator.change_pct}
                  tooltip={tnxIndicator.tooltip}
                  signal={
                    tnxIndicator.signal === "Bullish"
                      ? "bullish"
                      : tnxIndicator.signal === "Bearish"
                      ? "bearish"
                      : "neutral"
                  }
                  emoji={tnxIndicator.emoji}
                  size="sm"
                />
              </div>
            )}

            {dxyIndicator && (
              <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
                <LabeledIndicator
                  label={dxyIndicator.label}
                  value={dxyIndicator.value.toFixed(2)}
                  changePct={dxyIndicator.change_pct}
                  tooltip={dxyIndicator.tooltip}
                  signal={
                    dxyIndicator.signal === "Bullish"
                      ? "bullish"
                      : dxyIndicator.signal === "Bearish"
                      ? "bearish"
                      : "neutral"
                  }
                  emoji={dxyIndicator.emoji}
                  size="sm"
                />
              </div>
            )}

            {putcallIndicator && (
              <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
                <LabeledIndicator
                  label={putcallIndicator.label}
                  value={putcallIndicator.value.toFixed(2)}
                  changePct={putcallIndicator.change_pct}
                  tooltip={putcallIndicator.tooltip}
                  signal={
                    putcallIndicator.signal === "Bullish"
                      ? "bullish"
                      : putcallIndicator.signal === "Bearish"
                      ? "bearish"
                      : "neutral"
                  }
                  emoji={putcallIndicator.emoji}
                  size="sm"
                />
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Sector Rotation */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text mb-4 uppercase tracking-wide">
            Sector Rotation
          </h3>
          <div className="p-4 rounded-lg bg-surface-muted/20">
            <SectorRotationSummary rotation={sector_rotation} />
          </div>
        </div>
      </div>

      {/* Options Activity Section */}
      {options_activity && (
        <div className="mt-6 pt-6 border-t border-border">
          <h3 className="text-sm font-semibold text-text mb-4 uppercase tracking-wide">
            Options Positioning
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Near-term Focus */}
            <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                    Near-term Focus
                  </span>
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded ${
                      options_activity.near_term_signal === "High"
                        ? "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
                        : options_activity.near_term_signal === "Low"
                        ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                        : "bg-surface-muted/40 text-text-muted"
                    }`}
                  >
                    {options_activity.near_term_signal}
                  </span>
                </div>
                <div className="text-2xl font-bold text-text">
                  {options_activity.near_term_pct.toFixed(0)}%
                </div>
                <p className="text-xs text-text-muted">
                  {options_activity.near_term_signal === "High"
                    ? "Event uncertainty"
                    : options_activity.near_term_signal === "Low"
                    ? "Long-term positioning"
                    : "Balanced time horizon"}
                </p>
              </div>
            </div>

            {/* Concentration */}
            <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                    Market Positioning
                  </span>
                  <span
                    className={`text-xs font-semibold px-2 py-0.5 rounded ${
                      options_activity.concentration_signal === "Focused"
                        ? "bg-red-500/10 text-red-600 dark:text-red-400"
                        : options_activity.concentration_signal === "Dispersed"
                        ? "bg-green-500/10 text-green-600 dark:text-green-400"
                        : "bg-surface-muted/40 text-text-muted"
                    }`}
                  >
                    {options_activity.concentration_signal}
                  </span>
                </div>
                <div className="text-2xl font-bold text-text">
                  {options_activity.concentration_pct.toFixed(0)}%
                </div>
                <p className="text-xs text-text-muted">
                  {options_activity.concentration_signal === "Focused"
                    ? "High conviction trades"
                    : options_activity.concentration_signal === "Dispersed"
                    ? "Broad participation"
                    : "Balanced distribution"}
                </p>
              </div>
            </div>

            {/* Top Sectors */}
            <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
              <div className="flex flex-col gap-1">
                <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
                  Top Sectors
                </span>
                <div className="space-y-2 mt-2">
                  {options_activity.top_sectors.map((sector, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-text truncate flex-1">
                        {sector.sector}
                      </span>
                      <span className="text-xs font-semibold text-text ml-2">
                        {sector.weight_pct.toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer with timestamp */}
      <div className="mt-4 pt-3 border-t border-border">
        <p className="text-xs text-text-muted text-center">
          Market Data as of {formatRelativeTime(data.last_updated)}
        </p>
      </div>
    </Card>
  );
}
