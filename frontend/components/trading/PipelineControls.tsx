"use client";

import { useState } from "react";
import { Play, Zap, TrendingUp, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  usePipelineStatus,
  useTriggerStrategyResearch,
  useTriggerSignalGeneration,
  useTriggerAutoPaperTrade,
  useTriggerFullPipeline,
} from "@/lib/hooks/useAutomation";

export function PipelineControls() {
  const [isOpen, setIsOpen] = useState(false);

  const { data: status, isLoading: statusLoading } = usePipelineStatus();
  const triggerResearch = useTriggerStrategyResearch();
  const triggerSignals = useTriggerSignalGeneration();
  const triggerTrades = useTriggerAutoPaperTrade();
  const triggerFull = useTriggerFullPipeline();

  const isAnyRunning =
    triggerResearch.isPending ||
    triggerSignals.isPending ||
    triggerTrades.isPending ||
    triggerFull.isPending;

  return (
    <Card>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Pipeline Controls
            </CardTitle>
            <div className="flex items-center gap-2">
              {/* Quick Run Full Pipeline button */}
              <Button
                size="sm"
                onClick={() => triggerFull.mutate(false)}
                disabled={isAnyRunning}
              >
                <Play className="mr-1 h-4 w-4" />
                Run Full Pipeline
              </Button>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm">
                  {isOpen ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
            </div>
          </div>

          {/* Status badges */}
          {status && !statusLoading && (
            <div className="flex gap-2 mt-2">
              <Badge variant="outline">
                {status.stages.strategies.activeCount} strategies
              </Badge>
              <Badge variant="outline">
                {status.stages.signals.todayCount} signals today
              </Badge>
              <Badge variant="outline">
                {status.stages.paperTrades.openCount} open trades
              </Badge>
            </div>
          )}
        </CardHeader>

        <CollapsibleContent>
          <CardContent className="pt-0">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Stage 1: Strategy Research + Backtest */}
              <div className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <RefreshCw className="h-4 w-4 text-blue-500" />
                  <span className="font-medium">1. Research + Backtest</span>
                </div>
                <p className="text-sm text-text-muted mb-3">
                  Generate strategies, run backtests, store results
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => triggerResearch.mutate({})}
                  disabled={isAnyRunning}
                >
                  {triggerResearch.isPending ? "Running..." : "Run Research"}
                </Button>
              </div>

              {/* Stage 2: Signal Generation */}
              <div className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="h-4 w-4 text-green-500" />
                  <span className="font-medium">2. Signal Generation</span>
                </div>
                <p className="text-sm text-text-muted mb-3">
                  Evaluate strategies and generate trading signals
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => triggerSignals.mutate()}
                  disabled={isAnyRunning}
                >
                  {triggerSignals.isPending ? "Running..." : "Generate Signals"}
                </Button>
              </div>

              {/* Stage 3: Auto Paper Trading */}
              <div className="border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Play className="h-4 w-4 text-purple-500" />
                  <span className="font-medium">3. Auto Paper Trade</span>
                </div>
                <p className="text-sm text-text-muted mb-3">
                  Execute paper trades from strong signals
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => triggerTrades.mutate(5)}
                  disabled={isAnyRunning}
                >
                  {triggerTrades.isPending ? "Running..." : "Execute Trades"}
                </Button>
              </div>
            </div>

            {/* Quick actions row */}
            <div className="mt-4 pt-4 border-t flex justify-between items-center">
              <span className="text-sm text-text-muted">
                Pipeline runs automatically at 05:15, 21:30, and 21:45 UTC
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => triggerFull.mutate(true)}
                disabled={isAnyRunning}
              >
                Run Signals + Trades Only
              </Button>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}
