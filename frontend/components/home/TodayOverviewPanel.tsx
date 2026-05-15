'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import {
  useHouseholdDashboard,
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import {
  useMarketIntelligence,
  useMarketStatus,
} from '@/lib/hooks/useMarketIntelligence'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import {
  buildLiveMarketMetrics,
  MarketStripGrid,
} from './today/MarketStripGrid'
import { MarketSummaryGrid } from './today/MarketSummaryGrid'
import { PrimaryTilesGrid } from './today/PrimaryTilesGrid'

export function TodayOverviewPanel() {
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: netWorthTrend, isLoading: trendLoading } =
    useHouseholdNetWorthTrend({ days: 180 })
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics()
  const { data: market, isLoading: marketLoading } = useMarketIntelligence()
  const { data: marketStatus } = useMarketStatus()

  const marketMetrics =
    buildLiveMarketMetrics(market, {
      marketIsOpen: marketStatus?.isOpen ?? false,
    }) ?? []
  const marketStripTimestamp = market?.lastUpdated

  return (
    <SectionCard
      variant="surface"
      title="Overview"
      description="Household state, market tape, and next moves in one compact rail."
      padding="sm"
      headerClassName="px-5 py-4"
    >
      <div className="flex flex-col gap-3 animate-stagger">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1.08fr)_minmax(28rem,0.92fr)]">
          <PrimaryTilesGrid
            household={household}
            householdLoading={householdLoading}
            analytics={analytics}
            analyticsLoading={analyticsLoading}
            netWorthTrend={netWorthTrend}
            trendLoading={trendLoading}
          />
          <MarketSummaryGrid market={market} />
        </div>

        <MarketStripGrid
          metrics={marketMetrics}
          isLive={marketMetrics.length > 0}
          timestamp={marketStripTimestamp}
          loading={marketLoading}
        />
      </div>
    </SectionCard>
  )
}
