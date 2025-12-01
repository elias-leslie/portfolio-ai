"use client";

import { CheckCircle2, XCircle, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import type { PaperTrade } from "@/lib/api/paper-trades";
import { formatDate } from "@/lib/utils";

interface TradeDetailsProps {
  trade: PaperTrade;
}

export function TradeDetails({ trade }: TradeDetailsProps) {

  const getRiskBadgeVariant = (risk: string | undefined) => {
    if (!risk) return "secondary";
    switch (risk.toLowerCase()) {
      case "low":
        return "success";
      case "medium":
        return "secondary";
      case "high":
        return "destructive";
      default:
        return "secondary";
    }
  };

  return (
    <div className="space-y-6 py-4">
      {/* AI Thesis Section */}
      <div>
        <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
          <TrendingUp className="h-4 w-4" />
          AI Investment Thesis
        </h4>
        <div className="rounded-lg bg-surface p-4">
          <p className="text-sm text-text-muted">
            {trade.thesis || "No thesis available for this trade."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {trade.confidence_score !== undefined && (
              <Badge variant="secondary">
                Confidence: {(trade.confidence_score * 100).toFixed(0)}%
              </Badge>
            )}
            {trade.risk_level && (
              <Badge variant={getRiskBadgeVariant(trade.risk_level)}>
                Risk: {trade.risk_level}
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Agent Approval Section */}
      {(trade.strategy_agent_approved !== undefined ||
        trade.risk_agent_approved !== undefined) && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">AI Agent Approval</h4>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {/* Strategy Agent */}
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Strategy Agent</span>
                {trade.strategy_agent_approved ? (
                  <CheckCircle2 className="h-5 w-5 text-gain" />
                ) : (
                  <XCircle className="h-5 w-5 text-loss" />
                )}
              </div>
              <p className="mt-1 text-xs text-text-muted">
                {trade.strategy_agent_approved
                  ? "Approved based on backtest analysis"
                  : "Not approved"}
              </p>
            </div>

            {/* Risk Agent */}
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Risk Agent</span>
                {trade.risk_agent_approved ? (
                  <CheckCircle2 className="h-5 w-5 text-gain" />
                ) : (
                  <XCircle className="h-5 w-5 text-loss" />
                )}
              </div>
              <p className="mt-1 text-xs text-text-muted">
                {trade.risk_agent_approved
                  ? "Risk parameters within acceptable range"
                  : "Not approved"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Backtest Metrics Section */}
      {(trade.backtest_sharpe != null ||
        trade.backtest_win_rate != null ||
        trade.backtest_max_drawdown != null) && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">Backtest Validation Metrics</h4>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {trade.backtest_sharpe != null && (
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="text-xs text-text-muted">Sharpe Ratio</p>
                <p className="mt-1 text-lg font-semibold">
                  {trade.backtest_sharpe.toFixed(2)}
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {trade.backtest_sharpe >= 1.0 ? "Good" : "Below threshold"}
                </p>
              </div>
            )}

            {trade.backtest_win_rate != null && (
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="text-xs text-text-muted">Win Rate</p>
                <p className="mt-1 text-lg font-semibold">
                  {(trade.backtest_win_rate * 100).toFixed(1)}%
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {trade.backtest_win_rate >= 0.5 ? "Above 50%" : "Below 50%"}
                </p>
              </div>
            )}

            {trade.backtest_max_drawdown != null && (
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="text-xs text-text-muted">Max Drawdown</p>
                <p className="mt-1 text-lg font-semibold text-loss">
                  {(trade.backtest_max_drawdown * 100).toFixed(1)}%
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {Math.abs(trade.backtest_max_drawdown) <= 0.2
                    ? "Within limits"
                    : "High risk"}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Entry Details Section */}
      <div>
        <h4 className="mb-2 text-sm font-semibold">Entry Details</h4>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg bg-surface p-3 text-sm md:grid-cols-4">
          <div>
            <p className="text-xs text-text-muted">Entry Date</p>
            <p className="font-medium">{formatDate(trade.entry_date)}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Agent Run ID</p>
            <p className="truncate font-mono text-xs">{trade.agent_run_id.slice(0, 8)}...</p>
          </div>
          {trade.workflow_id && (
            <div>
              <p className="text-xs text-text-muted">Workflow ID</p>
              <p className="truncate font-mono text-xs">{trade.workflow_id.slice(0, 8)}...</p>
            </div>
          )}
          <div>
            <p className="text-xs text-text-muted">Triggered By</p>
            <p className="font-medium">Autonomous Agent</p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        {trade.workflow_id && (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/backtest?workflow=${trade.workflow_id}`}>View Full Backtest</Link>
          </Button>
        )}
      </div>
    </div>
  );
}
