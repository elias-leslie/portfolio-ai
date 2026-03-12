'use client'

import {
  AlertCircle,
  Briefcase,
  ChevronDown,
  ChevronRight,
  Loader2,
  Trash2,
} from 'lucide-react'
import Link from 'next/link'
import { Fragment } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  TableCell,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { ExpandedRow } from '@/components/watchlist/ExpandedRow'
import {
  getDataQualityBgColor,
  getDataQualityColor,
  getRiskLevelConfig,
  getScoreBadgeVariant,
} from '@/components/watchlist/ExpandedRowUtils'
import { SourceBadge } from '@/components/watchlist/SourceBadge'
import { SparklineWithHistory } from '@/components/watchlist/SparklineWithHistory'
import {
  formatDate,
  formatPillarStatus,
  getWatchlistPriceSnapshot,
} from '@/components/watchlist/watchlistTableUtils'
import type { RefreshStatus, WatchlistItem } from '@/lib/api/watchlist'
import { cn } from '@/lib/utils'

interface WatchlistTableRowProps {
  item: WatchlistItem
  isExpanded: boolean
  highlightedSymbol: string | null
  recentlyUpdatedRows: Set<string>
  changedCells: Record<string, Record<string, boolean>>
  portfolioSymbols: Set<string>
  refreshStatus: RefreshStatus | undefined
  isDeleting: boolean
  userTimezone: string
  rowRef: (el: HTMLTableRowElement | null) => void
  onToggle: () => void
  onDelete: (id: string, symbol: string) => void
}

export function WatchlistTableRow({
  item,
  isExpanded,
  highlightedSymbol,
  recentlyUpdatedRows,
  changedCells,
  portfolioSymbols,
  refreshStatus,
  isDeleting,
  userTimezone,
  rowRef,
  onToggle,
  onDelete,
}: WatchlistTableRowProps) {
  const hasScore = !!item.currentScore
  const overall = item.currentScore?.overall ?? 0
  const priceSnapshot = getWatchlistPriceSnapshot(item.currentScore?.price.metadata)

  return (
    <Fragment key={item.id}>
      <TableRow
        ref={rowRef}
        className={cn(
          'cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
          isExpanded && 'bg-surface-muted/40',
          highlightedSymbol === item.symbol && 'bg-accent/10 animate-pulse',
        )}
        role="button"
        tabIndex={0}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${item.symbol} details`}
        aria-expanded={isExpanded}
        aria-controls={`watchlist-row-${item.id}`}
        data-slot="table-row"
        data-recently-updated={
          recentlyUpdatedRows.has(item.id) ? 'true' : undefined
        }
        onClick={onToggle}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onToggle()
          }
        }}
      >
        <TableCell data-slot="table-cell">
          <button
            type="button"
            className="rounded p-1 hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            aria-label={isExpanded ? 'Collapse row' : 'Expand row'}
            onClick={(event) => {
              event.stopPropagation()
              onToggle()
            }}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
        </TableCell>
        <TableCell className="font-medium" data-slot="table-cell">
          <div className="flex items-center gap-2">
            <Link
              href={`/symbols/${item.symbol}`}
              className="rounded-sm underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              onClick={(event) => event.stopPropagation()}
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
            {refreshStatus?.isRefreshing &&
              refreshStatus.currentSymbol === item.symbol && (
                <Loader2
                  className="h-4 w-4 animate-spin text-accent"
                  aria-label="Refreshing..."
                />
              )}
            {item.scoreAlert && (
              <AlertCircle
                className="h-4 w-4 text-accent"
                aria-label="Score changed >10 points in last 7 days"
              />
            )}
          </div>
        </TableCell>
        <TableCell
          data-slot="table-cell"
          data-changed={changedCells[item.id]?.price ? 'true' : undefined}
        >
          {priceSnapshot ? (
            <div
              className="text-sm price-display"
              data-changed={
                changedCells[item.id]?.price ? 'true' : undefined
              }
            >
              <div className="font-medium">{priceSnapshot.priceLabel}</div>
              {priceSnapshot.changeLabel ? (
                <div
                  className={cn(
                    'text-xs',
                    priceSnapshot.isPositiveChange ? 'text-gain' : 'text-loss',
                  )}
                >
                  {priceSnapshot.changeLabel}
                </div>
              ) : null}
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell
          data-slot="table-cell"
          data-changed={changedCells[item.id]?.score ? 'true' : undefined}
        >
          {hasScore ? (
            <div className="flex items-center gap-2">
              <Badge
                variant={getScoreBadgeVariant(overall)}
                className="score-badge"
              >
                {overall.toFixed(0)}
              </Badge>
              <div className="flex-1 h-2 bg-surface-muted rounded-full overflow-hidden min-w-[60px]">
                <div
                  className={cn(
                    'h-full transition-all',
                    overall >= 80
                      ? 'bg-gain'
                      : overall >= 60
                        ? 'bg-warning'
                        : overall >= 40
                          ? 'bg-neutral'
                          : 'bg-loss',
                  )}
                  style={{ width: `${overall}%` }}
                />
              </div>
            </div>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell
          data-slot="table-cell"
          data-changed={changedCells[item.id]?.risk ? 'true' : undefined}
        >
          {item.riskLevel ? (
            (() => {
              const config = getRiskLevelConfig(item.riskLevel)
              return (
                <div className={cn('text-xs font-medium', config.color)}>
                  {config.icon} {config.label}
                </div>
              )
            })()
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell data-slot="table-cell">
          {item.dataQuality ? (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div
                    className={cn(
                      'inline-flex items-center justify-center rounded-md px-2 py-1 text-xs font-semibold cursor-help',
                      getDataQualityBgColor(item.dataQuality.overallPct),
                      getDataQualityColor(item.dataQuality.overallPct),
                    )}
                  >
                    {item.dataQuality.overallPct.toFixed(0)}%
                  </div>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-xs">
                  <div className="space-y-1.5">
                    <div className="font-semibold text-xs border-b border-border pb-1">
                      Data Quality Breakdown
                    </div>
                    {Object.entries(item.dataQuality.pillars).map(
                      ([pillar, data]) => (
                        <div key={pillar} className="text-xs">
                          <div className="font-medium capitalize">
                            {pillar}:
                          </div>
                          <div className="text-text-muted ml-2">
                            {formatPillarStatus(data.status)} - {data.details}
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell data-slot="table-cell">
          {hasScore ? (
            <SparklineWithHistory itemId={item.id} width={80} height={24} />
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell
          className="text-xs text-text-muted"
          data-slot="table-cell"
          data-changed={
            changedCells[item.id]?.updatedAt ? 'true' : undefined
          }
        >
          {item.currentScore?.price?.updatedAt
            ? formatDate(item.currentScore.price.updatedAt, userTimezone)
            : formatDate(item.updatedAt, userTimezone)}
        </TableCell>
        <TableCell data-slot="table-cell">
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation()
              onDelete(item.id, item.symbol)
            }}
            disabled={isDeleting}
            className="h-8 w-8 p-0"
            aria-label={`Delete ${item.symbol}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow id={`watchlist-row-${item.id}`} data-state="open">
          <TableCell colSpan={9} className="bg-surface-muted/20 p-4">
            <ExpandedRow item={item} refreshStatus={refreshStatus} />
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}
