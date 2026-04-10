'use client'

import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { IndicatorsTrendChart } from '@/components/market/IndicatorsTrendChart'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import { SectorPerformanceChart } from '@/components/market/SectorPerformanceChart'
import { SentimentTrendChart } from '@/components/market/SentimentTrendChart'
import {
  type Timeframe,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import { SectionCard } from '@/components/shared/SectionCard'
import {
  useMarketIntelligence,
  useSectorHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { describeMarketPositioning } from './investing-language'

function timeframeLabel(timeframe: Timeframe) {
  switch (timeframe) {
    case '1M':
      return 'past month'
    case '3M':
      return 'past 3 months'
    case '6M':
      return 'past 6 months'
    case '3Y':
      return 'past 3 years'
    case '5Y':
      return 'past 5 years'
    default:
      return 'past year'
  }
}

export function InvestingMarketPanel() {
  const [sectorTimeframe, setSectorTimeframe] = useState<Timeframe>('3M')
  const { data: market } = useMarketIntelligence()
  const {
    data: sectorHistory,
    isLoading: isSectorHistoryLoading,
    error: sectorHistoryError,
  } = useSectorHistory(timeframeToDays(sectorTimeframe))
  const positioning = describeMarketPositioning(market?.indicators.putcall)
  const sectorWindowLabel = timeframeLabel(sectorTimeframe)
  const leadingAreas = useMemo(() => {
    const sectors = sectorHistory?.sectors?.slice(0, 3) ?? []
    if (isSectorHistoryLoading) return 'Updating sector leaders...'
    if (sectorHistoryError) return 'Unable to rank sectors right now'
    if (sectors.length === 0) return 'Still populating'
    return sectors
      .map(
        (sector) =>
          `${sector.name} ${sector.currentPct >= 0 ? '+' : ''}${sector.currentPct.toFixed(1)}%`,
      )
      .join(' · ')
  }, [isSectorHistoryLoading, sectorHistory?.sectors, sectorHistoryError])
  const laggingAreas = useMemo(() => {
    const sectors = sectorHistory?.sectors
      ? [...sectorHistory.sectors].slice(-3).reverse()
      : []
    if (isSectorHistoryLoading) return 'Updating sector laggards...'
    if (sectorHistoryError) return 'Unable to rank sectors right now'
    if (sectors.length === 0) return 'Still populating'
    return sectors
      .map(
        (sector) =>
          `${sector.name} ${sector.currentPct >= 0 ? '+' : ''}${sector.currentPct.toFixed(1)}%`,
      )
      .join(' · ')
  }, [isSectorHistoryLoading, sectorHistory?.sectors, sectorHistoryError])

  return (
    <div className="space-y-4">
      <SectionCard
        title="Market"
        description={
          market?.narrative ??
          'Track the bigger backdrop before you decide what to buy, add, or trim.'
        }
        actions={
          <>
            <Badge variant="outline">Positioning: {positioning.label}</Badge>
            <MarketStatusBadge />
          </>
        }
        variant="surface"
      >
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
              Leading Areas
            </p>
            <p className="mt-2 text-[11px] uppercase tracking-[0.16em] text-text-muted">
              Strongest relative performers over the {sectorWindowLabel}
            </p>
            <p className="mt-2 text-sm font-medium leading-relaxed text-text">
              {leadingAreas}
            </p>
          </div>
          <div className="rounded-2xl border border-border/30 bg-surface-muted/20 px-4 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
              Lagging Areas
            </p>
            <p className="mt-2 text-[11px] uppercase tracking-[0.16em] text-text-muted">
              Weakest relative performers over the {sectorWindowLabel}
            </p>
            <p className="mt-2 text-sm font-medium leading-relaxed text-text">
              {laggingAreas}
            </p>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard variant="surface">
          <SentimentTrendChart />
        </SectionCard>

        <SectionCard variant="surface">
          <IndicatorsTrendChart />
        </SectionCard>

        <SectionCard variant="surface" className="xl:col-span-2">
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
    </div>
  )
}
