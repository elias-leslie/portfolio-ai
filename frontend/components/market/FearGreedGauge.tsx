/**
 * Fear & Greed Index Gauge Component
 * Displays the current Fear & Greed score with regime label and trend
 */

"use client";

import { useFearGreed } from "@/lib/hooks/useFearGreed";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowUpIcon, ArrowDownIcon } from "lucide-react";

interface DisplayConfig {
  emoji: string;
  label: string;
  colorClass: string;
  badgeVariant: "default" | "secondary" | "outline" | "success" | "warning" | "error";
}

function getDisplay(score: number): DisplayConfig {
  if (score >= 75) {
    return {
      emoji: "😱",
      label: "Extreme Greed",
      colorClass: "text-status-success",
      badgeVariant: "success",
    };
  }
  if (score >= 55) {
    return {
      emoji: "😃",
      label: "Greed",
      colorClass: "text-status-success",
      badgeVariant: "success",
    };
  }
  if (score >= 45) {
    return {
      emoji: "😐",
      label: "Neutral",
      colorClass: "text-text-muted",
      badgeVariant: "secondary",
    };
  }
  if (score >= 25) {
    return {
      emoji: "😟",
      label: "Fear",
      colorClass: "text-status-warning",
      badgeVariant: "warning",
    };
  }
  return {
    emoji: "😨",
    label: "Extreme Fear",
    colorClass: "text-status-error",
    badgeVariant: "error",
  };
}

export function FearGreedGauge() {
  const { data, isLoading, error } = useFearGreed();

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="space-y-4 animate-pulse">
          <h2 className="text-lg font-semibold text-foreground">Fear & Greed Index</h2>
          <div className="flex items-center justify-between">
            <div className="h-24 w-24 bg-muted rounded-full" />
            <div className="space-y-2 flex-1 ml-6">
              <div className="h-8 bg-muted rounded w-32" />
              <div className="h-6 bg-muted rounded w-24" />
            </div>
          </div>
        </div>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Fear & Greed Index</h2>
        <p className="text-sm text-muted-foreground">
          Unable to load Fear & Greed data. Please try again later.
        </p>
      </Card>
    );
  }

  const { reading } = data;
  const display = getDisplay(reading.score);
  const trendUp = reading.scoreChange && reading.scoreChange > 0;
  const trendDown = reading.scoreChange && reading.scoreChange < 0;

  return (
    <Card className="p-6">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Fear & Greed Index</h2>
          <span className="text-xs text-muted-foreground">
            {reading.signalCount} signals
          </span>
        </div>

        {/* Main Display */}
        <div className="flex items-center justify-between">
          {/* Score Circle */}
          <div className="relative">
            <div
              className={`
                flex items-center justify-center
                h-28 w-28 rounded-full
                border-4 ${display.colorClass}
                bg-background
              `}
            >
              <div className="text-center">
                <div className={`text-4xl font-bold ${display.colorClass}`}>
                  {reading.score.toFixed(0)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">/ 100</div>
              </div>
            </div>
          </div>

          {/* Label and Trend */}
          <div className="flex-1 ml-6 space-y-3">
            {/* Emoji + Label Badge */}
            <div className="flex items-center gap-3">
              <span className="text-4xl" role="img" aria-label={display.label}>
                {display.emoji}
              </span>
              <Badge variant={display.badgeVariant} className="text-base px-3 py-1">
                {display.label}
              </Badge>
            </div>

            {/* Trend Indicator */}
            {reading.scoreChange !== undefined && reading.scoreChange !== null && (
              <div className="flex items-center gap-2">
                {trendUp && (
                  <>
                    <ArrowUpIcon className="h-4 w-4 text-status-success" />
                    <span className="text-sm text-status-success font-medium">
                      +{reading.scoreChange.toFixed(1)} from yesterday
                    </span>
                  </>
                )}
                {trendDown && (
                  <>
                    <ArrowDownIcon className="h-4 w-4 text-status-error" />
                    <span className="text-sm text-status-error font-medium">
                      {reading.scoreChange.toFixed(1)} from yesterday
                    </span>
                  </>
                )}
                {!trendUp && !trendDown && (
                  <span className="text-sm text-muted-foreground">
                    Unchanged from yesterday
                  </span>
                )}
              </div>
            )}

            {/* Date */}
            <p className="text-xs text-muted-foreground">
              As of {new Date(reading.date).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
              })}
            </p>
          </div>
        </div>

        {/* Description */}
        <div className="pt-2 border-t border-border">
          <p className="text-sm text-muted-foreground">
            {reading.score >= 75 && "Market sentiment is extremely bullish. Watch for potential reversal."}
            {reading.score >= 55 && reading.score < 75 && "Market sentiment is optimistic. Greed is building."}
            {reading.score >= 45 && reading.score < 55 && "Market sentiment is balanced. No clear trend."}
            {reading.score >= 25 && reading.score < 45 && "Market sentiment is cautious. Fear is present."}
            {reading.score < 25 && "Market sentiment is extremely bearish. Potential buying opportunity."}
          </p>
        </div>
      </div>
    </Card>
  );
}
