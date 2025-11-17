/**
 * LabeledIndicator Component
 *
 * Displays a market indicator with plain-language label, value, and optional tooltip.
 * Zero jargon - designed for amateur investors.
 */

"use client";

import * as React from "react";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { cn } from "@/lib/utils";

export interface LabeledIndicatorProps {
  /**
   * Plain-language label (e.g., "Market Volatility")
   */
  label: string;

  /**
   * Current value to display
   */
  value: string | number;

  /**
   * Daily change percentage (optional, e.g., 2.5 for +2.5%)
   */
  changePct?: number | null;

  /**
   * Educational tooltip (optional)
   */
  tooltip?: string;

  /**
   * Signal indicator: bullish | neutral | bearish
   */
  signal?: "bullish" | "neutral" | "bearish";

  /**
   * Emoji indicator (optional, e.g., "🟢")
   */
  emoji?: string;

  /**
   * Additional CSS classes
   */
  className?: string;

  /**
   * Size variant
   */
  size?: "sm" | "md" | "lg";
}

export function LabeledIndicator({
  label,
  value,
  changePct,
  tooltip,
  signal = "neutral",
  emoji,
  className,
  size = "md",
}: LabeledIndicatorProps) {
  // Signal colors
  const getSignalColor = (sig: string) => {
    switch (sig) {
      case "bullish":
        return "text-gain";
      case "bearish":
        return "text-loss";
      default:
        return "text-text-muted";
    }
  };

  // Format change percentage with color
  const formatChangePct = (pct: number) => {
    const sign = pct >= 0 ? "+" : "";
    const colorClass = pct >= 0 ? "text-gain" : "text-loss";
    return { text: `${sign}${pct.toFixed(2)}%`, colorClass };
  };

  // Size variants
  const sizes = {
    sm: {
      label: "text-xs",
      value: "text-lg",
      change: "text-xs",
      spacing: "space-y-0.5",
    },
    md: {
      label: "text-sm",
      value: "text-2xl",
      change: "text-sm",
      spacing: "space-y-1",
    },
    lg: {
      label: "text-base",
      value: "text-3xl",
      change: "text-base",
      spacing: "space-y-2",
    },
  };

  const sizeClasses = sizes[size];

  return (
    <div className={cn("flex flex-col", sizeClasses.spacing, className)}>
      {/* Label with optional tooltip */}
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            "font-medium text-text-muted uppercase tracking-wide",
            sizeClasses.label
          )}
        >
          {label}
        </span>
        {tooltip && <InfoTooltip content={tooltip} side="top" iconSize={12} />}
      </div>

      {/* Value with optional emoji and change percentage */}
      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            "font-bold",
            sizeClasses.value,
            getSignalColor(signal)
          )}
        >
          {value}
        </span>
        {emoji && <span className="text-xl" role="img">{emoji}</span>}
        {changePct !== null && changePct !== undefined && (
          <span
            className={cn(
              "font-semibold",
              sizeClasses.change,
              formatChangePct(changePct).colorClass
            )}
          >
            {formatChangePct(changePct).text}
          </span>
        )}
      </div>
    </div>
  );
}
