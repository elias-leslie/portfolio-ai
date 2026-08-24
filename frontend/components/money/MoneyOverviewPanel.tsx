'use client'

import { PrimaryTilesGrid } from '@/components/home/today/PrimaryTilesGrid'
import type {
  HouseholdFinanceDashboard,
  HouseholdNetWorthTrend,
} from '@/lib/api/household'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import { useHouseholdNetWorthTrend } from '@/lib/hooks/useHousehold'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { BudgetPulseCard } from './BudgetPulseCard'
import { CoverageCard } from './CoverageCard'
import { ExcludedFromSpendCard } from './ExcludedFromSpendCard'
import type { MoneyOverviewSection } from './overview-helpers'
import { RecurringBillsCard } from './RecurringBillsCard'
import { SavingsLeversCard } from './SavingsLeversCard'
import { SpendTrendCard } from './SpendTrendCard'
import { useMoneyOverview } from './useMoneyOverview'
import { WhereMoneyWentCard } from './WhereMoneyWentCard'

export type { MoneyOverviewSection } from './overview-helpers'

export function MoneyOverviewPanel({
  dashboard,
  analytics: analyticsProp,
  netWorthTrend: netWorthTrendProp,
  sections,
}: {
  dashboard: HouseholdFinanceDashboard
  analytics?: PortfolioAnalytics
  netWorthTrend?: HouseholdNetWorthTrend
  sections?: MoneyOverviewSection[]
}) {
  const { data: analyticsQuery } = usePortfolioAnalytics()
  const { data: netWorthTrendQuery } = useHouseholdNetWorthTrend({ days: 180 })

  const analytics = analyticsProp ?? analyticsQuery
  const netWorthTrend = netWorthTrendProp ?? netWorthTrendQuery

  const visibleSections = new Set<MoneyOverviewSection>(
    sections ?? ['trend', 'budget', 'categories', 'commitments', 'levers'],
  )
  const showTiles = visibleSections.has('tiles')
  const showTrend = visibleSections.has('trend')
  const showBudget = visibleSections.has('budget')
  const showCategories = visibleSections.has('categories')
  const showCommitments = visibleSections.has('commitments')
  const showLevers = visibleSections.has('levers')

  const board = useMoneyOverview(dashboard)

  return (
    <div className="space-y-6">
      {showTiles ? (
        <PrimaryTilesGrid
          household={dashboard}
          householdLoading={false}
          analytics={analytics}
          analyticsLoading={!analytics}
          netWorthTrend={netWorthTrend}
          trendLoading={!netWorthTrend}
          hideSpendPace
        />
      ) : null}
      {showTrend ? (
        <SpendTrendCard
          dashboard={dashboard}
          spendTrustStatus={board.spendTrustStatus}
          spendTrustDetail={board.spendTrustDetail}
          spendTrustDegraded={board.spendTrustDegraded}
        />
      ) : null}

      {showBudget ? (
        <BudgetPulseCard
          dashboard={dashboard}
          spendTrustStatus={board.spendTrustStatus}
          spendTrustDetail={board.spendTrustDetail}
          spendTrustDegraded={board.spendTrustDegraded}
          monthComparison={board.monthComparison}
          watchItems={board.watchItems}
        />
      ) : null}

      {showCategories ? (
        <WhereMoneyWentCard
          dashboard={dashboard}
          categoryData={board.categoryData}
          selectedCategory={board.selectedCategory}
          setSelectedCategory={board.setSelectedCategory}
          selectedTransactions={board.selectedTransactions}
          spendTrustStatus={board.spendTrustStatus}
          spendTrustDetail={board.spendTrustDetail}
          spendTrustDegraded={board.spendTrustDegraded}
        />
      ) : null}

      {showCommitments || showLevers ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {showCommitments ? (
            <RecurringBillsCard dueSoonCommitments={board.dueSoonCommitments} />
          ) : null}

          {showLevers ? (
            <SavingsLeversCard
              priceInsights={board.priceInsights}
              merchantHighlights={board.merchantHighlights}
            />
          ) : null}
        </div>
      ) : null}

      {showCategories ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <ExcludedFromSpendCard exclusions={dashboard.spendExclusions} />
          {dashboard.overview.coverage ? (
            <CoverageCard coverage={dashboard.overview.coverage} />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
