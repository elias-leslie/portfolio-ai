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

  // Transform historical data: extract overall scores, filter out invalid values
  const allScores = historyResponse.history
    .map((h) => h.overall)
    .filter((score) => typeof score === "number" && !isNaN(score));

  // Sample data evenly across time range instead of just taking last 7 points
  // This ensures the sparkline shows actual trend variation, not just recent identical values
  const sampleDataEvenly = (data: number[], targetPoints: number = 7): number[] => {
    if (data.length <= targetPoints) {
      return data;
    }

    const sampled: number[] = [];
    const interval = (data.length - 1) / (targetPoints - 1);

    for (let i = 0; i < targetPoints; i++) {
      const index = Math.round(i * interval);
      sampled.push(data[index]);
    }

    return sampled;
  };

  const scoreData = sampleDataEvenly(allScores, 7);

  // If we don't have any valid data points, show placeholder
  if (scoreData.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-xs text-text-muted"
        style={{ width, height }}
      >
        —
      </div>
    );
  }

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
