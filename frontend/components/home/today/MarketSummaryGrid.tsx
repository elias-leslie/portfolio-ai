'use client'

import { useMemo } from 'react'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import {
  DEFAULT_MARKET_TIMEFRAME,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import { describeMarketPositioning } from '@/components/portfolio/investing-language'
import { Badge } from '@/components/ui/badge'
import type { MarketIntelligenceResponse } from '@/lib/api/market'
import {
  useMarketStatus,
  useSectorHistory,
} from '@/lib/hooks/useMarketIntelligence'

function formatAsOfTimestamp(value?: string | null) {
  if (!value) return 'Market update time unavailable'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Market update time unavailable'
  return `Intraday/current as of ${parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}`
}

function sectorSummaryText(
  sectors: { name: string; currentPct: number }[],
  fallback: string,
) {
  if (sectors.length === 0) return fallback
  return sectors
    .map(
      (sector) =>
        `${sector.name} ${sector.currentPct >= 0 ? '+' : ''}${sector.currentPct.toFixed(1)}%`,
    )
    .join(' · ')
}

export function MarketSummaryGrid({
  market,
}: {
  market: MarketIntelligenceResponse | undefined
}) {
  const {
    data: sectorHistory,
    isLoading: isSectorHistoryLoading,
    error: sectorHistoryError,
  } = useSectorHistory(timeframeToDays(DEFAULT_MARKET_TIMEFRAME))
  const { data: marketStatus } = useMarketStatus()
  const positioning = describeMarketPositioning(market?.indicators.putcall, {
    marketIsOpen: marketStatus?.isOpen ?? false,
  })
  const marketUpdatedLabel = formatAsOfTimestamp(market?.lastUpdated)
  // Defensive sort: backend currently sorts by currentPct desc, but trusting that
  // implicit contract silently swaps leaders/laggards if the backend ever changes.
  const sortedSectors = useMemo(() => {
    if (!sectorHistory?.sectors) return []
    return [...sectorHistory.sectors].sort(
      (a, b) => (b.currentPct ?? 0) - (a.currentPct ?? 0),
    )
  }, [sectorHistory?.sectors])
  const leadingAreas = useMemo(() => {
    if (isSectorHistoryLoading) return 'Updating sector leaders...'
    if (sectorHistoryError) return 'Unable to rank sectors right now'
    return sectorSummaryText(sortedSectors.slice(0, 3), 'Still populating')
  }, [isSectorHistoryLoading, sortedSectors, sectorHistoryError])
  const laggingAreas = useMemo(() => {
    if (isSectorHistoryLoading) return 'Updating sector laggards...'
    if (sectorHistoryError) return 'Unable to rank sectors right now'
    return sectorSummaryText(
      sortedSectors.slice(-3).reverse(),
      'Still populating',
    )
  }, [isSectorHistoryLoading, sortedSectors, sectorHistoryError])

  return (
    <section className="@container rounded-2xl border border-border/35 bg-surface/35 p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Market
          </p>
          {market?.narrative ? (
            <h3 className="mt-1 text-sm font-medium leading-5 text-text">
              {market.narrative}
            </h3>
          ) : null}
        </div>
        <div className="flex max-w-full flex-wrap gap-2">
          <Badge
            variant={positioning.label === 'Stale' ? 'warning' : 'outline'}
            title={positioning.detail}
          >
            Positioning: {positioning.label}
          </Badge>
          <Badge variant="outline">{marketUpdatedLabel}</Badge>
          <MarketStatusBadge />
        </div>
      </div>

      <div className="mt-3 grid gap-2 @[32rem]:grid-cols-2">
        <div className="rounded-2xl border border-border/30 bg-background/20 px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Leading Areas
          </p>
          <p className="mt-1.5 text-[12px] font-medium leading-5 text-text">
            {leadingAreas}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-background/20 px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Lagging Areas
          </p>
          <p className="mt-1.5 text-[12px] font-medium leading-5 text-text">
            {laggingAreas}
          </p>
        </div>
      </div>
    </section>
  )
}
