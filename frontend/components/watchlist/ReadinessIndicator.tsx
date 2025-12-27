/**
 * Analysis Readiness Indicator - Task 5.3
 *
 * Displays data coverage readiness score for a symbol to indicate
 * how complete the analysis is based on available data capabilities.
 */

interface ReadinessIndicatorProps {
  readinessScore: number | null | undefined;
  confidenceLevel: string | null | undefined;
  symbol: string;
  compact?: boolean;
}

export function ReadinessIndicator({
  readinessScore,
  confidenceLevel,
  symbol,
  compact = false,
}: ReadinessIndicatorProps) {
  // Don't show if no data
  if (readinessScore === null || readinessScore === undefined) {
    return null;
  }

  // Determine color based on confidence level
  const getColor = () => {
    if (confidenceLevel === "HIGH") return "text-gain";
    if (confidenceLevel === "MEDIUM") return "text-warning";
    return "text-loss"; // LOW or unknown
  };

  // Get badge color
  const getBadgeColor = () => {
    if (confidenceLevel === "HIGH") return "bg-gain/10 text-gain";
    if (confidenceLevel === "MEDIUM") return "bg-warning/10 text-warning";
    return "bg-loss/10 text-loss"; // LOW
  };

  // Compact mode - just percentage
  if (compact) {
    return (
      <span className={`text-xs font-medium ${getColor()}`} title={`Analysis Readiness: ${readinessScore.toFixed(0)}%`}>
        {readinessScore.toFixed(0)}%
      </span>
    );
  }

  // Full mode - with label
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-text-muted">Readiness:</span>
      <span className={`text-sm font-medium ${getColor()}`}>
        {readinessScore.toFixed(0)}%
      </span>
      <span className={`px-2 py-0.5 text-xs font-medium rounded ${getBadgeColor()}`}>
        {confidenceLevel || "UNKNOWN"}
      </span>
    </div>
  );
}
