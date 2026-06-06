'use client'

import { useState } from 'react'
import { IndicatorsTrendChart } from '@/components/market/IndicatorsTrendChart'
import { MacroRegimeDriversTrendChart } from '@/components/market/MacroRegimeDriversTrendChart'
import { OvernightLeanChart } from '@/components/market/OvernightLeanChart'
import { SectorPerformanceChart } from '@/components/market/SectorPerformanceChart'
import { SentimentTrendChart } from '@/components/market/SentimentTrendChart'
import {
  DEFAULT_MARKET_TIMEFRAME,
  type Timeframe,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import { SectionCard } from '@/components/shared/SectionCard'
import { useSectorHistory } from '@/lib/hooks/useMarketIntelligence'

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
        <MacroRegimeDriversTrendChart />
      </SectionCard>

      <SectionCard variant="surface">
        <SentimentTrendChart />
      </SectionCard>

      <SectionCard variant="surface">
        <IndicatorsTrendChart />
      </SectionCard>

      <SectionCard variant="surface">
        <OvernightLeanChart />
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
      <InvestingMarketTrendPanels />
    </div>
  )
}
