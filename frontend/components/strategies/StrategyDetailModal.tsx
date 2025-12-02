"use client";

import { formatDistanceToNow } from "date-fns";
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
import { ChevronDown, Archive, CheckCircle, TrendingUp, TrendingDown } from "lucide-react";
import { useState } from "react";
import { useStrategy, useUpdateStrategyStatus } from "@/lib/hooks/useStrategies";

interface StrategyDetailModalProps {
  strategyId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const statusColors: Record<string, string> = {
  testing: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  archived: "bg-gray-100 text-gray-500",
};

const pillarColors: Record<string, string> = {
  EXCELLENT: "text-green-600",
  GOOD: "text-green-500",
  FAIR: "text-yellow-500",
  POOR: "text-red-500",
  bullish: "text-green-600",
  neutral: "text-gray-500",
  bearish: "text-red-500",
  improving: "text-green-600",
  stable: "text-gray-500",
  declining: "text-red-500",
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
        request: { status: "archived", archive_reason: reason },
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-1/2" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-32 w-full" />
          </div>
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
                {strategy.symbol} &bull; {strategy.strategy_type} strategy &bull; v
                {strategy.version}
              </DialogDescription>
            </DialogHeader>

            {/* Metrics Summary */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <MetricCard
                label="Expected Sharpe"
                value={strategy.expected_sharpe?.toFixed(2) || "-"}
              />
              <MetricCard
                label="Expected Win Rate"
                value={
                  strategy.expected_win_rate != null
                    ? `${(strategy.expected_win_rate * 100).toFixed(0)}%`
                    : "-"
                }
              />
              <MetricCard
                label="Max Drawdown"
                value={
                  strategy.expected_max_drawdown != null
                    ? `${(strategy.expected_max_drawdown * 100).toFixed(1)}%`
                    : "-"
                }
              />
              <MetricCard
                label="Live Trades"
                value={strategy.live_trades_count.toString()}
              />
            </div>

            {/* Generation Reasoning */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Generation Reasoning</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-text-muted">{strategy.generation_reasoning}</p>
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
                      value={strategy.research_summary.news_sentiment_trend}
                      score={strategy.research_summary.news_sentiment_score}
                    />
                    <ResearchItem
                      label="Company Health"
                      value={strategy.research_summary.company_health}
                      score={strategy.research_summary.fundamental_score}
                    />
                    <ResearchItem
                      label="Valuation"
                      value={strategy.research_summary.valuation_tier}
                    />
                    <ResearchItem
                      label="Trend"
                      value={strategy.research_summary.trend_strength}
                    />
                    <ResearchItem
                      label="Market Regime"
                      value={strategy.research_summary.market_regime}
                    />
                    <ResearchItem
                      label="Fear & Greed"
                      value={strategy.research_summary.fear_greed_score?.toString() || "-"}
                    />
                    <ResearchItem
                      label="Sector"
                      value={strategy.research_summary.sector}
                    />
                    <ResearchItem
                      label="Sector Momentum"
                      value={strategy.research_summary.sector_momentum}
                    />
                    <ResearchItem
                      label="Confidence"
                      value={`${((strategy.research_summary.overall_confidence || 0) * 100).toFixed(0)}%`}
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
                        Walk-Forward Backtest Results ({strategy.backtest_metrics.length} windows)
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
                      {strategy.backtest_metrics.map((metric, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded border p-2 text-sm"
                        >
                          <span className="text-text-muted">
                            {metric.window_start} - {metric.window_end}
                          </span>
                          <div className="flex gap-4">
                            <span>
                              Sharpe:{" "}
                              <span
                                className={metric.sharpe > 1 ? "text-green-600" : "text-yellow-600"}
                              >
                                {metric.sharpe.toFixed(2)}
                              </span>
                            </span>
                            <span>
                              Win: {(metric.win_rate * 100).toFixed(0)}%
                            </span>
                            <span>
                              DD: {(metric.max_drawdown * 100).toFixed(1)}%
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
          <p className="text-text-muted">Strategy not found.</p>
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
