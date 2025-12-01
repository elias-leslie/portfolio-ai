/**
 * WatchlistCoverage component for displaying per-ticker gap coverage
 *
 * Shows a matrix view:
 * - Rows: Watchlist tickers
 * - Columns: Analysis types (Technical, Fundamental, Sentiment, Risk, etc.)
 * - Cells: Coverage % with color coding
 *
 * Features:
 * - Highlight tickers with poor coverage
 * - Show missing capabilities per ticker
 * - Color-coded heat map (green >80%, yellow 50-80%, red <50%)
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, AlertTriangle, CheckCircle2, TrendingDown } from "lucide-react";
import type { WatchlistGaps } from "@/lib/api/gaps";

interface WatchlistCoverageProps {
  data: WatchlistGaps;
}

/**
 * Get coverage color class
 */
function getCoverageColor(coverage: number): string {
  if (coverage >= 80) return "bg-green-500/20 text-green-700 dark:text-green-400";
  if (coverage >= 50) return "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400";
  if (coverage > 0) return "bg-red-500/20 text-red-700 dark:text-red-400";
  return "bg-muted text-muted-foreground";
}

/**
 * Get coverage status icon
 */
function getCoverageIcon(coverage: number) {
  if (coverage >= 80) return <CheckCircle2 className="h-3 w-3" />;
  if (coverage >= 50) return <AlertTriangle className="h-3 w-3" />;
  return <TrendingDown className="h-3 w-3" />;
}

/**
 * Format analysis type for display
 */
