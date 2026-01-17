'use client'

import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { RefreshStatus } from '@/lib/api/watchlist'

interface ExpandedRowRefreshStatusProps {
  refreshStatus: RefreshStatus
  symbol: string
}

/**
 * Refresh progress indicator for watchlist expanded row
 *
 * Displays real-time progress when a watchlist item is being refreshed:
 * - Elapsed time
 * - Progress percentage
 * - Items processed count
 *
 * Extracted from ExpandedRow.tsx to reduce file size.
 */
export function ExpandedRowRefreshStatus({
  refreshStatus,
  symbol,
}: ExpandedRowRefreshStatusProps) {
  const isRefreshing =
    refreshStatus.isRefreshing && refreshStatus.currentSymbol === symbol

  if (!isRefreshing) {
    return null
  }

  return (
    <Card className="border-accent bg-accent/5">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Refreshing Scores...
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="text-sm text-text-muted">
          {refreshStatus.elapsedSeconds !== undefined && (
            <p>
              Elapsed time:{' '}
              <span className="font-medium text-text">
                {refreshStatus.elapsedSeconds}s
              </span>
            </p>
          )}
          {refreshStatus.percentComplete !== undefined && (
            <p>
              Progress:{' '}
              <span className="font-medium text-text">
                {refreshStatus.percentComplete.toFixed(0)}%
              </span>
            </p>
          )}
          {refreshStatus.processedItems !== undefined &&
            refreshStatus.totalItems !== undefined && (
              <p>
                Items processed:{' '}
                <span className="font-medium text-text">
                  {refreshStatus.processedItems} / {refreshStatus.totalItems}
                </span>
              </p>
            )}
        </div>
      </CardContent>
    </Card>
  )
}
