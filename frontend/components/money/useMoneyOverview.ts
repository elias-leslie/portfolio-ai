import { useEffect, useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  formatMonthLabel,
  normalizeTrustStatus,
  signedCurrency,
} from './overview-helpers'

/**
 * Derive the values the Money overview panel still renders from a single
 * dashboard payload, and own the category selection state so the panel body
 * stays declarative.
 *
 * This was `useDecisionBoard`, and it derived four cards' worth of verdicts:
 * budget pace, free to spend, the needs/wants/mixed split and savings levers.
 * All four are gone — the first three moved to the review screen where the
 * household actually reads the month, and the last belongs on Levers. The
 * allocation donut went to Investing with its own state. What is left is the
 * trend, the pulse, the categories and the bills.
 */
export function useMoneyOverview(dashboard: HouseholdFinanceDashboard) {
  // Backend already returns the top categories sorted desc by total spend.
  const categoryData = dashboard.reports.categoryBreakdown

  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    categoryData[0]?.category ?? null,
  )

  useEffect(() => {
    if (!categoryData.some((item) => item.category === selectedCategory)) {
      setSelectedCategory(categoryData[0]?.category ?? null)
    }
  }, [categoryData, selectedCategory])

  const selectedTransactions = dashboard.reports.recentTransactions.filter(
    (transaction) => transaction.category === selectedCategory,
  )
  const monthComparison = dashboard.reports.monthComparison
  // Bills and subscriptions only. A merchant the household happens to visit on a
  // rhythm owes nothing on a date, and listing it here is how a vacation ended up
  // being read as a commitment the household still had to pay.
  const dueSoonCommitments = dashboard.recurringCommitments
    .filter(
      (commitment) =>
        commitment.daysUntilDue != null &&
        (commitment.commitmentType === 'bill' ||
          commitment.commitmentType === 'subscription'),
    )
    .sort((left, right) => {
      const leftDue = left.daysUntilDue ?? Number.POSITIVE_INFINITY
      const rightDue = right.daysUntilDue ?? Number.POSITIVE_INFINITY
      return leftDue - rightDue
    })
    .slice(0, 4)
  const merchantHighlights = dashboard.reports.merchantHighlights.slice(0, 4)
  const priceInsights = (dashboard.reports.priceInsights ?? []).slice(0, 4)
  const spendTrustStatus = normalizeTrustStatus(
    dashboard.overview.monthlySpendStatus,
  )
  const netWorthTrustStatus = normalizeTrustStatus(
    dashboard.overview.netWorthStatus,
  )
  const spendTrustDetail = dashboard.overview.monthlySpendDetail
  const spendTrustUnavailable = spendTrustStatus === 'unavailable'
  const spendTrustDegraded = spendTrustStatus !== 'current'
  // The pace sentence is not repeated here: the Month-to-date tile on the same
  // card already prints it, and a watch list that echoes the paragraph above it
  // is the second copy this phase exists to remove.
  const watchItems = [
    dashboard.budgetSnapshot.discretionaryHeadroom != null &&
    dashboard.budgetSnapshot.discretionaryHeadroom < 0
      ? `Discretionary spending is ${formatCurrencyWhole(Math.abs(dashboard.budgetSnapshot.discretionaryHeadroom))} over the current monthly cap.`
      : null,
    !spendTrustDegraded && monthComparison && monthComparison.change > 0
      ? `${formatMonthLabel(monthComparison.latestMonth)} is ${signedCurrency(monthComparison.change)} versus ${formatMonthLabel(monthComparison.previousMonth)}.`
      : null,
    dueSoonCommitments[0]
      ? `${dueSoonCommitments[0].merchant} is due ${
          dueSoonCommitments[0].daysUntilDue === 0
            ? 'today'
            : `in ${dueSoonCommitments[0].daysUntilDue} day${dueSoonCommitments[0].daysUntilDue === 1 ? '' : 's'}`
        }.`
      : null,
  ].filter((item): item is string => Boolean(item))

  return {
    categoryData,
    selectedCategory,
    setSelectedCategory,
    selectedTransactions,
    monthComparison,
    dueSoonCommitments,
    merchantHighlights,
    priceInsights,
    spendTrustStatus,
    netWorthTrustStatus,
    spendTrustDetail,
    spendTrustUnavailable,
    spendTrustDegraded,
    watchItems,
  }
}
