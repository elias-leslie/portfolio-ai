"use client";

import { cn } from "@/lib/utils";

export type Timeframe = "1M" | "3M" | "6M" | "1Y" | "3Y" | "5Y";

interface TimeframeSelectorProps {
  value: Timeframe;
  onChange: (value: Timeframe) => void;
  className?: string;
}

const TIMEFRAMES: { value: Timeframe; label: string; days: number }[] = [
  { value: "1M", label: "1M", days: 30 },
  { value: "3M", label: "3M", days: 90 },
  { value: "6M", label: "6M", days: 180 },
  { value: "1Y", label: "1Y", days: 365 },
  { value: "3Y", label: "3Y", days: 1095 },
  { value: "5Y", label: "5Y", days: 1825 },
];

export function timeframeToDays(tf: Timeframe): number {
  return TIMEFRAMES.find((t) => t.value === tf)?.days ?? 365;
}

export function TimeframeSelector({
  value,
  onChange,
  className,
}: TimeframeSelectorProps) {
  return (
    <div className={cn("flex gap-1", className)}>
      {TIMEFRAMES.map((tf) => (
        <button
          key={tf.value}
          onClick={() => onChange(tf.value)}
          className={cn(
            "px-2 py-0.5 text-xs font-medium rounded transition-colors",
            value === tf.value
              ? "bg-primary text-primary-foreground"
              : "bg-surface-muted/50 text-text-muted hover:bg-surface-muted"
          )}
        >
          {tf.label}
        </button>
      ))}
    </div>
  );
}
