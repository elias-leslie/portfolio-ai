/**
 * GapsList component for displaying all trading intelligence gaps in a table format
 *
 * Features:
 * - Expandable rows with detailed gap information
 * - Sortable by criticality, impact, effort
 * - Checkbox selection for task list generation
 * - Color-coded criticality badges
 */

import { useState, useEffect } from "react";
import {
  ChevronRight,
  ChevronDown,
  Database,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Target,
  Lightbulb,
  ExternalLink,
  Cloud,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import type { GapInfo } from "@/lib/api/gaps";
import { fetchGapProviders, type GapProvidersResponse } from "@/lib/api/sources";

interface GapsListProps {
  gaps: GapInfo[];
  onSelectionChange?: (selectedGapIds: string[]) => void;
  providerCounts?: Record<string, { count: number; tier: string }>;
}

/**
 * Get criticality badge color
 */
function getCriticalityColor(criticality: string): string {
  switch (criticality) {
    case "P0":
      return "bg-red-500/10 text-red-500 border-red-500/20";
    case "P1":
      return "bg-orange-500/10 text-orange-500 border-orange-500/20";
    case "P2":
      return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
    case "P3":
      return "bg-blue-500/10 text-blue-500 border-blue-500/20";
    default:
      return "bg-muted text-muted-foreground";
  }
}

/**
 * Get effort badge color
 */
function getEffortColor(effort: string): string {
  switch (effort) {
    case "LOW":
      return "bg-green-500/10 text-green-500 border-green-500/20";
    case "MEDIUM":
      return "bg-yellow-500/10 text-yellow-500 border-yellow-500/20";
    case "HIGH":
      return "bg-red-500/10 text-red-500 border-red-500/20";
    default:
      return "bg-muted text-muted-foreground";
  }
}

/**
 * Get severity badge color
 */
function getSeverityColor(severity: string): string {
  switch (severity) {
    case "blocking":
      return "bg-loss/10 text-loss border-loss/20";
    case "limiting":
      return "bg-accent/10 text-accent border-accent/20";
    case "optional":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-muted text-muted-foreground";
  }
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
 * Individual gap row component
 */
function GapRow({
  gap,
  rank,
  isExpanded,
  isSelected,
  onToggle,
  onSelect,
  providerCount,
}: {
  gap: GapInfo;
  rank: number;
  isExpanded: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onSelect: (selected: boolean) => void;
  providerCount?: { count: number; tier: string };
}) {
  const [providers, setProviders] = useState<GapProvidersResponse | null>(null);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [providersError, setProvidersError] = useState<string | null>(null);

  const handleFindProviders = async () => {
    setLoadingProviders(true);
    setProvidersError(null);
    try {
      const result = await fetchGapProviders(gap.gap_id);
      setProviders(result);
    } catch (err) {
      setProvidersError(err instanceof Error ? err.message : "Failed to fetch providers");
    } finally {
      setLoadingProviders(false);
    }
  };

  return (
    <div className="border-b border-border last:border-0">
      {/* Main row */}
      <div
        className="grid grid-cols-[auto_60px_150px_200px_80px_120px_80px_100px_auto] gap-3 px-4 py-3 hover:bg-surface-muted transition-colors cursor-pointer"
        onClick={onToggle}
      >
        {/* Checkbox + Expand icon */}
        <div className="flex items-center gap-2">
          <Checkbox
            checked={isSelected}
            onCheckedChange={onSelect}
            onClick={(e) => e.stopPropagation()}
          />
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>

        {/* Rank badge */}
        <div className="flex items-center">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {rank}
          </span>
        </div>

        {/* Analysis Type */}
        <div className="flex items-center">
          <span className="truncate text-sm font-medium" title={formatAnalysisType(gap.analysis_type)}>
            {formatAnalysisType(gap.analysis_type)}
          </span>
        </div>

        {/* Missing Capability */}
        <div className="flex items-center">
          <span className="truncate text-sm text-text" title={gap.capability}>
            {gap.capability.split("_").join(" ")}
          </span>
        </div>

        {/* Criticality */}
        <div className="flex items-center">
          <Badge className={getCriticalityColor(gap.criticality)} variant="outline">
            {gap.criticality}
          </Badge>
        </div>

        {/* Severity */}
        <div className="flex items-center">
          <Badge className={getSeverityColor(gap.severity)} variant="outline">
            {gap.severity}
          </Badge>
        </div>

        {/* Effort */}
        <div className="flex items-center">
          <Badge className={getEffortColor(gap.effort)} variant="outline">
            {gap.effort}
          </Badge>
        </div>

        {/* Provider Count */}
        <div className="flex items-center">
          {providerCount ? (
            providerCount.count > 0 ? (
              <Badge
                variant="outline"
                className={
                  providerCount.tier === "FREE"
                    ? "bg-gain/10 text-gain border-gain/20"
                    : "bg-accent/10 text-accent border-accent/20"
                }
              >
                {providerCount.count} {providerCount.count === 1 ? "provider" : "providers"}
              </Badge>
            ) : (
              <Badge variant="outline" className="bg-loss/10 text-loss border-loss/20">
                ⚠️ No coverage
              </Badge>
            )
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </div>

        {/* Gap ID */}
        <div className="flex items-center justify-end">
          <span className="text-xs font-mono text-muted-foreground">{gap.gap_id}</span>
        </div>
      </div>

      {/* Expanded detail section */}
      {isExpanded && (
        <div
          className="border-t border-border bg-surface-muted p-6 space-y-6"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Overview Section */}
          <section>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
              <Target className="h-4 w-4 text-primary" />
              Overview
            </h4>
            <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
              <div className="flex gap-8">
                <div className="flex-1">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                    Current State
                  </p>
                  <p className="text-sm text-text">{gap.current_state}</p>
                </div>
                <div className="flex items-center justify-center">
                  <ChevronRight className="h-6 w-6 text-muted-foreground" />
                </div>
                <div className="flex-1">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                    Desired State
                  </p>
                  <p className="text-sm text-text">{gap.desired_state}</p>
                </div>
              </div>
            </div>
          </section>

          {/* Impact Section */}
          <section>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
              <TrendingUp className="h-4 w-4 text-gain" />
              Impact & Why This Matters
            </h4>
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="text-sm text-text leading-relaxed">{gap.impact}</p>
              {gap.blocks_strategies && gap.blocks_strategies.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">
                    Blocks These Strategies
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {gap.blocks_strategies.map((strategy) => (
                      <Badge key={strategy} variant="outline" className="bg-loss/5 text-loss border-loss/20">
                        <AlertTriangle className="mr-1 h-3 w-3" />
                        {strategy}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Data Sources Section */}
          {gap.data_sources && gap.data_sources.length > 0 && (
            <section>
              <h4 className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
                <Database className="h-4 w-4 text-primary" />
                Data Sources Needed
              </h4>
              <div className="rounded-lg border border-border bg-surface p-4">
                <div className="grid gap-3">
                  {gap.data_sources.map((source, idx) => {
                    const sourceName = Object.keys(source)[0];
                    const sourceDesc = source[sourceName];
                    return (
                      <div key={idx} className="flex items-start gap-3">
                        <CheckCircle2 className="h-4 w-4 mt-0.5 text-gain" />
                        <div className="flex-1">
                          <p className="text-sm font-medium text-text">
                            {sourceName.charAt(0).toUpperCase() + sourceName.slice(1)}
                          </p>
                          <p className="text-xs text-muted-foreground">{sourceDesc}</p>
                        </div>
                        {!sourceName.startsWith("internal") && (
                          <ExternalLink className="h-4 w-4 text-muted-foreground" />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </section>
          )}

          {/* Available Providers Section */}
          <section>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
              <Cloud className="h-4 w-4 text-primary" />
              Available Data Providers
            </h4>
            <div className="rounded-lg border border-border bg-surface p-4">
              {!providers && !loadingProviders && !providersError && (
                <div className="flex flex-col items-center gap-3 py-2">
                  <p className="text-sm text-muted-foreground">
                    Click to find providers that can fulfill this requirement
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleFindProviders}
                  >
                    <Cloud className="mr-2 h-4 w-4" />
                    Find Providers
                  </Button>
                </div>
              )}

              {loadingProviders && (
                <div className="flex items-center justify-center py-4">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-sm text-muted-foreground">Searching providers...</span>
                </div>
              )}

              {providersError && (
                <div className="text-sm text-loss py-2">
                  {providersError}
                  <Button
                    variant="link"
                    size="sm"
                    className="ml-2"
                    onClick={handleFindProviders}
                  >
                    Retry
                  </Button>
                </div>
              )}

              {providers && providers.providers.length === 0 && (
                <div className="text-sm text-muted-foreground py-2">
                  No providers found for this requirement. Custom implementation may be needed.
                </div>
              )}

              {providers && providers.providers.length > 0 && (
                <div className="space-y-3">
                  {providers.providers.map((provider) => (
                    <div key={provider.provider} className="rounded-lg border border-border bg-surface-muted p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-text">{provider.provider}</span>
                          <Badge
                            variant="outline"
                            className={provider.tier === "FREE" ? "bg-gain/10 text-gain border-gain/20" : "bg-accent/10 text-accent border-accent/20"}
                          >
                            {provider.tier}
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          Priority: {provider.priority}
                        </span>
                      </div>
                      <div className="space-y-1">
                        {provider.endpoints.map((endpoint, idx) => (
                          <div key={idx} className="text-xs">
                            <code className="bg-surface px-1 py-0.5 rounded text-primary">
                              {endpoint.path || endpoint.endpoint}
                            </code>
                            <span className="text-muted-foreground ml-2">{endpoint.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Recommendation Section */}
          <section>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-text mb-3">
              <Lightbulb className="h-4 w-4 text-accent" />
              Recommended Action
            </h4>
            <div className="rounded-lg border-2 border-primary/20 bg-primary/5 p-4">
              <p className="text-sm text-text leading-relaxed font-medium">{gap.recommendation}</p>
              <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
                <span>
                  <span className="font-semibold">Effort:</span> {gap.effort}
                </span>
                <span>•</span>
                <span>
                  <span className="font-semibold">Priority:</span> {gap.criticality}
                </span>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

/**
 * Main GapsList component
 */
export function GapsList({ gaps, onSelectionChange, providerCounts }: GapsListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selectedGapIds, setSelectedGapIds] = useState<string[]>([]);

  const toggleExpand = (gapId: string) => {
    setExpandedId(expandedId === gapId ? null : gapId);
  };

  const toggleSelection = (gapId: string, selected: boolean) => {
    const newSelection = selected
      ? [...selectedGapIds, gapId]
      : selectedGapIds.filter((id) => id !== gapId);

    setSelectedGapIds(newSelection);
    onSelectionChange?.(newSelection);
  };

  const toggleSelectAll = (selected: boolean) => {
    const newSelection = selected ? gaps.map((g) => g.gap_id) : [];
    setSelectedGapIds(newSelection);
    onSelectionChange?.(newSelection);
  };

  const allSelected = gaps.length > 0 && selectedGapIds.length === gaps.length;
  const someSelected = selectedGapIds.length > 0 && selectedGapIds.length < gaps.length;

  if (gaps.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-gain opacity-50" />
        <p className="mt-4 text-sm font-medium text-text">No gaps found!</p>
        <p className="mt-1 text-xs text-muted-foreground">
          All trading analysis capabilities are available
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      {/* Header */}
      <div className="grid grid-cols-[auto_60px_150px_200px_80px_120px_80px_100px_auto] gap-3 border-b border-border bg-surface-muted px-4 py-3 text-xs font-medium text-muted-foreground">
        <div className="flex items-center gap-2">
          <Checkbox
            checked={allSelected || someSelected}
            onCheckedChange={toggleSelectAll}
          />
        </div>
        <div>Rank</div>
        <div>Analysis Type</div>
        <div>Missing Capability</div>
        <div>Priority</div>
        <div>Severity</div>
        <div>Effort</div>
        <div>Providers</div>
        <div className="text-right">Gap ID</div>
      </div>

      {/* Rows */}
      <div className="divide-y divide-border">
        {gaps.map((gap, index) => (
          <GapRow
            key={gap.gap_id}
            gap={gap}
            rank={index + 1}
            isExpanded={expandedId === gap.gap_id}
            isSelected={selectedGapIds.includes(gap.gap_id)}
            onToggle={() => toggleExpand(gap.gap_id)}
            onSelect={(selected) => toggleSelection(gap.gap_id, selected)}
            providerCount={providerCounts?.[gap.gap_id]}
          />
        ))}
      </div>

      {/* Selection Summary */}
      {selectedGapIds.length > 0 && (
        <div className="border-t border-border bg-primary/5 px-4 py-3 flex items-center justify-between">
          <p className="text-sm text-text">
            <span className="font-semibold">{selectedGapIds.length}</span> gap
            {selectedGapIds.length !== 1 ? "s" : ""} selected
          </p>
          <Button variant="outline" size="sm" onClick={() => toggleSelectAll(false)}>
            Clear Selection
          </Button>
        </div>
      )}
    </div>
  );
}
