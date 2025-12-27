/**
 * MarketNarrative Component
 *
 * Displays plain-language market narrative with dual health scoring.
 * Actionable recommendations for amateur investors.
 */

"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface MarketNarrativeProps {
  /**
   * Plain-language narrative (3-4 sentences)
   */
  narrative: string;

  /**
   * Market Health score (0-100)
   */
  healthScore: number;

  /**
   * Fear & Greed Index score (0-100)
   */
  fearGreedScore: number;

  /**
   * Additional CSS classes
   */
  className?: string;
}

export function MarketNarrative({
  narrative,
  healthScore,
  fearGreedScore,
  className,
}: MarketNarrativeProps) {
  // Determine sentiment from average score
  const avgScore = (healthScore + fearGreedScore) / 2;

  const getSentimentEmoji = (score: number) => {
    if (score >= 75) return "🚀";
    if (score >= 60) return "📈";
    if (score >= 40) return "😐";
    if (score >= 25) return "📉";
    return "⚠️";
  };

  const getSentimentColor = (score: number) => {
    if (score >= 75) return "from-gain to-gain/80";
    if (score >= 60) return "from-gain/80 to-warning";
    if (score >= 40) return "from-warning to-warning/80";
    if (score >= 25) return "from-warning to-loss";
    return "from-loss to-loss/80";
  };

  return (
    <div
      className={cn(
        "rounded-lg p-6",
        "bg-gradient-to-br from-surface-elev/50 to-surface-muted/30",
        "border border-border",
        className
      )}
    >
      {/* Header with emoji */}
      <div className="mb-4 flex items-center gap-3">
        <span className="text-4xl" role="img" aria-label="Market sentiment">
          {getSentimentEmoji(avgScore)}
        </span>
        <div>
          <h3 className="text-lg font-semibold text-text">Market Overview</h3>
          <p className="text-xs text-text-muted">
            Updated just now • Actionable intelligence
          </p>
        </div>
      </div>

      {/* Narrative text */}
      <p className="text-base leading-relaxed text-text mb-4">
        {narrative}
      </p>

      {/* Dual scoring footer */}
      <div className="flex items-center gap-6 pt-4 border-t border-border">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
            Market Health
          </span>
          <div
            className={cn(
              "px-3 py-1 rounded-full font-bold text-sm",
              "bg-gradient-to-r",
              getSentimentColor(healthScore),
              "text-text-inverted shadow-sm"
            )}
          >
            {healthScore}/100
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-text-muted uppercase tracking-wide">
            Fear & Greed
          </span>
          <div
            className={cn(
              "px-3 py-1 rounded-full font-bold text-sm",
              "bg-gradient-to-r",
              getSentimentColor(fearGreedScore),
              "text-text-inverted shadow-sm"
            )}
          >
            {fearGreedScore}/100
          </div>
        </div>
      </div>
    </div>
  );
}
