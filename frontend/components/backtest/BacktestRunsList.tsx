"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { SectionCard } from "@/components/shared/SectionCard";
import { cn } from "@/lib/utils";
import type { BacktestRun } from "@/lib/api/backtest";

interface BacktestRunsListProps {
  runs: BacktestRun[];
  isLoading: boolean;
  selectedRunId: string | null;
  comparisonMode: boolean;
  selectedRunIds: Set<string>;
  onSelectRun: (runId: string) => void;
  onToggleComparison: () => void;
}

export function BacktestRunsList({
  runs,
  isLoading,
  selectedRunId,
  comparisonMode,
  selectedRunIds,
  onSelectRun,
  onToggleComparison,
}: BacktestRunsListProps) {
  // Use standard date formatting from utils (US locale: "Nov 18, 2025")
  const formatDateRange = (dateStr: string) => {
    if (!dateStr) return "-";
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return "-";
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "success";
      case "running":
        return "secondary";
      case "failed":
        return "destructive";
      default:
        return "secondary";
    }
  };

  if (isLoading) {
    return (
      <SectionCard variant="surface">
        <div className="p-4 text-center text-sm text-text-muted">Loading runs...</div>
      </SectionCard>
    );
  }

  if (runs.length === 0) {
    return (
      <SectionCard variant="surface">
        <div className="p-4 text-center text-sm text-text-muted">
          No backtests yet. Click "New Backtest" to start.
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard variant="surface" padding="sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Backtest Runs ({runs.length})</h3>
        <Button variant="ghost" size="sm" onClick={onToggleComparison}>
          {comparisonMode ? "Exit Compare" : "Compare"}
        </Button>
      </div>

      <div className="space-y-2">
        {runs.map((run) => {
          const isSelected = comparisonMode
            ? selectedRunIds.has(run.id)
            : selectedRunId === run.id;

          return (
            <button
              key={run.id}
              onClick={() => onSelectRun(run.id)}
              className={cn(
                "w-full rounded-lg border p-3 text-left transition-colors",
                isSelected
                  ? "border-primary bg-primary/10"
                  : "border-border bg-surface hover:bg-surface-muted"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {comparisonMode && (
                      <Checkbox checked={isSelected} className="pointer-events-none" />
                    )}
                    <span className="font-semibold truncate">{run.symbol}</span>
                  </div>
                  <p className="text-xs text-text-muted mt-1">
                    {formatDateRange(run.start_date)} - {formatDateRange(run.end_date)}
                  </p>
                  {run.sharpe_ratio && (
                    <p className="text-xs text-text-muted mt-1">
                      Sharpe: {typeof run.sharpe_ratio === "number" ? run.sharpe_ratio.toFixed(2) : parseFloat(String(run.sharpe_ratio)).toFixed(2)}
                    </p>
                  )}
                </div>
                <Badge variant={getStatusColor(run.status)} className="text-xs">
                  {run.status}
                </Badge>
              </div>
            </button>
          );
        })}
      </div>

      {comparisonMode && selectedRunIds.size > 0 && (
        <div className="mt-4 rounded-lg bg-primary/10 p-3 text-sm">
          <p className="font-medium">{selectedRunIds.size} runs selected</p>
          <p className="text-xs text-text-muted mt-1">
            Select 2-5 runs to compare equity curves
          </p>
        </div>
      )}
    </SectionCard>
  );
}
