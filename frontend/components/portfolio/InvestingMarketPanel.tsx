'use client'

import { IndicatorsTrendChart } from '@/components/market/IndicatorsTrendChart'
import { MacroRegimeDriversTrendChart } from '@/components/market/MacroRegimeDriversTrendChart'
import { OvernightLeanChart } from '@/components/market/OvernightLeanChart'
import { SentimentTrendChart } from '@/components/market/SentimentTrendChart'
import { Sp500TrendChart } from '@/components/market/Sp500TrendChart'
import { SectionCard } from '@/components/shared/SectionCard'

export function InvestingMarketTrendPanels() {
  return (
    <div className="space-y-4">
      <SectionCard variant="surface">
        <Sp500TrendChart />
      </SectionCard>

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
