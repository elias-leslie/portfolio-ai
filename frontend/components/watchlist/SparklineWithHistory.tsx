"use client";

import { useScoreHistory } from "@/lib/hooks/useWatchlist";
import { Sparkline } from "@/components/ui/sparkline";

interface SparklineWithHistoryProps {
  itemId: string;
  width?: number;
  height?: number;
  className?: string;
}

/**
 * Sparkline component that fetches and displays real historical score data
 * Uses the useScoreHistory hook to fetch 7-day history from the API
 */
export function SparklineWithHistory({
  itemId,
  width = 80,
  height = 24,
  className,
}: SparklineWithHistoryProps) {
  const { data: historyResponse, isLoading, error } = useScoreHistory(itemId);

  // Loading state
  if (isLoading) {
    return (
      <div
        className="animate-pulse rounded bg-surface-muted"
        style={{ width, height }}
        aria-label="Loading score history"
      />
    );
  }

  // Error or empty state
  if (
    error ||
    !historyResponse ||
    !historyResponse.history ||
    historyResponse.history.length === 0
  ) {
    return (
      <div
        className="flex items-center justify-center text-xs text-text-muted"
        style={{ width, height }}
      >
        —
      </div>
    );
  }

  // Transform historical data: extract overall scores, sort by timestamp, limit to 7 points
  const scoreData = historyResponse.history
    .map((h) => h.overall_score)
    .slice(-7); // Take last 7 data points

  return (
    <Sparkline
      data={scoreData}
      width={width}
      height={height}
      className={className}
      aria-label={`Score history for ${itemId}`}
    />
  );
}
