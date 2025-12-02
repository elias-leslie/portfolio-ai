"use client";

import { useState } from "react";
import { Plus, Sparkles, ExternalLink } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { useBacktestRuns } from "@/lib/hooks/useBacktest";
import { useGenerateStrategiesBatch } from "@/lib/hooks/useStrategies";
import { BacktestRunsList } from "@/components/backtest/BacktestRunsList";
import { BacktestDetails } from "@/components/backtest/BacktestDetails";
import { NewBacktestDialog } from "@/components/backtest/NewBacktestDialog";
import Link from "next/link";

export default function BacktestPage() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [newBacktestOpen, setNewBacktestOpen] = useState(false);
  const [comparisonMode, setComparisonMode] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(new Set());

  const { data: runs, isLoading } = useBacktestRuns();
  const generateBatch = useGenerateStrategiesBatch();

  // Handle run selection
  const handleSelectRun = (runId: string) => {
    if (comparisonMode) {
      setSelectedRunIds((prev) => {
        const next = new Set(prev);
        if (next.has(runId)) {
          next.delete(runId);
        } else {
          if (next.size < 5) {
            next.add(runId);
          }
        }
        return next;
      });
    } else {
      setSelectedRunId(runId);
    }
  };

  // Toggle comparison mode
  const toggleComparisonMode = () => {
    if (!comparisonMode) {
      // Entering comparison mode
      setSelectedRunIds(new Set());
      setSelectedRunId(null);
    } else {
      // Exiting comparison mode
      setSelectedRunIds(new Set());
    }
    setComparisonMode(!comparisonMode);
  };

  return (
    <div className="bg-bg">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-10 sm:px-6 lg:px-8">
        {/* Page Header */}
        <PageHeader
          title="Backtesting"
          description="Strategy validation with historical data"
          size="md"
          actions={
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => generateBatch.mutate({ top_n: 20 })}
                disabled={generateBatch.isPending}
              >
                <Sparkles className="mr-2 h-4 w-4" />
                {generateBatch.isPending ? "Generating..." : "Generate Strategies"}
              </Button>
              <Link href="/strategies">
                <Button variant="ghost">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  View Strategies
                </Button>
              </Link>
              <Button onClick={() => setNewBacktestOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                New Backtest
              </Button>
            </div>
          }
        />

        {/* Two-Column Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Sidebar: Runs List */}
          <div className="lg:col-span-4 xl:col-span-3">
            <BacktestRunsList
              runs={runs || []}
              isLoading={isLoading}
              selectedRunId={selectedRunId}
              comparisonMode={comparisonMode}
              selectedRunIds={selectedRunIds}
              onSelectRun={handleSelectRun}
              onToggleComparison={toggleComparisonMode}
            />
          </div>

          {/* Main Area: Details or Comparison */}
          <div className="lg:col-span-8 xl:col-span-9">
            <BacktestDetails
              runId={selectedRunId}
              comparisonMode={comparisonMode}
              comparisonRunIds={Array.from(selectedRunIds)}
            />
          </div>
        </div>

        {/* New Backtest Dialog */}
        <NewBacktestDialog open={newBacktestOpen} onOpenChange={setNewBacktestOpen} />
      </div>
    </div>
  );
}
