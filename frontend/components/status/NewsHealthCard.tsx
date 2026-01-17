'use client'

import { Newspaper, RefreshCw } from 'lucide-react'
import { useMemo } from 'react'
import { ExpandableCard } from '@/components/status/ExpandableCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { NewsHealthResponse } from '@/lib/api/news'

interface NewsHealthCardProps {
  newsHealth: NewsHealthResponse | null
  newsHealthLoading: boolean
  newsHealthError: Error | null
  finbertStatus: {
    label: string
    variant: 'default' | 'destructive' | 'secondary'
  }
  onRefresh: () => void
}

export function NewsHealthCard({
  newsHealth,
  newsHealthLoading,
  newsHealthError,
  finbertStatus,
  onRefresh,
}: NewsHealthCardProps) {
  // Format date helper
  const formatDateTime = (value?: string | null) =>
    value ? new Date(value).toLocaleString() : '—'

  // Calculate derived values - memoized to avoid impure render
  const lookbackHours = useMemo(() => {
    if (!newsHealth) return 24
    // eslint-disable-next-line react-hooks/purity -- Date.now() is intentionally used for display-only age calculation
    const now = Date.now()
    return Math.round(
      (now - new Date(newsHealth.marketLastRefreshedAt || 0).getTime()) /
        3600000,
    )
  }, [newsHealth])

  const fallbackRatePercent =
    newsHealth && newsHealth.headlines24H > 0
      ? (newsHealth.fallbackHeadlines24H / newsHealth.headlines24H) * 100
      : 0

  const fallbackAvgLatency = newsHealth?.fallbackAvgLatencyMs24H ?? null
  const fallbackP95Latency = newsHealth?.fallbackP95LatencyMs24H ?? null
  const fallbackLastEventAt = newsHealth?.fallbackLastEventAt ?? null

  // Build summary text
  const summary = (() => {
    if (newsHealthError) {
      return newsHealthError.message || 'Failed to load telemetry'
    }
    if (newsHealthLoading && !newsHealth) {
      return 'Loading telemetry...'
    }
    if (!newsHealth) {
      return 'Waiting for news telemetry'
    }
    const fallbackCount = newsHealth.fallbackHeadlines24H ?? 0
    const fallbackSummary =
      fallbackCount > 0 ? `${fallbackCount} fallback` : 'No fallback'
    return `${newsHealth.headlines24H ?? 0} headlines • ${fallbackSummary} • ${finbertStatus.label}`
  })()

  return (
    <ExpandableCard
      title={
        <div className="flex items-center gap-2">
          <Newspaper className="h-5 w-5" />
          <span>News Health</span>
        </div>
      }
      description="FinBERT availability and cache freshness for the News surface."
      summary={summary}
      defaultCollapsed
      actions={
        <div className="flex items-center gap-2">
          <Badge variant={finbertStatus.variant}>{finbertStatus.label}</Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={newsHealthLoading}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      }
    >
      {newsHealthError ? (
        <Alert variant="destructive">
          <AlertTitle>Failed to load news health</AlertTitle>
          <AlertDescription>
            {newsHealthError.message || 'Unable to reach /api/news/health'}
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Market Last Refresh
            </p>
            <p className="text-sm font-medium">
              {newsHealthLoading && !newsHealth
                ? 'Loading...'
                : formatDateTime(newsHealth?.marketLastRefreshedAt)}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Watchlist Last Refresh
            </p>
            <p className="text-sm font-medium">
              {newsHealthLoading && !newsHealth
                ? 'Loading...'
                : formatDateTime(newsHealth?.watchlistLastRefreshedAt)}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Headlines (24h)
            </p>
            <p className="text-sm font-medium">
              {newsHealth?.headlines24H ?? 0}
            </p>
            <p className="text-xs text-muted-foreground">
              Lookback window: {lookbackHours} hrs
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Fallback Usage (24h)
            </p>
            <p className="text-sm font-medium">
              {newsHealth?.fallbackHeadlines24H ?? 0} headlines
            </p>
            <p className="text-xs text-muted-foreground">
              {newsHealth
                ? `${fallbackRatePercent.toFixed(1)}% fallback`
                : '0% fallback'}
            </p>
            {fallbackAvgLatency !== null && (
              <p className="text-xs text-muted-foreground">
                Avg latency: {Math.round(fallbackAvgLatency)} ms
              </p>
            )}
            {fallbackP95Latency !== null && (
              <p className="text-xs text-muted-foreground">
                P95 latency: {Math.round(fallbackP95Latency)} ms
              </p>
            )}
            {fallbackLastEventAt && (
              <p className="text-xs text-muted-foreground">
                Last fallback: {formatDateTime(fallbackLastEventAt)}
              </p>
            )}
          </div>
        </div>
      )}
    </ExpandableCard>
  )
}
