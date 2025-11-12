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
import { formatRelativeTime } from "@/lib/utils";

export function MarketIntelligence() {
  const { data, isLoading, error } = useMarketIntelligence();

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

  const { narrative, market_health, fear_greed, indicators, sector_rotation } = data;

  // Extract indicators in order
  const vixIndicator = indicators.vix;
  const sp500Indicator = indicators.sp500;
  const tnxIndicator = indicators.tnx;
  const dxyIndicator = indicators.dxy;

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

      {/* Split View: Indicators (left) + Sector Rotation (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Key Indicators */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-text mb-4 uppercase tracking-wide">
            Key Indicators
          </h3>

          {/* Dual Scores */}
          <div className="grid grid-cols-2 gap-4 p-4 rounded-lg bg-surface-muted/20">
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
          </div>

          {/* Market Indicators */}
          <div className="space-y-4">
            {vixIndicator && (
              <div className="p-4 rounded-lg bg-surface-muted/20 hover:bg-surface-muted/30 transition-colors">
                <LabeledIndicator
                  label={vixIndicator.label}
                  value={vixIndicator.value.toFixed(2)}
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

      {/* Footer with timestamp */}
      <div className="mt-4 pt-3 border-t border-border">
        <p className="text-xs text-text-muted text-center">
          Updated {formatRelativeTime(data.last_updated)}
        </p>
      </div>
    </Card>
  );
}
