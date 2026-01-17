'use client'

import { CheckCircle2, TrendingUp, XCircle } from 'lucide-react'
import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { PaperTrade } from '@/lib/api/paper-trades'
import { formatDate } from '@/lib/utils'

interface TradeDetailsProps {
  trade: PaperTrade
}

export function TradeDetails({ trade }: TradeDetailsProps) {
  const getRiskBadgeVariant = (risk: string | undefined) => {
    if (!risk) return 'secondary'
    switch (risk.toLowerCase()) {
      case 'low':
        return 'success'
      case 'medium':
        return 'secondary'
      case 'high':
        return 'destructive'
      default:
        return 'secondary'
    }
  }

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
            {trade.thesis || 'No thesis available for this trade.'}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {trade.confidenceScore !== undefined && (
              <Badge variant="secondary">
                Confidence: {(trade.confidenceScore * 100).toFixed(0)}%
              </Badge>
            )}
            {trade.riskLevel && (
              <Badge variant={getRiskBadgeVariant(trade.riskLevel)}>
                Risk: {trade.riskLevel}
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Agent Approval Section */}
      {(trade.strategyAgentApproved !== undefined ||
        trade.riskAgentApproved !== undefined) && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">AI Agent Approval</h4>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {/* Strategy Agent */}
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Strategy Agent</span>
                {trade.strategyAgentApproved ? (
                  <CheckCircle2 className="h-5 w-5 text-gain" />
                ) : (
                  <XCircle className="h-5 w-5 text-loss" />
                )}
              </div>
              <p className="mt-1 text-xs text-text-muted">
                {trade.strategyAgentApproved
                  ? 'Approved based on backtest analysis'
                  : 'Not approved'}
              </p>
            </div>

            {/* Risk Agent */}
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Risk Agent</span>
                {trade.riskAgentApproved ? (
                  <CheckCircle2 className="h-5 w-5 text-gain" />
                ) : (
                  <XCircle className="h-5 w-5 text-loss" />
                )}
              </div>
              <p className="mt-1 text-xs text-text-muted">
                {trade.riskAgentApproved
                  ? 'Risk parameters within acceptable range'
                  : 'Not approved'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Backtest Metrics Section */}
      {(trade.backtestSharpe != null ||
        trade.backtestWinRate != null ||
        trade.backtestMaxDrawdown != null) && (
        <div>
          <h4 className="mb-2 text-sm font-semibold">
            Backtest Validation Metrics
          </h4>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {trade.backtestSharpe != null && (
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="text-xs text-text-muted">Sharpe Ratio</p>
                <p className="mt-1 text-lg font-semibold">
                  {trade.backtestSharpe.toFixed(2)}
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {trade.backtestSharpe >= 1.0 ? 'Good' : 'Below threshold'}
                </p>
              </div>
            )}

            {trade.backtestWinRate != null && (
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="text-xs text-text-muted">Win Rate</p>
                <p className="mt-1 text-lg font-semibold">
                  {(trade.backtestWinRate * 100).toFixed(1)}%
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {trade.backtestWinRate >= 0.5 ? 'Above 50%' : 'Below 50%'}
                </p>
              </div>
            )}

            {trade.backtestMaxDrawdown != null && (
              <div className="rounded-lg border border-border bg-surface p-3">
                <p className="text-xs text-text-muted">Max Drawdown</p>
                <p className="mt-1 text-lg font-semibold text-loss">
                  {(trade.backtestMaxDrawdown * 100).toFixed(1)}%
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {Math.abs(trade.backtestMaxDrawdown) <= 0.2
                    ? 'Within limits'
                    : 'High risk'}
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
            <p className="font-medium">{formatDate(trade.entryDate)}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Agent Run ID</p>
            <p className="truncate font-mono text-xs">
              {trade.agentRunId.slice(0, 8)}...
            </p>
          </div>
          {trade.workflowId && (
            <div>
              <p className="text-xs text-text-muted">Workflow ID</p>
              <p className="truncate font-mono text-xs">
                {trade.workflowId.slice(0, 8)}...
              </p>
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
        {trade.workflowId && (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/backtest?workflow=${trade.workflowId}`}>
              View Full Backtest
            </Link>
          </Button>
        )}
      </div>
    </div>
  )
}
