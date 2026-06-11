'use client'

import { ChevronDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { SectorPerformanceChart } from '@/components/market/SectorPerformanceChart'
import {
  DEFAULT_MARKET_TIMEFRAME,
  type Timeframe,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import { useSectorHistory } from '@/lib/hooks/useMarketIntelligence'
import { cn } from '@/lib/utils'

function sectorSummaryText(
  sectors: { name: string; currentPct: number }[],
  fallback: string,
): string {
  if (sectors.length === 0) return fallback
  return sectors
    .map(
      (sector) =>
        `${sector.name} ${sector.currentPct >= 0 ? '+' : ''}${sector.currentPct.toFixed(1)}%`,
    )
    .join(' · ')
}

// Compact leading/lagging sector strip for the Daily Brief. Extracted from the
// former Overview MarketSummaryGrid — only the sector ranking survives; the
// market narrative/positioning header it used to carry was dropped.
export function LeadingLaggingStrip() {
  const [showTrend, setShowTrend] = useState(true)
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const {
    data: sectorHistory,
    isLoading,
    error,
  } = useSectorHistory(timeframeToDays(timeframe))

  // Defensive sort: backend currently sorts by currentPct desc, but trusting that
  // implicit contract silently swaps leaders/laggards if the backend ever changes.
  const sortedSectors = useMemo(() => {
    if (!sectorHistory?.sectors) return []
    return [...sectorHistory.sectors].sort(
      (a, b) => (b.currentPct ?? 0) - (a.currentPct ?? 0),
    )
  }, [sectorHistory?.sectors])

  const leadingAreas = isLoading
    ? 'Updating sector leaders...'
    : error
      ? 'Unable to rank sectors right now'
      : sectorSummaryText(sortedSectors.slice(0, 3), 'Still populating')
  const laggingAreas = isLoading
    ? 'Updating sector laggards...'
    : error
      ? 'Unable to rank sectors right now'
      : sectorSummaryText(sortedSectors.slice(-3).reverse(), 'Still populating')

  return (
    <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4">
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
          Sector Rotation
        </p>
        <button
          type="button"
          aria-expanded={showTrend}
          onClick={() => setShowTrend((value) => !value)}
          className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted transition-colors hover:bg-surface-muted/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {showTrend ? 'Hide trend' : 'Show trend'}
          <ChevronDown
            className={cn(
              'h-3 w-3 transition-transform',
              showTrend && 'rotate-180',
            )}
          />
        </button>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <div className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Leading Areas
          </p>
          <p className="mt-1.5 text-[12px] font-medium leading-5 text-text">
            {leadingAreas}
          </p>
        </div>
        <div className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
            Lagging Areas
          </p>
          <p className="mt-1.5 text-[12px] font-medium leading-5 text-text">
            {laggingAreas}
          </p>
        </div>
      </div>
      {showTrend ? (
        <div className="mt-3">
          <SectorPerformanceChart
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
            data={sectorHistory}
            isLoading={isLoading}
            error={error instanceof Error ? error : null}
          />
        </div>
      ) : null}
    </div>
  )
}