function formatAnalysisType(type: string): string {
  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Ticker coverage data from API
 */
interface TickerCoverageData {
  ticker: string;
  readiness_score: number;
  confidence_level: "LOW" | "MEDIUM" | "HIGH";
  coverage_by_analysis: Record<string, number>;
  missing_capabilities: string[];
  data_availability: Record<string, { exists: boolean; has_data: boolean; row_count: number }>;
}

/**
 * Calculate average coverage for a ticker from coverage_by_analysis
 */
function getAverageCoverage(tickerData: TickerCoverageData | undefined): number {
  if (!tickerData?.coverage_by_analysis) return 0;
  const coverages = Object.values(tickerData.coverage_by_analysis);
  if (coverages.length === 0) return 0;
  return coverages.reduce((sum, val) => sum + val, 0) / coverages.length;
}

/**
 * Get confidence level badge color
 */
function getConfidenceColor(level: string): string {
  if (level === "HIGH") return "bg-green-500/20 text-green-700 dark:text-green-400";
  if (level === "MEDIUM") return "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400";
  return "bg-red-500/20 text-red-700 dark:text-red-400";
}

/**
 * Individual ticker row component
 */
function TickerRow({
  ticker,
  tickerData,
  analysisTypes,
  isExpanded,
  onToggle,
}: {
  ticker: string;
  tickerData: TickerCoverageData | undefined;
  analysisTypes: string[];
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const coverageByAnalysis = tickerData?.coverage_by_analysis || {};
  const missingCapabilities = tickerData?.missing_capabilities || [];
  const readinessScore = tickerData?.readiness_score || 0;
  const confidenceLevel = tickerData?.confidence_level || "LOW";

  return (
    <div className="border-b border-border last:border-0">
      {/* Main row */}
      <div className="hover:bg-surface-muted transition-colors">
        <div
          className="grid gap-2 px-4 py-3 cursor-pointer"
          style={{
            gridTemplateColumns: `auto 100px 80px repeat(${analysisTypes.length}, minmax(70px, 1fr)) 80px`,
          }}
          onClick={onToggle}
        >
          {/* Expand icon */}
          <div className="flex items-center">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </div>

          {/* Ticker symbol */}
          <div className="flex items-center">
            <span className="font-mono font-semibold text-text">{ticker}</span>
          </div>

          {/* Confidence level */}
          <div className="flex items-center justify-center">
            <span className={`text-xs font-semibold px-2 py-1 rounded ${getConfidenceColor(confidenceLevel)}`}>
              {confidenceLevel}
            </span>
          </div>

          {/* Coverage per analysis type */}
          {analysisTypes.map((analysisType) => {
            const typeCoverage = coverageByAnalysis[analysisType] || 0;
            return (
              <div
                key={analysisType}
                className={`flex items-center justify-center rounded-md p-2 ${getCoverageColor(typeCoverage)}`}
              >
                <div className="flex items-center gap-1">
                  {getCoverageIcon(typeCoverage)}
                  <span className="text-xs font-semibold">{Math.round(typeCoverage)}%</span>
                </div>
              </div>
            );
          })}

          {/* Readiness score */}
          <div className={`flex items-center justify-center rounded-md p-2 ${getCoverageColor(readinessScore)}`}>
            <span className="text-xs font-semibold">{Math.round(readinessScore)}%</span>
          </div>
        </div>
      </div>

      {/* Expanded detail section */}
      {isExpanded && (
        <div
          className="border-t border-border bg-surface-muted p-4"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">
            Missing Capabilities for {ticker} ({missingCapabilities.length} total)
          </p>

          {missingCapabilities.length > 0 ? (
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {missingCapabilities.map((capability) => (
                <div
                  key={capability}
                  className="flex items-start gap-2 rounded-lg border border-border bg-surface p-2"
                >
                  <span className="text-loss">•</span>
                  <span className="text-xs text-muted-foreground">{capability}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-surface p-4 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-gain opacity-50" />
              <p className="mt-2 text-xs text-muted-foreground">
                No missing capabilities - Full coverage!
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Main WatchlistCoverage component
 */
export function WatchlistCoverage({ data }: WatchlistCoverageProps) {
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  const toggleExpand = (ticker: string) => {
    setExpandedTicker(expandedTicker === ticker ? null : ticker);
  };

  // Get unique analysis types from coverage_by_analysis of all tickers
  const analysisTypes = Array.from(
    new Set(
      Object.values(data.ticker_coverage || {}).flatMap((tickerData) =>
        Object.keys((tickerData as TickerCoverageData)?.coverage_by_analysis || {})
      )
    )
  ).sort();

  const tickers = data.watchlist_tickers || [];

  if (tickers.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <AlertTriangle className="mx-auto h-12 w-12 text-accent opacity-50" />
        <p className="mt-4 text-sm font-medium text-text">No watchlist tickers found</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Add tickers to your watchlist to see coverage analysis
        </p>
      </div>
    );
  }

  // Calculate average readiness across all tickers
  const avgReadiness = tickers.reduce((sum, ticker) => {
    const tickerData = data.ticker_coverage?.[ticker] as TickerCoverageData | undefined;
    return sum + (tickerData?.readiness_score || 0);
  }, 0) / (tickers.length || 1);

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">Coverage Legend</p>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded bg-green-500/20" />
            <span className="text-xs text-muted-foreground">
              <span className="font-semibold text-text">≥80%</span> Complete
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded bg-yellow-500/20" />
            <span className="text-xs text-muted-foreground">
              <span className="font-semibold text-text">50-79%</span> Adequate
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded bg-red-500/20" />
            <span className="text-xs text-muted-foreground">
              <span className="font-semibold text-text">&lt;50%</span> Poor
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-4 w-4 rounded bg-muted" />
            <span className="text-xs text-muted-foreground">
              <span className="font-semibold text-text">0%</span> Missing
            </span>
          </div>
        </div>
      </div>

      {/* Matrix table */}
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        {/* Header */}
        <div
          className="grid gap-2 border-b border-border bg-surface-muted px-4 py-3 text-xs font-medium text-muted-foreground sticky top-0"
          style={{
            gridTemplateColumns: `auto 100px 80px repeat(${analysisTypes.length}, minmax(70px, 1fr)) 80px`,
          }}
        >
          <div></div>
          <div>Ticker</div>
          <div className="text-center">Confidence</div>
          {analysisTypes.map((type) => (
            <div key={type} className="text-center text-[10px]">
              {formatAnalysisType(type).replace(" Analysis", "").replace(" Infrastructure", "")}
            </div>
          ))}
          <div className="text-center">Ready</div>
        </div>

        {/* Ticker rows */}
        <div className="divide-y divide-border">
          {tickers.map((ticker) => (
            <TickerRow
              key={ticker}
              ticker={ticker}
              tickerData={data.ticker_coverage?.[ticker] as TickerCoverageData | undefined}
              analysisTypes={analysisTypes}
              isExpanded={expandedTicker === ticker}
              onToggle={() => toggleExpand(ticker)}
            />
          ))}
        </div>
      </div>

      {/* Summary stats */}
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">Summary</p>
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <p className="text-2xl font-semibold text-text">{tickers.length}</p>
            <p className="text-xs text-muted-foreground">Tickers Analyzed</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-text">{analysisTypes.length}</p>
            <p className="text-xs text-muted-foreground">Analysis Types</p>
          </div>
          <div>
            <p className={`text-2xl font-semibold ${avgReadiness >= 50 ? "text-gain" : "text-loss"}`}>
              {Math.round(avgReadiness)}%
            </p>
            <p className="text-xs text-muted-foreground">Average Readiness</p>
          </div>
        </div>
      </div>
    </div>
  );
}
