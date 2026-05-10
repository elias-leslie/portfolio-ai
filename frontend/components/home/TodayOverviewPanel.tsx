'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { useHomeTodayBrief } from '@/lib/hooks/useHomeTodayBrief'
import {
  useHouseholdDashboard,
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import {
  buildLiveMarketMetrics,
  MarketStripGrid,
} from './today/MarketStripGrid'
import { PrimaryTilesGrid } from './today/PrimaryTilesGrid'
import { SystemPulseGrid } from './today/SystemPulseGrid'

export function TodayOverviewPanel() {
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: netWorthTrend, isLoading: trendLoading } =
    useHouseholdNetWorthTrend({ days: 180 })
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics()
  const { data: market, isLoading: marketLoading } = useMarketIntelligence()
  const { data: todayBrief, isLoading: briefLoading } = useHomeTodayBrief()

  const liveMarketMetrics = buildLiveMarketMetrics(market)
  const marketMetrics = liveMarketMetrics ?? todayBrief?.marketMetrics ?? []
  const marketStripTimestamp = liveMarketMetrics
    ? market?.lastUpdated
    : todayBrief?.generatedAt

  return (
    <SectionCard
      variant="surface"
      title="Overview"
      description="Household state, market tape, and data quality in one compact rail."
      padding="sm"
      headerClassName="px-5 py-4"
      className="h-full"
    >
      <div className="flex h-full flex-col gap-3 animate-stagger">
        <PrimaryTilesGrid
          household={household}
          householdLoading={householdLoading}
          analytics={analytics}
          analyticsLoading={analyticsLoading}
          netWorthTrend={netWorthTrend}
          trendLoading={trendLoading}
        />

        <MarketStripGrid
          metrics={marketMetrics}
          isLive={Boolean(liveMarketMetrics)}
          timestamp={marketStripTimestamp}
          loading={briefLoading}
        />

        <SystemPulseGrid
          household={household}
          householdLoading={householdLoading}
          analytics={analytics}
          analyticsLoading={analyticsLoading}
          market={market}
          marketLoading={marketLoading}
        />
      </div>
    </SectionCard>
  )
}
