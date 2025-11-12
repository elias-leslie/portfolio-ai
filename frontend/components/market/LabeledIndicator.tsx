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

  // Size variants
  const sizes = {
    sm: {
      label: "text-xs",
      value: "text-lg",
      spacing: "space-y-0.5",
    },
    md: {
      label: "text-sm",
      value: "text-2xl",
      spacing: "space-y-1",
    },
    lg: {
      label: "text-base",
      value: "text-3xl",
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

      {/* Value with optional emoji */}
      <div className="flex items-center gap-2">
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
      </div>
    </div>
  );
}
