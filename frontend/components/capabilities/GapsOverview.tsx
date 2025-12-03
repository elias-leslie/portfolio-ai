/**
 * Trading Intelligence Gaps Overview
 *
 * Displays gap analysis summary with:
 * - Total gaps by criticality (P0/P1/P2/P3)
 * - Coverage % per analysis type
 * - TOP 10 priority gaps
 */

"use client";

import { useState } from "react";
import { AlertTriangle, TrendingUp, CheckCircle2, XCircle, List, FileText, Loader2, BarChart3 } from "lucide-react";
import type { GapSummary, GapInfo, WatchlistGaps } from "@/lib/api/gaps";
import { generateTaskList, fetchWatchlistGaps } from "@/lib/api/gaps";
import { GapsList } from "./GapsList";
import { WatchlistCoverage } from "./WatchlistCoverage";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";

interface GapsOverviewProps {
  data: GapSummary;
}

export function GapsOverview({ data }: GapsOverviewProps) {
  const [showAllGaps, setShowAllGaps] = useState(false);
  const [selectedGapIds, setSelectedGapIds] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showWatchlistCoverage, setShowWatchlistCoverage] = useState(false);

  // Fetch watchlist coverage data
  const { data: watchlistData, isLoading: watchlistLoading } = useQuery({
    queryKey: ["watchlist-gaps"],
    queryFn: fetchWatchlistGaps,
    enabled: showWatchlistCoverage,
  });

  // Get all gaps from analysis types
  const allGaps: GapInfo[] = Object.values(data.analysis_types || {}).flatMap(
    (result) => result.gaps || []
  );

  // Handle task list generation
  const handleGenerateTaskList = async () => {
    if (selectedGapIds.length === 0) {
      toast.error("Please select at least one gap to fill");
      return;
    }

    setIsGenerating(true);
    try {
      const result = await generateTaskList(selectedGapIds);

      toast.success(
        `Task list generated!`,
        {
          description: `File: ${result.task_file}\nRun /do_it to start implementation`,
          duration: 8000,
        }
      );

      // Clear selection after successful generation
      setSelectedGapIds([]);
    } catch (error) {
      console.error("Failed to generate task list:", error);
      toast.error("Failed to generate task list", {
        description: error instanceof Error ? error.message : "Unknown error occurred",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  // Get criticality color
  const getCriticalityColor = (criticality: string) => {
    switch (criticality) {
      case "P0":
        return "text-red-500 bg-red-500/10 border-red-500/20";
      case "P1":
        return "text-orange-500 bg-orange-500/10 border-orange-500/20";
      case "P2":
        return "text-yellow-500 bg-yellow-500/10 border-yellow-500/20";
      case "P3":
        return "text-blue-500 bg-blue-500/10 border-blue-500/20";
      default:
        return "text-muted-foreground bg-muted";
    }
  };

  // Get coverage color
  const getCoverageColor = (coverage: number) => {
    if (coverage >= 80) return "text-green-500";
    if (coverage >= 50) return "text-yellow-500";
    return "text-red-500";
  };

  // Get maturity level badge
  const getMaturityBadge = (level: number) => {
    const labels = ["Missing", "Minimal", "Adequate", "Complete"];
    const colors = [
      "text-red-500 bg-red-500/10",
      "text-orange-500 bg-orange-500/10",
      "text-yellow-500 bg-yellow-500/10",
      "text-green-500 bg-green-500/10",
    ];
    return (
      <span className={`px-2 py-1 rounded-full text-xs ${colors[level]}`}>
        {labels[level]}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Total Gaps */}
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Gaps</p>
              <p className="text-2xl font-bold mt-1">{data.total_gaps}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-muted-foreground opacity-50" />
          </div>
        </div>

        {/* P0 Critical */}
        <div className="rounded-lg border border-red-500/20 bg-surface p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-red-500">P0 Critical</p>
              <p className="text-2xl font-bold mt-1 text-red-500">{data.p0_gaps}</p>
            </div>
            <XCircle className="h-8 w-8 text-red-500 opacity-50" />
          </div>
          <p className="text-xs text-muted-foreground mt-2">Blocking profitable trading</p>
        </div>

        {/* P1 High */}
        <div className="rounded-lg border border-orange-500/20 bg-surface p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-orange-500">P1 High</p>
              <p className="text-2xl font-bold mt-1 text-orange-500">{data.p1_gaps}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-orange-500 opacity-50" />
          </div>
          <p className="text-xs text-muted-foreground mt-2">Limiting edge potential</p>
        </div>

        {/* Average Coverage */}
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Avg Coverage</p>
              <p className={`text-2xl font-bold mt-1 ${getCoverageColor(data.avg_coverage_pct)}`}>
                {data.avg_coverage_pct.toFixed(1)}%
              </p>
            </div>
            <TrendingUp className="h-8 w-8 text-muted-foreground opacity-50" />
          </div>
          <p className="text-xs text-muted-foreground mt-2">Across all analysis types</p>
        </div>
      </div>

      {/* Analysis Types Coverage */}
      <div className="rounded-lg border border-border bg-surface p-6">
        <h3 className="text-lg font-semibold mb-4">Coverage by Analysis Type</h3>
        <div className="space-y-4">
          {Object.entries(data.analysis_types).map(([type, coverage]) => (
            <div key={type} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-medium capitalize">
                    {type.replace(/_/g, " ")}
                  </span>
                  {getMaturityBadge(coverage.maturity_level)}
                </div>
                <span className={`font-semibold ${getCoverageColor(coverage.coverage_pct)}`}>
                  {coverage.coverage_pct.toFixed(1)}%
                </span>
              </div>
              {/* Progress Bar */}
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${getCoverageColor(coverage.coverage_pct).replace("text-", "bg-")}`}
                  style={{ width: `${coverage.coverage_pct}%` }}
                />
              </div>
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>{coverage.available_capabilities} available</span>
                <span>•</span>
                <span className="text-red-400">{coverage.missing_capabilities} missing</span>
                <span>•</span>
                <span>{coverage.total_capabilities} total</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* TOP 10 Priority Gaps */}
      {data.top_10_priorities.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-6">
          <h3 className="text-lg font-semibold mb-4">
            TOP 10 Priority Gaps (Impact × 1/Effort)
          </h3>
          <div className="space-y-3">
            {data.top_10_priorities.map((gap, index) => (
              <div
                key={gap.gap_id}
                className="rounded-lg border border-border bg-surface-muted p-4 hover:bg-surface-hover transition-colors"
              >
                <div className="flex items-start gap-4">
                  {/* Rank */}
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center font-bold text-primary">
                    {index + 1}
                  </div>

                  {/* Content */}
                  <div className="flex-1 space-y-2">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h4 className="font-semibold">{gap.capability.replace(/_/g, " ")}</h4>
                        <p className="text-sm text-muted-foreground mt-1">{gap.gap_id}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 rounded-full text-xs border ${getCriticalityColor(gap.criticality)}`}>
                          {gap.criticality}
                        </span>
                        <span className="px-2 py-1 rounded-full text-xs bg-muted text-muted-foreground">
                          {gap.effort}
                        </span>
                      </div>
                    </div>

                    {/* Impact */}
                    <p className="text-sm">{gap.impact}</p>

                    {/* Current → Desired */}
                    <div className="text-xs space-y-1">
                      <div className="flex gap-2">
                        <span className="text-muted-foreground font-medium">Current:</span>
                        <span className="text-red-400">{gap.current_state}</span>
                      </div>
                      <div className="flex gap-2">
                        <span className="text-muted-foreground font-medium">Desired:</span>
                        <span className="text-green-400">{gap.desired_state}</span>
                      </div>
                    </div>

                    {/* Recommendation */}
                    <div className="text-xs bg-primary/5 p-2 rounded border border-primary/20">
                      <span className="text-primary font-medium">→ </span>
                      {gap.recommendation}
                    </div>

                    {/* Data Sources */}
                    {gap.data_sources && gap.data_sources.length > 0 && (
                      <div className="flex flex-wrap gap-2 text-xs">
                        {gap.data_sources.map((source, idx) => {
                          const [key, value] = Object.entries(source)[0] || ["", ""];
                          return (
                            <span
                              key={idx}
                              className="px-2 py-1 rounded bg-muted text-muted-foreground"
                            >
                              {key}: {value}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Gaps Section */}
      {data.total_gaps > 0 && (
        <div className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <List className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-text">All Gaps</h3>
              <span className="text-sm text-muted-foreground">
                ({allGaps.length} total)
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAllGaps(!showAllGaps)}
            >
              {showAllGaps ? "Hide Details" : "View All Gaps"}
            </Button>
          </div>

          {showAllGaps && (
            <div className="space-y-4">
              <GapsList
                gaps={allGaps}
                onSelectionChange={setSelectedGapIds}
              />

              {/* Generate Task List Button */}
              {selectedGapIds.length > 0 && (
                <div className="rounded-lg border-2 border-primary/20 bg-primary/5 p-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {selectedGapIds.length} gap{selectedGapIds.length !== 1 ? "s" : ""} selected
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Generate a task list to systematically fill these gaps
                    </p>
                  </div>
                  <Button
                    onClick={handleGenerateTaskList}
                    disabled={isGenerating}
                    className="flex items-center gap-2"
                  >
                    {isGenerating ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <FileText className="h-4 w-4" />
                        Generate Task List
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}

          {!showAllGaps && (
            <div className="rounded-lg border border-border bg-surface p-6 text-center">
              <p className="text-sm text-muted-foreground">
                Click "View All Gaps" to see detailed table with all {allGaps.length} gaps
              </p>
            </div>
          )}
        </div>
      )}

      {/* Watchlist Coverage Section */}
      {data.total_gaps > 0 && (
        <div className="mt-8">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-text">Watchlist Coverage</h3>
              <span className="text-sm text-muted-foreground">
                (per-symbol analysis)
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowWatchlistCoverage(!showWatchlistCoverage)}
            >
              {showWatchlistCoverage ? "Hide Coverage" : "Show Coverage Matrix"}
            </Button>
          </div>

          {showWatchlistCoverage && (
            <div>
              {watchlistLoading ? (
                <div className="rounded-lg border border-border bg-surface p-8 text-center">
                  <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
                  <p className="mt-4 text-sm text-muted-foreground">Loading watchlist coverage...</p>
                </div>
              ) : watchlistData ? (
                <WatchlistCoverage data={watchlistData} />
              ) : (
                <div className="rounded-lg border border-border bg-surface p-8 text-center">
                  <AlertTriangle className="mx-auto h-12 w-12 text-accent opacity-50" />
                  <p className="mt-4 text-sm text-muted-foreground">
                    Failed to load watchlist coverage data
                  </p>
                </div>
              )}
            </div>
          )}

          {!showWatchlistCoverage && (
            <div className="rounded-lg border border-border bg-surface p-6 text-center">
              <p className="text-sm text-muted-foreground">
                Click "Show Coverage Matrix" to see per-symbol gap analysis
              </p>
            </div>
          )}
        </div>
      )}

      {/* No Gaps */}
      {data.total_gaps === 0 && (
        <div className="rounded-lg border border-border bg-surface p-8 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-green-500 opacity-50" />
          <p className="mt-4 text-sm text-muted-foreground">
            No capability gaps identified. System is fully capable!
          </p>
        </div>
      )}
    </div>
  );
}
