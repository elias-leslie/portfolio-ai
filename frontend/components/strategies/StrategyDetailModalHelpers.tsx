'use client'

import { ChevronDown } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { BacktestMetric, ResearchSummary } from '@/lib/api/strategies'

export const statusColors: Record<string, string> = {
  testing: 'bg-status-warning/10 text-status-warning',
  active: 'bg-status-success/10 text-status-success',
  archived: 'bg-surface-muted text-text-muted',
}

export const pillarColors: Record<string, string> = {
  excellent: 'text-status-success',
  good: 'text-status-success',
  fair: 'text-status-warning',
  poor: 'text-status-error',
  bullish: 'text-status-success',
  neutral: 'text-text-muted',
  bearish: 'text-status-error',
  improving: 'text-status-success',
  stable: 'text-text-muted',
  declining: 'text-status-error',
}

export function formatParamKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  )
}

export function ResearchItem({
  label,
  value,
  score,
}: {
  label: string
  value: string
  score?: number
}) {
  const colorClass = pillarColors[value?.toLowerCase()] || ''
  return (
    <div>
      <p className="text-xs text-text-muted">{label}</p>
      <p className={`font-medium ${colorClass}`}>
        {value || '-'}
        {score != null && (
          <span className="ml-1 text-xs">({score.toFixed(1)})</span>
        )}
      </p>
    </div>
  )
}

export function BacktestMetricRow({ metric }: { metric: BacktestMetric }) {
  return (
    <div className="flex items-center justify-between rounded border p-2 text-sm">
      <span className="text-text-muted">
        {metric.windowStart || '?'} - {metric.windowEnd || '?'}
      </span>
      <div className="flex gap-4">
        <span>
          Sharpe:{' '}
          <span
            className={
              metric.sharpe != null
                ? metric.sharpe > 1
                  ? 'text-status-success'
                  : 'text-status-warning'
                : ''
            }
          >
            {metric.sharpe?.toFixed(2) ?? '-'}
          </span>
        </span>
        <span>
          Win:{' '}
          {metric.winRate != null ? `${(metric.winRate * 100).toFixed(0)}%` : '-'}
        </span>
        <span>
          DD:{' '}
          {metric.maxDrawdown != null
            ? `${(metric.maxDrawdown * 100).toFixed(1)}%`
            : '-'}
        </span>
      </div>
    </div>
  )
}

export function ResearchGrid({ summary }: { summary: ResearchSummary }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
      <ResearchItem
        label="News Sentiment"
        value={summary.newsSentimentTrend}
        score={summary.newsSentimentScore}
      />
      <ResearchItem
        label="Company Health"
        value={summary.companyHealth}
        score={summary.fundamentalScore}
      />
      <ResearchItem label="Valuation" value={summary.valuationTier} />
      <ResearchItem label="Trend" value={summary.trendStrength} />
      <ResearchItem label="Market Regime" value={summary.marketRegime} />
      <ResearchItem
        label="Fear & Greed"
        value={summary.fearGreedScore?.toString() || '-'}
      />
      <ResearchItem label="Sector" value={summary.sector} />
      <ResearchItem label="Sector Momentum" value={summary.sectorMomentum} />
      <ResearchItem
        label="Confidence"
        value={`${((summary.overallConfidence ?? 0) * 100).toFixed(0)}%`}
      />
    </div>
  )
}

interface CollapsibleSectionProps {
  title: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

export function CollapsibleSection({
  title,
  open,
  onOpenChange,
  children,
}: CollapsibleSectionProps) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">{title}</CardTitle>
              <ChevronDown
                className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
              />
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent>{children}</CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  )
}
