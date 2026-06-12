'use client'

import { useEffect, useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatRelativeTime } from '@/lib/utils'
import { AllocationCard } from './AllocationCard'
import { BudgetPulseCard } from './BudgetPulseCard'
import { DecisionBoard } from './DecisionBoard'
import type { MoneyOverviewSection } from './overview-helpers'
import { RecurringBillsCard } from './RecurringBillsCard'
import { SavingsLeversCard } from './SavingsLeversCard'
import { SpendTrendCard } from './SpendTrendCard'
import { useDecisionBoard } from './useDecisionBoard'
import { WhereMoneyWentCard } from './WhereMoneyWentCard'

export type { MoneyOverviewSection } from './overview-helpers'

/**
 * Hydration-safe relative time for mid-sentence use ('Generated just now.').
 * The shared `RelativeTime` keeps `formatRelativeTime`'s capitalized labels
 * ('Just now', 'Yesterday') because its other consumers render them
 * sentence-initial or standalone; here only those two variants are lowercased —
 * absolute dates ('Apr 11, 10:30 AM') keep their casing.
 */
function MidSentenceRelativeTime({ value }: { value: string }) {
  const [label, setLabel] = useState<string | null>(null)

  useEffect(() => {
    const update = () => {
      const raw = formatRelativeTime(value)
      setLabel(
        raw === 'Just now' || raw === 'Yesterday' ? raw.toLowerCase() : raw,
      )
    }
    update()
    const timer = setInterval(update, 60_000)
    return () => clearInterval(timer)
  }, [value])

  return <>{label ?? '—'}</>
}

export function MoneyOverviewPanel({
  dashboard,
  sections,
}: {
  dashboard: HouseholdFinanceDashboard
  sections?: MoneyOverviewSection[]
}) {
  const visibleSections = new Set<MoneyOverviewSection>(
    sections ?? [
      'decision',
      'allocation',
      'trend',
      'budget',
      'categories',
      'commitments',
      'levers',
    ],
  )
  const showDecision = visibleSections.has('decision')
  const showAllocation = visibleSections.has('allocation')
  const showTrend = visibleSections.has('trend')
  const showBudget = visibleSections.has('budget')
  const showCategories = visibleSections.has('categories')
  const showCommitments = visibleSections.has('commitments')
  const showLevers = visibleSections.has('levers')

  const board = useDecisionBoard(dashboard)

  const decisionBoardDescription = (
    <>
      Generated <MidSentenceRelativeTime value={dashboard.generatedAt} />.
    </>
  )

  return (
    <div className="space-y-6">
      {showDecision ? (
        <DecisionBoard
          dashboard={dashboard}
          description={decisionBoardDescription}
          spendTrustStatus={board.spendTrustStatus}
          spendTrustDetail={board.spendTrustDetail}
          spendTrustDegraded={board.spendTrustDegraded}
          spendTrustUnavailable={board.spendTrustUnavailable}
          whyShortStatus={board.whyShortStatus}
          whyShortSummary={board.whyShortSummary}
          whyShortDrivers={board.whyShortDrivers}
          planIsPartial={board.planIsPartial}
          monthGap={board.monthGap}
          safeSpendStatus={board.safeSpendStatus}
          safeSpendSummary={board.safeSpendSummary}
          safeSpendBindingLabel={board.safeSpendBindingLabel}
          safeSpendRepairItems={board.safeSpendRepairItems}
          weekendSpendAllowance={board.weekendSpendAllowance}
          operatingCushion={board.operatingCushion}
          dueSoonTotal={board.dueSoonTotal}
          needsAmount={board.needsAmount}
          wantsAmount={board.wantsAmount}
          needsShare={board.needsShare}
          wantsShare={board.wantsShare}
          needCategories={board.needCategories}
          wantCategories={board.wantCategories}
          saveNowLines={board.saveNowLines}
          priceInsights={board.priceInsights}
          merchantHighlights={board.merchantHighlights}
        />
      ) : null}

      {showAllocation || showTrend ? (
        <div
          className={
            showAllocation && showTrend
              ? 'grid gap-6 xl:grid-cols-2'
              : 'grid gap-6'
          }
        >
          {showAllocation ? (
            <AllocationCard
              dashboard={dashboard}
              allocationData={board.allocationData}
              selectedAssetGroup={board.selectedAssetGroup}
              setSelectedAssetGroup={board.setSelectedAssetGroup}
              selectedAccounts={board.selectedAccounts}
              netWorthTrustStatus={board.netWorthTrustStatus}
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
        </div>
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
    </div>
  )
}
