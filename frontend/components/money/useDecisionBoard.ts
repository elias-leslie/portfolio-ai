import { useEffect, useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  formatAssetGroup,
  formatMonthLabel,
  normalizeTrustStatus,
  priceInsightBadgeLabel,
  signedCurrency,
} from './overview-helpers'

// The backend names which input limits Safe-to-Spend; the frontend only words it.
const safeSpendConstraintLabels: Record<
  NonNullable<
    HouseholdFinanceDashboard['budgetSnapshot']['safeToSpendConstraint']
  >,
  string
> = {
  cash_after_cushion: 'visible cash after cushion and bills due in 14 days',
  plan_residual: 'income minus your monthly plan (a target, not cash on hand)',
  discretionary_cap: 'remaining discretionary cap for the month',
}

/**
 * Derive every Decision Board / Budget Pulse / Allocation value the Money overview
 * panel renders from a single dashboard payload. Owns the chart selection state
 * (asset group + category) so the panel body stays declarative. Pure aside from the
 * two selection `useState`/`useEffect` pairs — extracted so the math can be reasoned
 * about (and the panel kept small) without touching markup.
 */
export function useDecisionBoard(dashboard: HouseholdFinanceDashboard) {
  // Backend owns the allocation math (credit/debt excluded, sorted desc);
  // the map here is purely a label transform.
  const allocationData = dashboard.overview.assetAllocation.map((slice) => ({
    assetGroup: slice.assetGroup,
    label: formatAssetGroup(slice.assetGroup),
    value: slice.totalValue,
  }))
  // Backend already returns the top categories sorted desc by total spend.
  const categoryData = dashboard.reports.categoryBreakdown

  const [selectedAssetGroup, setSelectedAssetGroup] = useState<string | null>(
    allocationData[0]?.assetGroup ?? null,
  )
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    categoryData[0]?.category ?? null,
  )

  useEffect(() => {
    if (
      !allocationData.some((item) => item.assetGroup === selectedAssetGroup)
    ) {
      setSelectedAssetGroup(allocationData[0]?.assetGroup ?? null)
    }
  }, [allocationData, selectedAssetGroup])

  useEffect(() => {
    if (!categoryData.some((item) => item.category === selectedCategory)) {
      setSelectedCategory(categoryData[0]?.category ?? null)
    }
  }, [categoryData, selectedCategory])

  const selectedAccounts = dashboard.accounts.filter(
    (account) => account.assetGroup === selectedAssetGroup,
  )
  const selectedTransactions = dashboard.reports.recentTransactions.filter(
    (transaction) => transaction.category === selectedCategory,
  )
  const monthComparison = dashboard.reports.monthComparison
  const dueSoonCommitments = dashboard.recurringCommitments
    .filter((commitment) => commitment.daysUntilDue != null)
    .sort((left, right) => {
      const leftDue = left.daysUntilDue ?? Number.POSITIVE_INFINITY
      const rightDue = right.daysUntilDue ?? Number.POSITIVE_INFINITY
      return leftDue - rightDue
    })
    .slice(0, 4)
  const merchantHighlights = dashboard.reports.merchantHighlights.slice(0, 4)
  const priceInsights = (dashboard.reports.priceInsights ?? []).slice(0, 4)
  const dueSoonTotal = dashboard.budgetSnapshot.dueSoonBillsTotal
  const operatingCushion = dashboard.budgetSnapshot.operatingCushion
  const spendTrustStatus = normalizeTrustStatus(
    dashboard.overview.monthlySpendStatus,
  )
  const netWorthTrustStatus = normalizeTrustStatus(
    dashboard.overview.netWorthStatus,
  )
  const spendTrustDetail = dashboard.overview.monthlySpendDetail
  const spendTrustUnavailable = spendTrustStatus === 'unavailable'
  const spendTrustDegraded = spendTrustStatus !== 'current'
  const weekendSpendAllowance = dashboard.budgetSnapshot.safeToSpend
  const safeSpendStatus = spendTrustDegraded
    ? 'review'
    : weekendSpendAllowance == null
      ? 'mixed'
      : weekendSpendAllowance <= 0
        ? 'hold'
        : weekendSpendAllowance < 150
          ? 'tight'
          : 'safe'
  const safeSpendRepairItems = dashboard.inbox
    .filter((item) => item.affects.includes('safe_to_spend'))
    .slice(0, 2)
  const planIsPartial = dashboard.budgetSnapshot.planIsPartial
  const missingPlanComponents = dashboard.budgetSnapshot.missingPlanComponents
  // Surface which of the three inputs actually limits the Safe-to-Spend figure so the
  // dollar value is interpretable — it is often the income−target residual, not raw cash.
  const safeSpendBindingLabel =
    dashboard.budgetSnapshot.safeToSpendConstraint != null
      ? safeSpendConstraintLabels[
          dashboard.budgetSnapshot.safeToSpendConstraint
        ]
      : null
  const safeSpendSummary = spendTrustDegraded
    ? 'Stale account data; refresh before relying on this.'
    : 'Discretionary spend room against visible cash, bills due in 14 days, and the current plan.'
  const needsAmount = dashboard.reports.executive.averageMonthlyEssentials
  const wantsAmount = dashboard.reports.executive.averageMonthlyDiscretionary
  const trackedMonthlySpend = dashboard.reports.executive.averageMonthlySpend
  const needsShare =
    trackedMonthlySpend > 0 ? (needsAmount / trackedMonthlySpend) * 100 : null
  const wantsShare =
    trackedMonthlySpend > 0 ? (wantsAmount / trackedMonthlySpend) * 100 : null
  const needCategories = dashboard.reports.categoryBreakdown.filter(
    (category) => category.essentiality === 'essential',
  )
  const wantCategories = dashboard.reports.categoryBreakdown.filter(
    (category) => category.essentiality === 'discretionary',
  )
  const monthGap =
    dashboard.budgetSnapshot.monthToDatePlan != null
      ? dashboard.budgetSnapshot.monthToDateSpend -
        dashboard.budgetSnapshot.monthToDatePlan
      : null
  const discretionaryGap =
    dashboard.budgetSnapshot.discretionaryTarget != null
      ? dashboard.budgetSnapshot.actualDiscretionaryMonthlySpend -
        dashboard.budgetSnapshot.discretionaryTarget
      : null
  const essentialGap =
    dashboard.budgetSnapshot.essentialTarget != null
      ? dashboard.budgetSnapshot.actualEssentialMonthlySpend -
        dashboard.budgetSnapshot.essentialTarget
      : null
  const latestPricePressure = priceInsights.find(
    (insight) =>
      insight.signalType === 'shrinkflation' ||
      insight.signalType === 'unit_price_up' ||
      insight.signalType === 'price_up',
  )
  const whyShortDrivers = [
    !planIsPartial && monthGap != null && monthGap > 100
      ? `${formatCurrencyWhole(monthGap)} over month-to-date pace right now.`
      : null,
    discretionaryGap != null && discretionaryGap > 50
      ? `Wants are ${formatCurrencyWhole(discretionaryGap)} above the current cap.`
      : null,
    essentialGap != null && essentialGap > 50
      ? `Needs are ${formatCurrencyWhole(essentialGap)} above target.`
      : null,
    monthComparison && monthComparison.change > 100
      ? `${formatMonthLabel(monthComparison.latestMonth)} ran ${signedCurrency(monthComparison.change)} versus ${formatMonthLabel(monthComparison.previousMonth)}.`
      : null,
    dueSoonTotal != null && dueSoonTotal > 0
      ? `${formatCurrencyWhole(dueSoonTotal)} of recurring bills are due inside 14 days.`
      : null,
    latestPricePressure
      ? `${latestPricePressure.itemName} is pressuring the budget via ${priceInsightBadgeLabel(latestPricePressure.signalType).toLowerCase()}.`
      : null,
  ].filter((item): item is string => Boolean(item))
  const whyShortStatus = spendTrustUnavailable
    ? 'mixed'
    : spendTrustDegraded
      ? 'mixed'
      : planIsPartial
        ? 'partial_plan'
        : discretionaryGap != null && discretionaryGap > 50
          ? 'wants_driving_gap'
          : essentialGap != null && essentialGap > 50
            ? 'essentials_driving_gap'
            : monthGap != null && monthGap > 100
              ? 'mixed'
              : 'inside_guardrails'
  const whyShortSummary = planIsPartial
    ? `Plan is partial — ${missingPlanComponents.join(' and ')} ${missingPlanComponents.length === 1 ? 'target is' : 'targets are'} not set, so total spend is not paced against it yet.`
    : (whyShortDrivers[0] ??
      'Nothing obvious is breaking the month right now. Shortfall risk looks more like bill timing than overspend.')
  const saveNowLines = [
    latestPricePressure
      ? `${priceInsightBadgeLabel(latestPricePressure.signalType)}: ${latestPricePressure.itemName}`
      : null,
    merchantHighlights[0]
      ? `Merchant to attack first: ${merchantHighlights[0].merchant}`
      : null,
    dashboard.jennyBrief.prompts[0] ?? null,
  ].filter((item): item is string => Boolean(item))
  const watchItems = [
    dashboard.budgetSnapshot.paceStatus === 'running_hot'
      ? dashboard.budgetSnapshot.paceDetail
      : null,
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
    allocationData,
    categoryData,
    selectedAssetGroup,
    setSelectedAssetGroup,
    selectedCategory,
    setSelectedCategory,
    selectedAccounts,
    selectedTransactions,
    monthComparison,
    dueSoonCommitments,
    merchantHighlights,
    priceInsights,
    dueSoonTotal,
    operatingCushion,
    spendTrustStatus,
    netWorthTrustStatus,
    spendTrustDetail,
    spendTrustUnavailable,
    spendTrustDegraded,
    weekendSpendAllowance,
    safeSpendStatus,
    safeSpendRepairItems,
    planIsPartial,
    safeSpendBindingLabel,
    safeSpendSummary,
    needsAmount,
    wantsAmount,
    needsShare,
    wantsShare,
    needCategories,
    wantCategories,
    monthGap,
    whyShortDrivers,
    whyShortStatus,
    whyShortSummary,
    saveNowLines,
    watchItems,
  }
}
