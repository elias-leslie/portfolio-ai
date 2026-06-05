'use client'

import {
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
import { TableCell, TableRow } from '@/components/ui/table'
import { ExpandedRow } from '@/components/watchlist/ExpandedRow'
import {
  getRiskLevelConfig,
  getSignalDisplay,
} from '@/components/watchlist/ExpandedRowUtils'
import { PriceSparkline } from '@/components/watchlist/PriceSparkline'
import {
  buildTodayGate,
  ScannerStatusDot,
  ScoreAlertBadge,
  SetupScoreMeter,
  type TodayGate,
} from '@/components/watchlist/ScannerMetricBadges'
import { getWatchlistPriceSnapshot } from '@/components/watchlist/watchlistTableUtils'
import type { MacroConditionsResponse } from '@/lib/api/macro'
import type { RefreshStatus, WatchlistItem } from '@/lib/api/watchlist'
import { cn } from '@/lib/utils'

interface WatchlistTableRowProps {
  item: WatchlistItem
  isExpanded: boolean
  highlightedSymbol: string | null
  recentlyUpdatedRows: Set<string>
  changedCells: Record<string, Record<string, boolean>>
  portfolioSymbols: Set<string>
  macroConditions?: MacroConditionsResponse
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
  macroConditions,
  refreshStatus,
  isDeleting,
  userTimezone,
  rowRef,
  onToggle,
  onDelete,
}: WatchlistTableRowProps) {
  const hasScore = !!item.currentScore
  const priceSnapshot = getWatchlistPriceSnapshot(
    item.currentScore?.price.metadata,
    item.quote,
  )
  const riskConfig = item.riskLevel ? getRiskLevelConfig(item.riskLevel) : null
  const signalDisplay = item.signalType
    ? getSignalDisplay(item.signalType)
    : null
  const todayGate: TodayGate | undefined = buildTodayGate(macroConditions)

  return (
    <Fragment key={item.id}>
      <TableRow
        ref={rowRef}
        className={cn(
          'cursor-pointer transition-all duration-150 hover:bg-surface-muted/25 hover:shadow-[inset_2px_0_0_0] hover:shadow-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
          isExpanded &&
            'bg-surface-muted/30 shadow-[inset_2px_0_0_0] shadow-primary/30',
          highlightedSymbol === item.symbol && 'bg-accent/10 animate-pulse',
        )}
        data-slot="table-row"
        data-recently-updated={
          recentlyUpdatedRows.has(item.id) ? 'true' : undefined
        }
        onClick={onToggle}
      >
        <TableCell data-slot="table-cell">
          <button
            type="button"
            className="rounded p-1 hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${item.symbol} details`}
            aria-expanded={isExpanded}
            aria-controls={`watchlist-row-${item.id}`}
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
        <TableCell
          className="min-w-[18rem] max-w-[24rem] font-medium"
          data-slot="table-cell"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Link
                href={`/symbols/${item.symbol}?tab=decision`}
                className="rounded-sm font-semibold underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                onClick={(event) => event.stopPropagation()}
              >
                {item.symbol}
              </Link>
              <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
                Watch
              </Badge>
              {portfolioSymbols.has(item.symbol.toUpperCase()) && (
                <Badge
                  variant="outline"
                  className="gap-1 border-accent/30 bg-accent/10 px-1.5 py-0 text-accent"
                >
                  <Briefcase className="h-3 w-3" aria-hidden />
                  <span>Held</span>
                </Badge>
              )}
              <ScannerStatusDot item={item} userTimezone={userTimezone} />
              {refreshStatus?.isRefreshing &&
                refreshStatus.currentSymbol === item.symbol && (
                  <Loader2
                    className="h-4 w-4 animate-spin text-accent"
                    aria-label="Refreshing..."
                  />
                )}
              {item.scoreAlert && <ScoreAlertBadge />}
            </div>
            {item.companyName ? (
              <p
                className="max-w-[22rem] truncate text-xs text-text-muted"
                title={item.companyName}
              >
                {item.companyName}
              </p>
            ) : null}
            {item.narrativeHeadline ? (
              <p
                className="max-w-[22rem] truncate text-xs text-text/80"
                title={item.narrativeHeadline}
              >
                {item.narrativeHeadline}
              </p>
            ) : null}
          </div>
        </TableCell>
        <TableCell data-slot="table-cell">
          {signalDisplay ? (
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-bold uppercase tracking-[0.12em] shadow-sm',
                signalDisplay.solidColor,
              )}
            >
              <span aria-hidden>{signalDisplay.icon}</span>
              {signalDisplay.label}
            </span>
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell
          data-slot="table-cell"
          data-changed={changedCells[item.id]?.price ? 'true' : undefined}
        >
          {priceSnapshot ? (
            <div className="space-y-1">
              <div
                className="text-sm tabular-nums price-display"
                data-changed={changedCells[item.id]?.price ? 'true' : undefined}
              >
                <span className="font-medium">{priceSnapshot.priceLabel}</span>
                {priceSnapshot.changeLabel ? (
                  <span
                    className={cn(
                      'ml-1.5 text-xs',
                      priceSnapshot.isPositiveChange
                        ? 'text-gain'
                        : 'text-loss',
                    )}
                  >
                    {priceSnapshot.changeLabel}
                  </span>
                ) : null}
              </div>
              <PriceSparkline itemId={item.id} />
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
            <SetupScoreMeter item={item} />
          ) : (
            <span className="text-text-muted">—</span>
          )}
        </TableCell>
        <TableCell
          data-slot="table-cell"
          data-changed={changedCells[item.id]?.risk ? 'true' : undefined}
        >
          {riskConfig ? (
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded-md border border-border/35 bg-surface-muted/25 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.1em]',
                riskConfig.color,
              )}
            >
              {riskConfig.icon ? (
                <span aria-hidden>{riskConfig.icon}</span>
              ) : null}
              {riskConfig.label}
            </span>
          ) : (
            <span className="text-text-muted">—</span>
          )}
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
            className="h-8 w-8 p-0 text-text-muted hover:bg-loss/10 hover:text-loss"
            aria-label={`Delete ${item.symbol}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow id={`watchlist-row-${item.id}`} data-state="open">
          <TableCell colSpan={7} className="bg-surface-muted/20 p-4">
            <ExpandedRow
              item={item}
              refreshStatus={refreshStatus}
              todayGate={todayGate}
            />
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}
