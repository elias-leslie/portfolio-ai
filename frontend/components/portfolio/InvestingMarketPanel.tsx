'use client'

import { Badge } from '@/components/ui/badge'
import { IndicatorsTrendChart } from '@/components/market/IndicatorsTrendChart'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import { SectorPerformanceChart } from '@/components/market/SectorPerformanceChart'
import { SentimentTrendChart } from '@/components/market/SentimentTrendChart'
import { SectionCard } from '@/components/shared/SectionCard'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { describeMarketPositioning } from './investing-language'

export function InvestingMarketPanel() {
  const { data: market } = useMarketIntelligence()
  const positioning = describeMarketPositioning(market?.indicators.putcall)
  const leadingAreas =
    market?.sectorRotation.leading
      .slice(0, 3)
      .map((sector) => sector.name)
      .join(' · ') ?? 'Still populating'
  const laggingAreas =
    market?.sectorRotation.lagging
      .slice(0, 3)
      .map((sector) => sector.name)
      .join(' · ') ?? 'Still populating'

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

      <div className="grid gap-4 xl:grid-cols-2">
        <SectionCard variant="surface">
          <SentimentTrendChart />
        </SectionCard>

        <SectionCard variant="surface">
          <IndicatorsTrendChart />
        </SectionCard>

        <SectionCard variant="surface" className="xl:col-span-2">
          <SectorPerformanceChart />
        </SectionCard>
      </div>
    </div>
  )
}
