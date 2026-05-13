'use client'

import { useMemo, useState } from 'react'
import { IndicatorsTrendChart } from '@/components/market/IndicatorsTrendChart'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import { SectorPerformanceChart } from '@/components/market/SectorPerformanceChart'
import { SentimentTrendChart } from '@/components/market/SentimentTrendChart'
import {
  DEFAULT_MARKET_TIMEFRAME,
  type Timeframe,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import {
  useMarketIntelligence,
  useSectorHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { describeMarketPositioning } from './investing-language'

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

export function InvestingMarketSummaryPanel() {
  const { data: market } = useMarketIntelligence()
  const {
    data: sectorHistory,
    isLoading: isSectorHistoryLoading,
    error: sectorHistoryError,
  } = useSectorHistory(timeframeToDays(DEFAULT_MARKET_TIMEFRAME))
  const positioning = describeMarketPositioning(market?.indicators.putcall)
  const marketUpdatedLabel = formatAsOfTimestamp(market?.lastUpdated)
  const leadingAreas = useMemo(() => {
    const sectors = sectorHistory?.sectors?.slice(0, 3) ?? []
    if (isSectorHistoryLoading) return 'Updating sector leaders...'
    if (sectorHistoryError) return 'Unable to rank sectors right now'
    return sectorSummaryText(sectors, 'Still populating')
  }, [isSectorHistoryLoading, sectorHistory?.sectors, sectorHistoryError])
  const laggingAreas = useMemo(() => {
    const sectors = sectorHistory?.sectors
      ? [...sectorHistory.sectors].slice(-3).reverse()
      : []
    if (isSectorHistoryLoading) return 'Updating sector laggards...'
    if (sectorHistoryError) return 'Unable to rank sectors right now'
    return sectorSummaryText(sectors, 'Still populating')
  }, [isSectorHistoryLoading, sectorHistory?.sectors, sectorHistoryError])

  return (
    <SectionCard
      title="Market"
      description={
        market?.narrative ??
        'Market, benchmark, sector, news, and sentiment data.'
      }
      actions={
        <>
          <Badge variant="outline">Positioning: {positioning.label}</Badge>
          <Badge variant="outline">{marketUpdatedLabel}</Badge>
          <MarketStatusBadge />
        </>
      }
      variant="surface"
      className="h-full"
    >
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Leading Areas
          </p>
          <p className="mt-2 text-sm font-medium leading-relaxed text-text">
            {leadingAreas}
          </p>
        </div>
        <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Lagging Areas
          </p>
          <p className="mt-2 text-sm font-medium leading-relaxed text-text">
            {laggingAreas}
          </p>
        </div>
      </div>
    </SectionCard>
  )
}

export function InvestingMarketTrendPanels() {
  const [sectorTimeframe, setSectorTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const {
    data: sectorHistory,
    isLoading: isSectorHistoryLoading,
    error: sectorHistoryError,
  } = useSectorHistory(timeframeToDays(sectorTimeframe))

  return (
    <div className="space-y-4">
      <SectionCard variant="surface">
        <SentimentTrendChart />
      </SectionCard>

      <SectionCard variant="surface">
        <IndicatorsTrendChart />
      </SectionCard>

      <SectionCard variant="surface">
        <SectorPerformanceChart
          timeframe={sectorTimeframe}
          onTimeframeChange={setSectorTimeframe}
          data={sectorHistory}
          isLoading={isSectorHistoryLoading}
          error={
            sectorHistoryError instanceof Error ? sectorHistoryError : null
          }
        />
      </SectionCard>
    </div>
  )
}

export function InvestingMarketPanel() {
  return (
    <div className="space-y-4">
      <InvestingMarketSummaryPanel />
      <InvestingMarketTrendPanels />
    </div>
  )
}
