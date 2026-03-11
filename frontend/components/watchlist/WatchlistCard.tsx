'use client'

import { AlertCircle, Briefcase, ChevronDown, ChevronRight, Loader2, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sparkline } from '@/components/ui/sparkline'
import { ExpandedRow } from '@/components/watchlist/ExpandedRow'
import { getDataQualityBgColor, getDataQualityColor, getRiskLevelConfig } from '@/components/watchlist/ExpandedRowUtils'
import { SourceBadge } from '@/components/watchlist/SourceBadge'
import { formatDate } from '@/components/watchlist/watchlistTableUtils'
import type { RefreshStatus, WatchlistItem } from '@/lib/api/watchlist'
import { cn } from '@/lib/utils'

interface WatchlistCardProps {
  item: WatchlistItem
  portfolioSymbols: Set<string>
  refreshStatus?: RefreshStatus
  userTimezone: string
  onDelete: (itemId: string, symbol: string) => void
  isDeleting: boolean
}

// Get score badge variant based on score value
const getScoreBadgeVariant = (
  score: number,
): 'viz-0' | 'viz-1' | 'viz-2' | 'viz-3' | 'viz-4' | 'viz-5' => {
  if (score >= 80) return 'viz-5'
  if (score >= 60) return 'viz-4'
  if (score >= 40) return 'viz-3'
  if (score >= 20) return 'viz-2'
  if (score >= 10) return 'viz-1'
  return 'viz-0'
}

export function WatchlistCard({
  item,
  portfolioSymbols,
  refreshStatus,
  userTimezone,
  onDelete,
  isDeleting,
}: WatchlistCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const hasScore = !!item.currentScore
  const overall = item.currentScore?.overall ?? 0
  const priceScore = item.currentScore?.price.score ?? 0
  const techScore = item.currentScore?.technical.score ?? 0
  const priceStale = item.currentScore?.price.stale ?? false
  const techStale = item.currentScore?.technical.stale ?? false
  const isRefreshing =
    refreshStatus?.isRefreshing && refreshStatus.currentSymbol === item.symbol
  const latestUpdatedAt = item.currentScore?.price.updatedAt ?? item.updatedAt
  const riskConfig = item.riskLevel ? getRiskLevelConfig(item.riskLevel) : null

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-surface p-4 shadow-sm',
        isRefreshing && 'border-accent/40 bg-accent/5',
      )}
    >
      {/* Card Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Link
              href={`/symbols/${item.symbol}`}
              className="text-lg font-semibold text-text underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {item.symbol}
            </Link>
            {portfolioSymbols.has(item.symbol.toUpperCase()) && (
              <Badge
                variant="outline"
                className="gap-1 text-xs px-1.5 py-0 h-5 bg-accent/10 border-accent/30 text-accent"
              >
                <Briefcase className="h-3 w-3" />
                <span>Portfolio</span>
              </Badge>
            )}
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin text-accent" aria-label="Refreshing..." />
            ) : null}
            {item.scoreAlert && (
              <AlertCircle
                className="h-4 w-4 text-accent"
                aria-label="Score changed >10 points in last 7 days"
              />
            )}
          </div>
          {item.currentScore?.price.metadata?.source &&
          typeof item.currentScore.price.metadata.source === 'string' ? (
            <SourceBadge
              source={item.currentScore.price.metadata.source}
              stale={item.currentScore.price.stale}
              priority={
                typeof item.currentScore.price.metadata.priority === 'number'
                  ? item.currentScore.price.metadata.priority
                  : undefined
              }
            />
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          <Button asChild variant="ghost" size="sm" className="h-8 px-2 text-xs">
            <Link href={`/symbols/${item.symbol}`}>Workspace</Link>
          </Button>
          <Button
            data-testid="watchlist-card-expand"
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-8 w-8 p-0"
            aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
            aria-expanded={isExpanded}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(item.id, item.symbol)}
            disabled={isDeleting}
            className="h-8 w-8 p-0 text-loss hover:bg-loss/10"
            aria-label={`Delete ${item.symbol}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
        {riskConfig ? (
          <span className={cn('font-medium', riskConfig.color)}>
            {riskConfig.icon} {riskConfig.label}
          </span>
        ) : null}
        {item.dataQuality ? (
          <span
            className={cn(
              'rounded-md px-2 py-1 font-semibold',
              getDataQualityBgColor(item.dataQuality.overallPct),
              getDataQualityColor(item.dataQuality.overallPct),
            )}
          >
            DQ {item.dataQuality.overallPct.toFixed(0)}%
          </span>
        ) : null}
        {isRefreshing && refreshStatus?.processedItems !== undefined && refreshStatus?.totalItems !== undefined ? (
          <span>
            Refreshing {refreshStatus.processedItems}/{refreshStatus.totalItems}
          </span>
        ) : null}
      </div>

      {/* Score Grid */}
      <div className="mb-3 grid grid-cols-3 gap-3">
        <div>
          <p className="mb-1 text-xs text-text-muted">Overall</p>
          {hasScore ? (
            <Badge variant={getScoreBadgeVariant(overall)} className="text-sm">
              {overall.toFixed(1)}
            </Badge>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </div>
        <div>
          <p className="mb-1 text-xs text-text-muted">Price</p>
          {hasScore ? (
            <div className="flex flex-col gap-0.5">
              <Badge
                variant={getScoreBadgeVariant(priceScore)}
                className="text-sm"
              >
                {priceScore.toFixed(1)}
              </Badge>
              {priceStale && (
                <span className="text-xs text-text-muted">(stale)</span>
              )}
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </div>
        <div>
          <p className="mb-1 text-xs text-text-muted">Technical</p>
          {hasScore ? (
            <div className="flex flex-col gap-0.5">
              <Badge
                variant={getScoreBadgeVariant(techScore)}
                className="text-sm"
              >
                {techScore.toFixed(1)}
              </Badge>
              {techStale && (
                <span className="text-xs text-text-muted">(stale)</span>
              )}
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </div>
      </div>

      {/* 7-Day Trend */}
      {hasScore && (
        <div className="mb-2">
          <p className="mb-1 text-xs text-text-muted">7-Day Trend</p>
          <Sparkline
            data={[65, 68, 72, 70, 73, 71, overall]}
            width={120}
            height={32}
          />
        </div>
      )}

      {/* Updated Timestamp */}
      <p className="text-xs text-text-muted">
        Updated {formatDate(latestUpdatedAt, userTimezone)}
      </p>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="mt-4 border-t border-border pt-4">
          <ExpandedRow item={item} />
        </div>
      )}
    </div>
  )
}
