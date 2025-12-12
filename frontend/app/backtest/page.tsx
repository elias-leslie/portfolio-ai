"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, Sparkles, ExternalLink } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { useBacktestRuns } from "@/lib/hooks/useBacktest";
import { useGenerateStrategiesBatch } from "@/lib/hooks/useStrategies";
import { BacktestRunsList } from "@/components/backtest/BacktestRunsList";
import { BacktestDetails } from "@/components/backtest/BacktestDetails";
import { NewBacktestDialog } from "@/components/backtest/NewBacktestDialog";
import Link from "next/link";

import { PageContainer } from "@/components/shared/PageContainer";

// Wrapper component that uses search params
function BacktestPageContent() {
  const searchParams = useSearchParams();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [newBacktestOpen, setNewBacktestOpen] = useState(false);
  const [comparisonMode, setComparisonMode] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(new Set());

  const { data: runs, isLoading } = useBacktestRuns();

  // Auto-select run from query parameter (?runId=xxx)
  useEffect(() => {
    const runIdParam = searchParams?.get("runId");
    if (runIdParam && runs && runs.length > 0 && !selectedRunId) {
      // Check if the run ID exists in the list
      const targetRun = runs.find((run) => run.id === runIdParam);
      if (targetRun) {
        setSelectedRunId(runIdParam);
      } else {
        // If specific run not found, select the first run as fallback
        // This handles cases where ?runId=first or invalid ID is passed
        if (runIdParam === "first" || runIdParam === "latest") {
          setSelectedRunId(runs[0].id);
        }
      }
    }
  }, [searchParams, runs, selectedRunId]);
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
    <PageContainer className="space-y-10 py-10">
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
    </PageContainer>
  );
}

// Main export wrapped in Suspense for useSearchParams
export default function BacktestPage() {
  return (
    <Suspense fallback={<div className="p-10">Loading...</div>}>
      <BacktestPageContent />
    </Suspense>
  );
}
