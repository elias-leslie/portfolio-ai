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
    if (confidenceLevel === "HIGH") return "text-green-600 dark:text-green-400";
    if (confidenceLevel === "MEDIUM") return "text-yellow-600 dark:text-yellow-400";
    return "text-red-600 dark:text-red-400"; // LOW or unknown
  };

  // Get badge color
  const getBadgeColor = () => {
    if (confidenceLevel === "HIGH") return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
    if (confidenceLevel === "MEDIUM") return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
    return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"; // LOW
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
      <span className="text-xs text-gray-500 dark:text-gray-400">Readiness:</span>
      <span className={`text-sm font-medium ${getColor()}`}>
        {readinessScore.toFixed(0)}%
      </span>
      <span className={`px-2 py-0.5 text-xs font-medium rounded ${getBadgeColor()}`}>
        {confidenceLevel || "UNKNOWN"}
      </span>
    </div>
  );
}
