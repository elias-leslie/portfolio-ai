'use client'

import { useMemo } from 'react'
import {
  DEFAULT_MARKET_TIMEFRAME,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import { useSectorHistory } from '@/lib/hooks/useMarketIntelligence'

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
  const {
    data: sectorHistory,
    isLoading,
    error,
  } = useSectorHistory(timeframeToDays(DEFAULT_MARKET_TIMEFRAME))

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
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
        Sector Rotation
      </p>
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
    </div>
  )
}
