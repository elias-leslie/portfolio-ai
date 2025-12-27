"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronDown, Archive, CheckCircle } from "lucide-react";
import { useState } from "react";
import { useStrategy, useUpdateStrategyStatus } from "@/lib/hooks/useStrategies";
import { SeedEvolution } from "./SeedEvolution";

interface StrategyDetailModalProps {
  strategyId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const statusColors: Record<string, string> = {
  testing: "bg-status-warning/10 text-status-warning",
  active: "bg-status-success/10 text-status-success",
  archived: "bg-surface-muted text-text-muted",
};

const pillarColors: Record<string, string> = {
  EXCELLENT: "text-status-success",
  GOOD: "text-status-success",
  FAIR: "text-status-warning",
  POOR: "text-status-error",
  bullish: "text-status-success",
  neutral: "text-text-muted",
  bearish: "text-status-error",
  improving: "text-status-success",
  stable: "text-text-muted",
  declining: "text-status-error",
};

export function StrategyDetailModal({
  strategyId,
  open,
  onOpenChange,
}: StrategyDetailModalProps) {
  const { data: strategy, isLoading } = useStrategy(strategyId);
  const updateStatus = useUpdateStrategyStatus();
  const [researchOpen, setResearchOpen] = useState(false);
  const [parametersOpen, setParametersOpen] = useState(false);
  const [backtestOpen, setBacktestOpen] = useState(false);

  const handleActivate = () => {
    if (!strategyId) return;
    updateStatus.mutate({ strategyId, request: { status: "active" } });
  };

  const handleArchive = () => {
    if (!strategyId) return;
    const reason = prompt("Enter archive reason:");
    if (reason) {
      updateStatus.mutate({
        strategyId,
        request: { status: "archived", archiveReason: reason },
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        {isLoading ? (
          <DialogHeader>
            <DialogTitle>Loading Strategy...</DialogTitle>
            <div className="space-y-4 pt-4">
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-32 w-full" />
            </div>
          </DialogHeader>
        ) : strategy ? (
          <>
            <DialogHeader>
              <div className="flex items-center gap-3">
                <DialogTitle className="text-xl">{strategy.name}</DialogTitle>
                <Badge variant="outline" className={statusColors[strategy.status]}>
                  {strategy.status}
                </Badge>
              </div>
              <DialogDescription>
                {strategy.symbol} &bull; {strategy.strategyType} strategy &bull; v
                {strategy.version}
              </DialogDescription>
            </DialogHeader>

            {/* Metrics Summary */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <MetricCard
                label="Expected Sharpe"
                value={strategy.expectedSharpe?.toFixed(2) || "-"}
              />
              <MetricCard
                label="Expected Win Rate"
                value={
                  strategy.expectedWinRate != null
                    ? `${(strategy.expectedWinRate * 100).toFixed(0)}%`
                    : "-"
                }
              />
              <MetricCard
                label="Max Drawdown"
                value={
                  strategy.expectedMaxDrawdown != null
                    ? `${(strategy.expectedMaxDrawdown * 100).toFixed(1)}%`
                    : "-"
                }
              />
              <MetricCard
                label="Live Trades"
                value={strategy.liveTradesCount.toString()}
              />
            </div>

            {/* Seed Evolution Timeline (FEAT-218) */}
            <SeedEvolution strategyId={strategy.id} />

            {/* Generation Reasoning */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Generation Reasoning</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-text-muted">{strategy.generationReasoning}</p>
              </CardContent>
            </Card>

            {/* Research Summary - Collapsible */}
            <Collapsible open={researchOpen} onOpenChange={setResearchOpen}>
              <Card>
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/50">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">Research Summary</CardTitle>
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${researchOpen ? "rotate-180" : ""}`}
                      />
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <CardContent className="grid grid-cols-2 gap-4 md:grid-cols-3">
                    <ResearchItem
                      label="News Sentiment"
                      value={strategy.researchSummary.newsSentimentTrend}
                      score={strategy.researchSummary.newsSentimentScore}
                    />
                    <ResearchItem
                      label="Company Health"
                      value={strategy.researchSummary.companyHealth}
                      score={strategy.researchSummary.fundamentalScore}
                    />
                    <ResearchItem
                      label="Valuation"
                      value={strategy.researchSummary.valuationTier}
                    />
                    <ResearchItem
                      label="Trend"
                      value={strategy.researchSummary.trendStrength}
                    />
                    <ResearchItem
                      label="Market Regime"
                      value={strategy.researchSummary.marketRegime}
                    />
                    <ResearchItem
                      label="Fear & Greed"
                      value={strategy.researchSummary.fearGreedScore?.toString() || "-"}
                    />
                    <ResearchItem
                      label="Sector"
                      value={strategy.researchSummary.sector}
                    />
                    <ResearchItem
                      label="Sector Momentum"
                      value={strategy.researchSummary.sectorMomentum}
                    />
                    <ResearchItem
                      label="Confidence"
                      value={`${((strategy.researchSummary.overallConfidence || 0) * 100).toFixed(0)}%`}
                    />
                  </CardContent>
                </CollapsibleContent>
              </Card>
            </Collapsible>

            {/* Parameters - Collapsible */}
            <Collapsible open={parametersOpen} onOpenChange={setParametersOpen}>
              <Card>
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/50">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">Strategy Parameters</CardTitle>
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${parametersOpen ? "rotate-180" : ""}`}
                      />
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
                      {Object.entries(strategy.parameters).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="text-text-muted">{formatParamKey(key)}:</span>
                          <span className="font-mono">
                            {typeof value === "number" ? value.toFixed(2) : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </CollapsibleContent>
              </Card>
            </Collapsible>

            {/* Backtest Results - Collapsible */}
            <Collapsible open={backtestOpen} onOpenChange={setBacktestOpen}>
              <Card>
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/50">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">
                        Walk-Forward Backtest Results ({strategy.backtestMetrics.length} windows)
                      </CardTitle>
                      <ChevronDown
                        className={`h-4 w-4 transition-transform ${backtestOpen ? "rotate-180" : ""}`}
                      />
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <CardContent>
                    <div className="space-y-2">
                      {strategy.backtestMetrics.map((metric, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded border p-2 text-sm"
                        >
                          <span className="text-text-muted">
                            {metric.windowStart || "?"} - {metric.windowEnd || "?"}
                          </span>
                          <div className="flex gap-4">
                            <span>
                              Sharpe:{" "}
                              <span
                                className={(metric.sharpe ?? 0) > 1 ? "text-status-success" : "text-status-warning"}
                              >
                                {metric.sharpe?.toFixed(2) ?? "-"}
                              </span>
                            </span>
                            <span>
                              Win: {metric.winRate != null ? `${(metric.winRate * 100).toFixed(0)}%` : "-"}
                            </span>
                            <span>
                              DD: {metric.maxDrawdown != null ? `${(metric.maxDrawdown * 100).toFixed(1)}%` : "-"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </CollapsibleContent>
              </Card>
            </Collapsible>

            {/* Actions */}
            <div className="flex justify-end gap-2">
              {strategy.status === "testing" && (
                <Button onClick={handleActivate} disabled={updateStatus.isPending}>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Activate
                </Button>
              )}
              {strategy.status !== "archived" && (
                <Button
                  variant="outline"
                  onClick={handleArchive}
                  disabled={updateStatus.isPending}
                >
                  <Archive className="mr-2 h-4 w-4" />
                  Archive
                </Button>
              )}
            </div>
          </>
        ) : (
          <DialogHeader>
            <DialogTitle>Strategy Not Found</DialogTitle>
            <p className="text-text-muted">The requested strategy could not be found.</p>
          </DialogHeader>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

function ResearchItem({
  label,
  value,
  score,
}: {
  label: string;
  value: string;
  score?: number;
}) {
  const colorClass = pillarColors[value?.toLowerCase()] || "";
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`font-medium ${colorClass}`}>
        {value || "-"}
        {score != null && <span className="ml-1 text-xs">({score.toFixed(1)})</span>}
      </p>
    </div>
  );
}

function formatParamKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
