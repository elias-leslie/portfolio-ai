'use client'

import {
  Activity,
  CheckCircle2,
  Clock,
  Cpu,
  DollarSign,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AgentStats } from '@/lib/api/status'
import { useTelemetrySummary } from '@/lib/hooks/useAgentTelemetry'

interface AgentStatsCardProps {
  stats: AgentStats | undefined
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

export function AgentStatsCard({ stats }: AgentStatsCardProps) {
  // Fetch telemetry for token usage (7 day summary)
  const { data: telemetry } = useTelemetrySummary(7)

  if (!stats && !telemetry) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Agent Execution Stats
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No agent statistics available
          </p>
        </CardContent>
      </Card>
    )
  }

  const successRate =
    stats && stats.totalRuns > 0
      ? ((stats.completedRuns / stats.totalRuns) * 100).toFixed(1)
      : telemetry
        ? telemetry.successRate.toFixed(1)
        : '0.0'

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 80) return 'text-gain'
    if (rate >= 50) return 'text-warning'
    return 'text-loss'
  }

  const rate = parseFloat(successRate)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Agent Execution Stats
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Total Runs */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-medium">Total Runs</p>
            </div>
            <p className="text-2xl font-bold">
              {stats?.totalRuns ?? telemetry?.totalRuns ?? 0}
            </p>
          </div>

          {/* Success Rate */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2
                className={`h-4 w-4 ${getSuccessRateColor(rate)}`}
              />
              <p className="text-sm font-medium">Success Rate</p>
            </div>
            <p className={`text-2xl font-bold ${getSuccessRateColor(rate)}`}>
              {successRate}%
            </p>
          </div>

          {/* Completed Runs */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-gain" />
              <p className="text-sm font-medium">Completed</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-xl font-semibold">
                {stats?.completedRuns ?? telemetry?.successfulRuns ?? 0}
              </p>
              <Badge variant="success" className="text-xs">
                Success
              </Badge>
            </div>
          </div>

          {/* Failed Runs */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-loss" />
              <p className="text-sm font-medium">Failed</p>
            </div>
            <div className="flex items-center gap-2">
              <p className="text-xl font-semibold">
                {stats?.failedRuns ?? telemetry?.failedRuns ?? 0}
              </p>
              <Badge variant="destructive" className="text-xs">
                Failed
              </Badge>
            </div>
          </div>

          {/* Average Duration */}
          {(stats?.avgDurationS !== undefined ||
            telemetry?.avgDurationMs !== undefined) && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Avg Duration</p>
              </div>
              <p className="text-lg font-semibold">
                {stats?.avgDurationS !== undefined
                  ? `${stats.avgDurationS.toFixed(1)}s`
                  : telemetry?.avgDurationMs !== undefined
                    ? `${(telemetry.avgDurationMs / 1000).toFixed(1)}s`
                    : 'N/A'}
              </p>
            </div>
          )}

          {/* Average Cost */}
          {stats?.avgCostUsd !== undefined && stats?.avgCostUsd !== null && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Avg Cost</p>
              </div>
              <p className="text-lg font-semibold">
                ${stats.avgCostUsd.toFixed(4)}
              </p>
            </div>
          )}

          {/* Total Tokens (7d) */}
          {telemetry && (
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Tokens (7d)</p>
              </div>
              <p className="text-lg font-semibold">
                {formatNumber(telemetry.totalTokens)}
              </p>
            </div>
          )}
        </div>

        <div className="mt-4 border-t pt-4 text-sm text-muted-foreground">
          Agent activity is summarized here for observability. Interactive
          agent tooling is not exposed in the Portfolio AI UI.
        </div>
      </CardContent>
    </Card>
  )
}
