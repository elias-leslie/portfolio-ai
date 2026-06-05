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
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ExpandedRow } from '@/components/watchlist/ExpandedRow'
import {
  getRiskLevelConfig,
  getSignalDisplay,
} from '@/components/watchlist/ExpandedRowUtils'
import {
  buildTodayGate,
  DataHealthBadge,
  FreshnessBadge,
  PriceTrendStrip,
  SetupScoreFormula,
  type TodayGate,
  TodayGateBadge,
  VwapBadge,
} from '@/components/watchlist/ScannerMetricBadges'
import { getWatchlistPriceSnapshot } from '@/components/watchlist/watchlistTableUtils'
import type { MacroConditionsResponse } from '@/lib/api/macro'
import type { RefreshStatus, WatchlistItem } from '@/lib/api/watchlist'
import { cn } from '@/lib/utils'

interface WatchlistCardProps {
  item: WatchlistItem
  portfolioSymbols: Set<string>
  macroConditions?: MacroConditionsResponse
  refreshStatus?: RefreshStatus
  userTimezone: string
  onDelete: (itemId: string, symbol: string) => void
  isDeleting: boolean
}

export function WatchlistCard({
  item,
  portfolioSymbols,
  macroConditions,
  refreshStatus,
  userTimezone,
  onDelete,
  isDeleting,
}: WatchlistCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const hasScore = !!item.currentScore
  const isRefreshing =
    refreshStatus?.isRefreshing && refreshStatus.currentSymbol === item.symbol
  const riskConfig = item.riskLevel ? getRiskLevelConfig(item.riskLevel) : null
  const signalDisplay = item.signalType
    ? getSignalDisplay(item.signalType)
    : null
  const priceSnapshot = getWatchlistPriceSnapshot(
    item.currentScore?.price.metadata,
    item.quote,
  )
  const todayGate: TodayGate | undefined = buildTodayGate(macroConditions)
  const highlightedIndicators =
    item.priorityIndicators
      ?.slice()
      .sort((left, right) => right.priority - left.priority)
      .slice(0, 2) ?? []

  return (
    <div
      className={cn(
        'rounded-xl border border-border/40 bg-surface/60 p-4 shadow-sm transition-all duration-200 hover:border-border/60',
        isRefreshing && 'border-accent/40 bg-accent/5',
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/symbols/${item.symbol}?tab=decision`}
              className="text-lg font-semibold text-text underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {item.symbol}
            </Link>
            <Badge variant="outline" className="px-1.5 py-0 text-[10px]">
              Watch
            </Badge>
            {portfolioSymbols.has(item.symbol.toUpperCase()) ? (
              <Badge
                variant="outline"
                className="gap-1 border-accent/30 bg-accent/10 px-1.5 py-0 text-accent"
              >
                <Briefcase className="h-3 w-3" aria-hidden />
                <span>Held</span>
              </Badge>
            ) : null}
            {isRefreshing ? (
              <Loader2
                className="h-4 w-4 animate-spin text-accent"
                aria-label="Refreshing..."
              />
            ) : null}
            {item.scoreAlert ? (
              <AlertCircle
                className="h-4 w-4 text-accent"
                aria-label="Score changed >10 points in last 7 days"
              />
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <FreshnessBadge item={item} userTimezone={userTimezone} />
            <DataHealthBadge item={item} vwapSignal={item.vwapSignal} />
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <Button
            asChild
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-xs"
          >
            <Link href={`/symbols/${item.symbol}?tab=decision`}>Open</Link>
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
            className="h-8 w-8 p-0 text-text-muted hover:bg-loss/10 hover:text-loss"
            aria-label={`Delete ${item.symbol}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isRefreshing &&
      refreshStatus?.processedItems !== undefined &&
      refreshStatus?.totalItems !== undefined ? (
        <p className="mb-3 text-xs text-text-muted">
          Refreshing {refreshStatus.processedItems}/{refreshStatus.totalItems}
        </p>
      ) : null}

      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Price
          </p>
          {priceSnapshot ? (
            <div className="mt-1 flex items-baseline justify-between gap-3">
              <p className="text-base font-semibold text-text">
                {priceSnapshot.priceLabel}
              </p>
              {priceSnapshot.changeLabel ? (
                <p
                  className={cn(
                    'text-sm font-medium',
                    priceSnapshot.isPositiveChange ? 'text-gain' : 'text-loss',
                  )}
                >
                  {priceSnapshot.changeLabel}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="mt-1 text-sm text-text-muted">—</p>
          )}
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2.5">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Setup
          </p>
          {hasScore ? <SetupScoreFormula item={item} /> : <span>—</span>}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2.5">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Signal / Risk
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            {signalDisplay ? (
              <span
                className={cn(
                  'rounded-md border px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]',
                  signalDisplay.color,
                )}
              >
                {signalDisplay.label}
              </span>
            ) : null}
            {riskConfig ? (
              <span
                className={cn(
                  'rounded-md border border-border/35 bg-surface-muted/25 px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]',
                  riskConfig.color,
                )}
              >
                {riskConfig.label}
              </span>
            ) : null}
            <TodayGateBadge gate={todayGate} />
            {highlightedIndicators.map((indicator) => (
              <span
                key={`${indicator.category}-${indicator.label}`}
                className="rounded-md border border-border/35 bg-surface-muted/25 px-1.5 py-1 text-[10px] font-semibold text-text-muted"
                title={indicator.tooltip}
              >
                {indicator.label}
              </span>
            ))}
            {!signalDisplay &&
            !riskConfig &&
            !todayGate &&
            highlightedIndicators.length === 0 ? (
              <span className="text-sm text-text-muted">—</span>
            ) : null}
          </div>
        </div>

        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2.5">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Trend / VWAP
          </p>
          {hasScore ? (
            <div className="space-y-2">
              <PriceTrendStrip trends={item.priceTrends} compact />
              <VwapBadge signal={item.vwapSignal} />
            </div>
          ) : (
            <span className="text-sm text-text-muted">—</span>
          )}
        </div>
      </div>

      {isExpanded ? (
        <div className="mt-4 border-t border-border pt-4">
          <ExpandedRow
            item={item}
            refreshStatus={refreshStatus}
            todayGate={todayGate}
          />
        </div>
      ) : null}
    </div>
  )
}
