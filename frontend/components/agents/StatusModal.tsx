'use client'

import { Activity, CheckCircle2, Clock, Cpu, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  useRunHistory,
  useTelemetrySummary,
} from '@/lib/hooks/useAgentTelemetry'
import { cn } from '@/lib/utils'

interface StatusModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function StatusModal({ open, onOpenChange }: StatusModalProps) {
  const [days, setDays] = useState(7)
  const { data: summary, isLoading: summaryLoading } = useTelemetrySummary(days)
  const { data: historyData, isLoading: historyLoading } = useRunHistory({
    limit: 20,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col bg-bg text-text border-border">
        <DialogHeader className="border-b border-border pb-4">
          <DialogTitle>Agent Status</DialogTitle>
        </DialogHeader>

        {/* Period selector */}
        <div className="flex gap-1 py-2">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                'px-3 py-1 rounded-md text-xs transition-colors',
                days === d
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-surface text-text-muted hover:bg-surface-muted',
              )}
            >
              {d}d
            </button>
          ))}
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 gap-3 py-2">
          <MetricCard
            title="Total Runs"
            value={summary?.totalRuns ?? 0}
            icon={<Activity className="h-4 w-4 text-primary" />}
            loading={summaryLoading}
          />
          <MetricCard
            title="Success Rate"
            value={`${summary?.successRate?.toFixed(1) ?? 0}%`}
            icon={<CheckCircle2 className="h-4 w-4 text-gain" />}
            loading={summaryLoading}
            valueColor={
              (summary?.successRate ?? 0) >= 90
                ? 'text-gain'
                : (summary?.successRate ?? 0) >= 70
                  ? 'text-warning'
                  : 'text-loss'
            }
          />
          <MetricCard
            title="Total Tokens"
            value={formatNumber(summary?.totalTokens ?? 0)}
            icon={<Cpu className="h-4 w-4 text-accent" />}
            loading={summaryLoading}
          />
          <MetricCard
            title="Avg Duration"
            value={formatDuration(summary?.avgDurationMs ?? 0)}
            icon={<Clock className="h-4 w-4 text-warning" />}
            loading={summaryLoading}
          />
        </div>

        {/* Provider breakdown */}
        {!summaryLoading &&
          summary?.byProvider &&
          summary.byProvider.length > 0 && (
            <div className="border-t border-border pt-3">
              <h4 className="text-xs text-text-muted mb-2">By Provider</h4>
              <div className="space-y-2">
                {summary.byProvider.map((provider) => (
                  <div
                    key={provider.provider}
                    className="flex items-center justify-between p-2 bg-surface/50 rounded text-xs"
                  >
                    <Badge variant="outline" className="capitalize text-xs">
                      {provider.provider}
                    </Badge>
                    <div className="flex gap-4 text-text-muted">
                      <span>{provider.totalRuns} runs</span>
                      <span
                        className={
                          provider.successRate >= 90
                            ? 'text-gain'
                            : provider.successRate >= 70
                              ? 'text-warning'
                              : 'text-loss'
                        }
                      >
                        {provider.successRate.toFixed(0)}%
                      </span>
                      <span>{formatNumber(provider.totalTokens)} tok</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        {/* Recent Runs */}
        <div className="flex-1 overflow-y-auto border-t border-border pt-3 mt-2">
          <h4 className="text-xs text-text-muted mb-2">Recent Runs</h4>
          {historyLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-10 w-full animate-pulse bg-surface rounded"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {historyData?.runs.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between p-2 bg-surface/30 rounded text-xs"
                >
                  <div className="flex items-center gap-2">
                    {run.status === 'completed' ? (
                      <CheckCircle2 className="h-3 w-3 text-gain" />
                    ) : (
                      <XCircle className="h-3 w-3 text-loss" />
                    )}
                    <span className="text-text">{run.agentType}</span>
                    <Badge
                      variant="secondary"
                      className="text-[10px] px-1 py-0"
                    >
                      {run.provider ?? 'unknown'}
                    </Badge>
                  </div>
                  <div className="flex gap-3 text-text-muted">
                    <span>
                      {run.durationMs ? formatDuration(run.durationMs) : '-'}
                    </span>
                    <span>{formatDate(run.startedAt)}</span>
                  </div>
                </div>
              ))}
              {historyData?.runs.length === 0 && (
                <p className="text-text-muted text-center py-4 text-xs">
                  No runs yet
                </p>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// Helper Components
function MetricCard({
  title,
  value,
  icon,
  loading,
  valueColor,
}: {
  title: string
  value: string | number
  icon: React.ReactNode
  loading?: boolean
  valueColor?: string
}) {
  if (loading) {
    return (
      <div className="p-3 bg-surface rounded-lg">
        <div className="h-4 w-20 animate-pulse bg-surface-muted rounded mb-2" />
        <div className="h-6 w-16 animate-pulse bg-surface-muted rounded" />
      </div>
    )
  }

  return (
    <div className="p-3 bg-surface rounded-lg">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-text-muted">{title}</span>
      </div>
      <div className={cn('text-lg font-semibold', valueColor || 'text-text')}>
        {value}
      </div>
    </div>
  )
}

// Helper functions
function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

function formatDuration(ms: number): string {
  if (ms >= 60000) return `${(ms / 60000).toFixed(1)}m`
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return isoString
  }
}
