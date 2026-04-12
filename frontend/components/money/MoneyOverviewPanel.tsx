'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  type TooltipValueType,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

const allocationColors = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
]

function formatMonthLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

function formatAssetGroup(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

function getTooltipNumber(value: TooltipValueType | undefined): number | null {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  if (Array.isArray(value)) {
    const parsed = Number(value[0])
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function formatThousandsAxis(value: number) {
  return `$${Math.round(value / 1000)}k`
}

const currencyTooltipFormatter: TooltipProps<TooltipValueType>['formatter'] = (
  value,
) => formatCurrency(getTooltipNumber(value), { decimals: 0, nullDisplay: '—' })

const monthTooltipLabelFormatter: TooltipProps<TooltipValueType>['labelFormatter'] =
  (label) =>
    formatMonthLabel(typeof label === 'string' ? label : String(label ?? ''))

function signedCurrency(
  value: number | null | undefined,
  opts?: { decimals?: number },
) {
  const decimals = opts?.decimals ?? 0
  if (value == null) {
    return '—'
  }
  if (value === 0) {
    return formatCurrency(0, { decimals })
  }
  return `${value > 0 ? '+' : '-'}${formatCurrency(Math.abs(value), { decimals })}`
}

function paceBadgeVariant(status: string) {
  switch (status) {
    case 'on_track':
    case 'under_plan':
    case 'upcoming':
      return 'success' as const
    case 'due_soon':
    case 'running_hot':
      return 'warning' as const
    case 'overdue':
    case 'essentials_above_plan':
    case 'discretionary_above_plan':
      return 'error' as const
    default:
      return 'secondary' as const
  }
}

function comparisonBadgeVariant(change: number) {
  if (change > 0) {
    return 'warning' as const
  }
  if (change < 0) {
    return 'success' as const
  }
  return 'secondary' as const
}

function priceInsightBadgeVariant(signalType: string) {
  switch (signalType) {
    case 'shrinkflation':
      return 'error' as const
    case 'unit_price_up':
    case 'price_up':
      return 'warning' as const
    case 'price_down':
      return 'success' as const
    default:
      return 'secondary' as const
  }
}

function priceInsightBadgeLabel(signalType: string) {
  switch (signalType) {
    case 'shrinkflation':
      return 'Less product'
    case 'unit_price_up':
      return 'Unit price up'
    case 'price_up':
      return 'Price up'
    case 'price_down':
      return 'Price down'
    default:
      return 'Price move'
  }
}

function latestCompletedMonthComparison(
  trend: HouseholdFinanceDashboard['reports']['monthlySpendTrend'],
) {
  if (trend.length < 2) {
    return null
  }

  const sorted = trend
    .slice()
    .sort((left, right) => left.month.localeCompare(right.month))
  const currentMonthKey = new Date().toISOString().slice(0, 7)
  const completed =
    sorted[sorted.length - 1]?.month === currentMonthKey
      ? sorted.slice(0, -1)
      : sorted

  if (completed.length < 2) {
    return null
  }

  const latest = completed[completed.length - 1]
  const previous = completed[completed.length - 2]
  const change = latest.totalSpend - previous.totalSpend
  const changePct =
    previous.totalSpend > 0 ? (change / previous.totalSpend) * 100 : null

  return { latest, previous, change, changePct }
}

function decisionBadgeVariant(status: string) {
  switch (status) {
    case 'safe':
    case 'inside_guardrails':
    case 'needs_leading':
      return 'success' as const
    case 'tight':
    case 'review':
    case 'mixed':
      return 'warning' as const
    case 'hold':
    case 'wants_driving_gap':
    case 'essentials_driving_gap':
      return 'error' as const
    default:
      return 'secondary' as const
  }
}

function formatCategoryPreview(
  categories: HouseholdFinanceDashboard['reports']['categoryBreakdown'],
) {
  if (categories.length === 0) {
    return 'No category split yet.'
  }
  return categories
    .slice(0, 2)
    .map(
      (category) =>
        `${category.category} ${formatCurrencyWhole(category.monthlyAverage)}`,
    )
    .join(' · ')
}

function normalizeTrustStatus(status: string) {
  switch (status) {
    case 'trusted':
      return 'current'
    case 'partial':
      return 'estimated'
    case 'blocked':
      return 'unavailable'
    default:
      return status
  }
}

function trustCardValue(
  status: string,
  visibleValue: string,
  unavailableValue = '—',
) {
  return normalizeTrustStatus(status) === 'unavailable'
    ? unavailableValue
    : visibleValue
}

function trustStatusLabel(status: string) {
  switch (normalizeTrustStatus(status)) {
    case 'current':
      return 'Current'
    case 'estimated':
      return 'Estimate'
    case 'stale':
      return 'Stale'
    default:
      return 'Unavailable'
  }
}

export function MoneyOverviewPanel({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const allocationData = Object.entries(
    dashboard.accounts.reduce<Record<string, number>>((totals, account) => {
      if (
        ['credit', 'debt'].includes(account.assetGroup) ||
        (account.currentValue ?? 0) <= 0
      ) {
        return totals
      }
      totals[account.assetGroup] =
        (totals[account.assetGroup] ?? 0) + (account.currentValue ?? 0)
      return totals
    }, {}),
  )
    .map(([assetGroup, value]) => ({
      assetGroup,
      label: formatAssetGroup(assetGroup),
      value,
    }))
    .sort((left, right) => right.value - left.value)
  const categoryData = dashboard.reports.categoryBreakdown
    .slice()
    .sort((left, right) => right.totalSpend - left.totalSpend)
    .slice(0, 6)
    .map((category) => ({
      category: category.category,
      totalSpend: category.totalSpend,
      monthlyAverage: category.monthlyAverage,
      shareOfSpend: category.shareOfSpend,
    }))

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
  const monthComparison = latestCompletedMonthComparison(
    dashboard.reports.monthlySpendTrend,
  )
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
  const dueSoonTotal = dashboard.recurringCommitments
    .filter(
      (commitment) =>
        commitment.daysUntilDue != null && commitment.daysUntilDue <= 14,
    )
    .reduce((total, commitment) => total + commitment.averageAmount, 0)
  const operatingCushion =
    dashboard.profile.monthlyEssentialTarget ??
    dashboard.reports.executive.averageMonthlyEssentials
  const spendTrustStatus = normalizeTrustStatus(
    dashboard.overview.monthlySpendStatus,
  )
  const netWorthTrustStatus = normalizeTrustStatus(
    dashboard.overview.netWorthStatus,
  )
  const spendTrustDetail = dashboard.overview.monthlySpendDetail
  const spendTrustUnavailable = spendTrustStatus === 'unavailable'
  const spendTrustDegraded = spendTrustStatus !== 'current'
  const spendTrustLabel = trustStatusLabel(spendTrustStatus).toLowerCase()
  const weekendSpendRaw = Math.min(
    dashboard.overview.cashReserve - operatingCushion - dueSoonTotal,
    dashboard.budgetSnapshot.remainingCashAfterPlan ?? Number.POSITIVE_INFINITY,
    dashboard.budgetSnapshot.discretionaryHeadroom ?? Number.POSITIVE_INFINITY,
  )
  const weekendSpendAllowance = Number.isFinite(weekendSpendRaw)
    ? Math.max(weekendSpendRaw, 0)
    : null
  const safeSpendStatus =
    spendTrustUnavailable || weekendSpendAllowance == null
      ? 'review'
      : weekendSpendAllowance <= 0
          ? 'hold'
          : weekendSpendAllowance < 150
            ? 'tight'
            : 'safe'
  const safeSpendSummary = spendTrustDegraded
    ? `Weekend spend room is ${spendTrustLabel} until spending coverage is current. ${spendTrustDetail}`
    : 'Discretionary spend that still respects visible cash, due-soon bills, and the current plan.'
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
  const coverageBlockers = dashboard.inbox
    .filter((item) => item.category !== 'question')
    .slice(0, 3)
    .map((item) => item.title)
  const whyShortDrivers = spendTrustDegraded
    ? coverageBlockers.length > 0
      ? coverageBlockers
      : [spendTrustDetail]
    : [
        monthGap != null && monthGap > 100
          ? `${formatCurrencyWhole(monthGap)} over month-to-date pace right now.`
          : null,
        discretionaryGap != null && discretionaryGap > 50
          ? `Wants are ${formatCurrencyWhole(discretionaryGap)} above the current cap.`
          : null,
        essentialGap != null && essentialGap > 50
          ? `Needs are ${formatCurrencyWhole(essentialGap)} above target.`
          : null,
        monthComparison && monthComparison.change > 100
          ? `${formatMonthLabel(monthComparison.latest.month)} ran ${signedCurrency(monthComparison.change)} versus ${formatMonthLabel(monthComparison.previous.month)}.`
          : null,
        dueSoonTotal > 0
          ? `${formatCurrencyWhole(dueSoonTotal)} of recurring bills are due inside 14 days.`
          : null,
        latestPricePressure
          ? `${latestPricePressure.itemName} is pressuring the budget via ${priceInsightBadgeLabel(latestPricePressure.signalType).toLowerCase()}.`
          : null,
      ].filter((item): item is string => Boolean(item))
  const whyShortStatus = spendTrustUnavailable
    ? 'review'
    : spendTrustDegraded
      ? 'review'
      : discretionaryGap != null && discretionaryGap > 50
        ? 'wants_driving_gap'
        : essentialGap != null && essentialGap > 50
          ? 'essentials_driving_gap'
          : monthGap != null && monthGap > 100
            ? 'mixed'
            : 'inside_guardrails'
  const whyShortSummary = spendTrustDegraded
    ? spendTrustDetail
    : whyShortDrivers[0] ??
      'Nothing obvious is breaking the month right now. Shortfall risk looks more like bill timing than overspend.'
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
    spendTrustDegraded ? spendTrustDetail : null,
    dashboard.budgetSnapshot.paceStatus === 'running_hot'
      ? dashboard.budgetSnapshot.paceDetail
      : null,
    dashboard.budgetSnapshot.discretionaryHeadroom != null &&
    dashboard.budgetSnapshot.discretionaryHeadroom < 0
      ? `Discretionary spending is ${formatCurrencyWhole(Math.abs(dashboard.budgetSnapshot.discretionaryHeadroom))} over the current monthly cap.`
      : null,
    !spendTrustDegraded && monthComparison && monthComparison.change > 0
      ? `${formatMonthLabel(monthComparison.latest.month)} is ${signedCurrency(monthComparison.change)} versus ${formatMonthLabel(monthComparison.previous.month)}.`
      : null,
    dueSoonCommitments[0]
      ? `${dueSoonCommitments[0].merchant} is due ${
          dueSoonCommitments[0].daysUntilDue === 0
            ? 'today'
            : `in ${dueSoonCommitments[0].daysUntilDue} day${dueSoonCommitments[0].daysUntilDue === 1 ? '' : 's'}`
        }.`
      : null,
  ].filter((item): item is string => Boolean(item))

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Decision Board"
        description="Answer the household questions first, then drill into the charts and transactions below."
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">
                Why this month feels tight
              </p>
              <Badge variant={decisionBadgeVariant(whyShortStatus)}>
                {formatEnumLabel(whyShortStatus)}
              </Badge>
            </div>
            <p className="mt-3 text-2xl font-semibold text-text">
              {spendTrustDegraded
                ? trustCardValue(spendTrustStatus, signedCurrency(monthGap))
                : signedCurrency(monthGap)}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              {!spendTrustDegraded && dashboard.budgetSnapshot.monthToDatePlan != null
                ? 'Current month pace versus plan.'
                : spendTrustDegraded
                  ? 'Money data needs repair before Jenny can explain this month with confidence.'
                  : 'Waiting on a full monthly plan for a cleaner answer.'}
            </p>
            <p className="mt-3 text-sm leading-relaxed text-text-muted">
              {whyShortSummary}
            </p>
            <div className="mt-3 space-y-2">
              {whyShortDrivers.slice(0, 3).map((driver) => (
                <p key={driver} className="text-xs text-text-muted">
                  {driver}
                </p>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">
                Safe to spend this weekend
              </p>
              <Badge variant={decisionBadgeVariant(safeSpendStatus)}>
                {formatEnumLabel(safeSpendStatus)}
              </Badge>
            </div>
            <p className="mt-3 text-2xl font-semibold text-text">
              {trustCardValue(
                spendTrustStatus,
                formatCurrencyWhole(weekendSpendAllowance, {
                  nullDisplay: 'Review',
                }),
                'Review',
              )}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              {safeSpendSummary}
            </p>
            <div className="mt-3 space-y-2 text-xs text-text-muted">
              {spendTrustDegraded ? (
                <>
                  <p>
                    Latest covered transaction:{' '}
                    {dashboard.overview.lastTransactionDate ?? 'Unknown'}
                  </p>
                  <p>
                    Coverage: {dashboard.overview.coverageMonths} month
                    {dashboard.overview.coverageMonths === 1 ? '' : 's'}
                  </p>
                  <p>
                    Fix first: {coverageBlockers[0] ?? dashboard.overview.nextBestAction}
                  </p>
                </>
              ) : (
                <>
                  <p>
                    Operating cushion: {formatCurrencyWhole(operatingCushion)}
                  </p>
                  <p>Due in 14 days: {formatCurrencyWhole(dueSoonTotal)}</p>
                  <p>
                    Remaining after plan:{' '}
                    {formatCurrencyWhole(
                      dashboard.budgetSnapshot.remainingCashAfterPlan,
                      { nullDisplay: 'Not set' },
                    )}
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">Want vs need</p>
              <Badge
                variant={decisionBadgeVariant(
                  spendTrustDegraded
                    ? 'mixed'
                    : needsAmount >= wantsAmount
                      ? 'needs_leading'
                      : 'mixed',
                )}
              >
                {!spendTrustDegraded && needsShare != null
                  ? `${formatPercent(needsShare, { decimals: 0 })} needs`
                  : trustStatusLabel(spendTrustStatus)}
              </Badge>
            </div>
            <p className="mt-3 text-2xl font-semibold text-text">
              {trustCardValue(
                spendTrustStatus,
                `${formatCurrencyWhole(needsAmount)} / ${formatCurrencyWhole(wantsAmount)}`,
                'Awaiting split',
              )}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              {spendTrustDegraded
                ? `Needs versus wants is ${spendTrustLabel} until spending coverage is current. ${spendTrustDetail}`
                : 'Needs versus wants from the recent monthly average.'}
            </p>
            <div className="mt-3 space-y-2 text-xs text-text-muted">
              {spendTrustDegraded ? (
                whyShortDrivers.slice(0, 3).map((driver) => (
                  <p key={driver}>{driver}</p>
                ))
              ) : (
                <>
                  <p>Needs: {formatCategoryPreview(needCategories)}</p>
                  <p>Wants: {formatCategoryPreview(wantCategories)}</p>
                  <p>
                    Wants share:{' '}
                    {formatPercent(wantsShare, {
                      decimals: 0,
                      nullDisplay: '—',
                    })}
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text">
                Where to save next
              </p>
              <Badge
                variant={decisionBadgeVariant(
                  saveNowLines.length > 0 ? 'mixed' : 'inside_guardrails',
                )}
              >
                {saveNowLines.length} live lever
                {saveNowLines.length === 1 ? '' : 's'}
              </Badge>
            </div>
            <p className="mt-3 text-2xl font-semibold text-text">
              {priceInsights.length + merchantHighlights.length}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              Price moves, merchant patterns, and Jenny follow-ups worth
              checking first.
            </p>
            <div className="mt-3 space-y-2">
              {saveNowLines.length === 0 ? (
                <p className="text-xs text-text-muted">
                  Jenny needs more repeat-buy history before it can surface
                  savings levers here.
                </p>
              ) : (
                saveNowLines.map((line) => (
                  <p key={line} className="text-xs text-text-muted">
                    {line}
                  </p>
                ))
              )}
            </div>
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <SectionCard
            variant="surface"
            title="Account Allocation"
          >
          {netWorthTrustStatus !== 'current' ? (
            <div className="mb-4 rounded-2xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-text-muted">
              {dashboard.overview.netWorthDetail}
            </div>
          ) : null}
          {allocationData.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
              No asset allocation yet. Upload bank, brokerage, or retirement
              evidence so Jenny can map account balances.
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={allocationData}
                      dataKey="value"
                      nameKey="label"
                      innerRadius={58}
                      outerRadius={92}
                      paddingAngle={2}
                      onClick={(_, index) => {
                        const entry = allocationData[index]
                        if (entry?.assetGroup) {
                          setSelectedAssetGroup(entry.assetGroup)
                        }
                      }}
                    >
                      {allocationData.map((entry, index) => (
                        <Cell
                          key={entry.assetGroup}
                          fill={
                            allocationColors[index % allocationColors.length]
                          }
                        />
                      ))}
                    </Pie>
                    <Tooltip formatter={currencyTooltipFormatter} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-3">
                {allocationData.map((entry, index) => {
                  const isActive = entry.assetGroup === selectedAssetGroup
                  return (
                    <button
                      key={entry.assetGroup}
                      type="button"
                      onClick={() => setSelectedAssetGroup(entry.assetGroup)}
                      className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition-colors ${
                        isActive
                          ? 'border-primary/40 bg-primary/10'
                          : 'border-border/40 bg-surface-muted/15 hover:border-border/60'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className="h-3 w-3 rounded-full"
                          style={{
                            backgroundColor:
                              allocationColors[index % allocationColors.length],
                          }}
                        />
                        <div>
                          <p className="text-sm font-semibold text-text">
                            {entry.label}
                          </p>
                          <p className="text-xs text-text-muted">
                            {
                              dashboard.accounts.filter(
                                (account) =>
                                  account.assetGroup === entry.assetGroup,
                              ).length
                            }{' '}
                            account
                            {dashboard.accounts.filter(
                              (account) =>
                                account.assetGroup === entry.assetGroup,
                            ).length === 1
                              ? ''
                              : 's'}
                          </p>
                        </div>
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-text">
                        {formatCurrencyWhole(entry.value)}
                      </span>
                    </button>
                  )
                })}
                {selectedAccounts.length > 0 ? (
                  <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                      Drill-down
                    </p>
                    <div className="mt-3 space-y-2">
                      {selectedAccounts.slice(0, 4).map((account) => (
                        <div
                          key={account.id}
                          className="flex items-center justify-between gap-3 text-sm"
                        >
                          <div>
                            <p className="font-medium text-text">
                              {account.label}
                            </p>
                            <p className="text-xs text-text-muted">
                              {account.freshnessLabel} · {account.matchStatus}
                            </p>
                          </div>
                          <span className="tabular-nums text-text">
                            {formatCurrencyWhole(account.currentValue)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4">
                      <Button asChild size="sm" variant="outline">
                        <Link href="/money?tab=accounts">
                          Open accounts
                        </Link>
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </SectionCard>

          <SectionCard
            variant="surface"
            title="Monthly Spend Trend"
          >
          {spendTrustDegraded ? (
            <div className="mb-4 rounded-2xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-text-muted">
              {spendTrustDetail}
            </div>
          ) : null}
          {dashboard.reports.monthlySpendTrend.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
              No monthly spend trend yet. Upload at least one
              transaction-bearing statement or export.
            </div>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={dashboard.reports.monthlySpendTrend}
                  margin={{ top: 10, right: 12, left: 0, bottom: 8 }}
                >
                  <XAxis
                    dataKey="month"
                    tickFormatter={formatMonthLabel}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={{ stroke: 'var(--color-border)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={formatThousandsAxis}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    formatter={currencyTooltipFormatter}
                    labelFormatter={monthTooltipLabelFormatter}
                  />
                  <Line
                    type="monotone"
                    dataKey="totalSpend"
                    stroke="var(--color-chart-blue)"
                    strokeWidth={2.5}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          </SectionCard>
        </div>

        <div className="space-y-6">
          <SectionCard
            variant="surface"
            title="Budget Pulse"
            description={dashboard.budgetSnapshot.summary}
          >
          {spendTrustDegraded ? (
            <div className="mb-4 rounded-2xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-text-muted">
              {spendTrustDetail}
            </div>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">
                  Month to date
                </p>
                <Badge variant={paceBadgeVariant(dashboard.budgetSnapshot.paceStatus)}>
                  {formatEnumLabel(dashboard.budgetSnapshot.paceStatus)}
                </Badge>
              </div>
              <p className="mt-3 text-2xl font-semibold text-text">
                {trustCardValue(
                  spendTrustStatus,
                  formatCurrencyWhole(dashboard.budgetSnapshot.monthToDateSpend),
                )}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                {spendTrustDegraded
                  ? `Month-to-date subtotal is ${spendTrustLabel} until spending coverage is current.`
                  : `Plan: ${formatCurrencyWhole(dashboard.budgetSnapshot.monthToDatePlan, {
                      nullDisplay: 'Not set',
                    })}`}
              </p>
              <p className="mt-3 text-sm leading-relaxed text-text-muted">
                {spendTrustDegraded
                  ? spendTrustDetail
                  : dashboard.budgetSnapshot.paceDetail}
              </p>
            </div>

            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">
                  Discretionary headroom
                </p>
                {dashboard.budgetSnapshot.discretionaryHeadroom != null ? (
                  <Badge
                    variant={
                      dashboard.budgetSnapshot.discretionaryHeadroom >= 0
                        ? 'success'
                        : 'warning'
                    }
                  >
                    {dashboard.budgetSnapshot.discretionaryHeadroom >= 0
                      ? 'Inside cap'
                      : 'Above cap'}
                  </Badge>
                ) : null}
              </div>
              <p className="mt-3 text-2xl font-semibold text-text">
                {trustCardValue(
                  spendTrustStatus,
                  signedCurrency(dashboard.budgetSnapshot.discretionaryHeadroom),
                )}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                {spendTrustDegraded
                  ? `Headroom is ${spendTrustLabel} while spending coverage is degraded.`
                  : `Monthly plan: ${formatCurrencyWhole(dashboard.budgetSnapshot.monthlyPlanTotal, {
                      nullDisplay: 'Not set',
                    })}`}
              </p>
              <p className="mt-3 text-sm leading-relaxed text-text-muted">
                {spendTrustDegraded
                  ? spendTrustDetail
                  : `Remaining after plan: ${formatCurrencyWhole(
                      dashboard.budgetSnapshot.remainingCashAfterPlan,
                      {
                        nullDisplay: 'Not available',
                      },
                    )}`}
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">
                  Latest full-month change
                </p>
                {!spendTrustDegraded && monthComparison ? (
                  <Badge variant={comparisonBadgeVariant(monthComparison.change)}>
                    {formatPercent(monthComparison.changePct, {
                      decimals: 0,
                      sign: true,
                      nullDisplay: 'New',
                    })}
                  </Badge>
                ) : null}
              </div>
              {spendTrustDegraded ? (
                <>
                  <p className="mt-3 text-2xl font-semibold text-text">
                    {monthComparison
                      ? trustCardValue(
                          spendTrustStatus,
                          signedCurrency(monthComparison.change),
                        )
                      : trustCardValue(spendTrustStatus, '—')}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    {monthComparison
                      ? `${formatMonthLabel(monthComparison.latest.month)} versus ${formatMonthLabel(
                          monthComparison.previous.month,
                        )}. ${spendTrustDetail}`
                      : spendTrustDetail}
                  </p>
                </>
              ) : monthComparison ? (
                <>
                  <p className="mt-3 text-2xl font-semibold text-text">
                    {signedCurrency(monthComparison.change)}
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    {formatMonthLabel(monthComparison.latest.month)} versus{' '}
                    {formatMonthLabel(monthComparison.previous.month)}
                  </p>
                </>
              ) : (
                <p className="mt-3 text-sm text-text-muted">
                  Jenny needs two completed months of clean spending history to
                  show a reliable month-over-month change.
                </p>
              )}
            </div>

            <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
              <p className="text-sm font-semibold text-text">Watch right now</p>
              <div className="mt-3 space-y-2">
                {watchItems.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    Jenny does not see a near-term budget risk right now.
                  </p>
                ) : (
                  watchItems.map((item) => (
                    <p key={item} className="text-sm text-text-muted">
                      {item}
                    </p>
                  ))
                )}
              </div>
            </div>
          </div>
          </SectionCard>

          <SectionCard
            variant="surface"
            title="Where Money Went"
            description="High-level category split with drilldown into the transactions behind it."
          >
          {spendTrustDegraded ? (
            <div className="mb-4 rounded-2xl border border-warning/25 bg-warning/5 px-4 py-3 text-sm text-text-muted">
              Category totals are {spendTrustLabel} right now. {spendTrustDetail}
            </div>
          ) : null}
          {categoryData.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
              Category visuals will appear once Jenny has enough transaction
              history to categorize your spending.
            </div>
          ) : (
            <div className="space-y-5">
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={categoryData}
                    layout="vertical"
                    margin={{ top: 10, right: 12, left: 12, bottom: 8 }}
                  >
                    <XAxis
                      type="number"
                      tickFormatter={formatThousandsAxis}
                      tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="category"
                      width={90}
                      tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip formatter={currencyTooltipFormatter} />
                    <Bar
                      dataKey="totalSpend"
                      radius={[0, 10, 10, 0]}
                      onClick={(_, index) => {
                        const entry = categoryData[index]
                        if (entry?.category) {
                          setSelectedCategory(entry.category)
                        }
                      }}
                    >
                      {categoryData.map((entry) => (
                        <Cell
                          key={entry.category}
                          fill={
                            entry.category === selectedCategory
                              ? 'var(--color-chart-orange)'
                              : 'var(--color-chart-cyan)'
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {selectedCategory ?? 'Recent category'}
                    </p>
                    <p className="text-xs text-text-muted">
                      {selectedTransactions.length > 0
                        ? 'Recent transactions behind this category.'
                        : 'No recent transactions are visible for this category yet.'}
                    </p>
                  </div>
                  {selectedCategory ? (
                    <button
                      type="button"
                      onClick={() => setSelectedCategory(null)}
                      className="text-xs font-medium text-text-muted transition-colors hover:text-text"
                    >
                      Clear
                    </button>
                  ) : null}
                </div>
                <div className="mt-4 space-y-2">
                  {(selectedCategory
                    ? selectedTransactions
                    : dashboard.reports.recentTransactions
                  )
                    .slice(0, 6)
                    .map((transaction) => (
                      <div
                        key={`${transaction.date}-${transaction.description}-${transaction.amount}`}
                        className="flex items-center justify-between gap-3 rounded-xl border border-border/30 bg-surface/60 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-text">
                            {transaction.merchant}
                          </p>
                          <p className="text-xs text-text-muted">
                            {transaction.date} · {transaction.category}
                          </p>
                        </div>
                        <span className="text-sm font-semibold tabular-nums text-text">
                          {formatCurrencyWhole(transaction.amount)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}
          </SectionCard>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard
              variant="surface"
              title="Recurring Bills"
              description="Known commitments and near-term due dates."
            >
            <div className="space-y-3">
              {dueSoonCommitments.length === 0 ? (
                <p className="text-sm text-text-muted">
                  Jenny needs more recurring bill history before it can flag
                  due dates here.
                </p>
              ) : (
                dueSoonCommitments.map((commitment) => (
                  <div
                    key={`${commitment.merchant}-${commitment.lastSeen}`}
                    className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-text">
                        {commitment.merchant}
                      </p>
                      <Badge variant={paceBadgeVariant(commitment.dueStatus)}>
                        {formatEnumLabel(commitment.dueStatus)}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm text-text-muted">
                      {formatCurrencyWhole(commitment.averageAmount)} ·{' '}
                      {formatEnumLabel(commitment.cadence)}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {commitment.daysUntilDue == null
                        ? 'Jenny does not have a due-date estimate yet.'
                        : commitment.daysUntilDue === 0
                          ? 'Expected today.'
                          : `Expected in ${commitment.daysUntilDue} day${commitment.daysUntilDue === 1 ? '' : 's'}.`}
                    </p>
                  </div>
                ))
              )}
            </div>
            </SectionCard>

            <SectionCard
              variant="surface"
              title="Savings Levers"
              description="Repeated-item price moves and merchants Jenny can optimize first."
            >
            <div className="space-y-3">
              {priceInsights.length === 0 && merchantHighlights.length === 0 ? (
                <p className="text-sm text-text-muted">
                  Jenny needs more merchant history before it can suggest price
                  and optimization levers.
                </p>
              ) : (
                <>
                  {priceInsights.map((insight) => (
                    <div
                      key={`${insight.merchant}-${insight.itemName}`}
                      className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">
                          {insight.itemName}
                        </p>
                        <Badge variant={priceInsightBadgeVariant(insight.signalType)}>
                          {priceInsightBadgeLabel(insight.signalType)}
                        </Badge>
                      </div>
                      <p className="mt-1 text-xs text-text-muted">
                        {insight.merchant} · {formatCurrency(insight.latestPrice)}{' '}
                        now versus {formatCurrency(insight.previousPrice)} on{' '}
                        {insight.previousDate}
                      </p>
                      {insight.latestUnitLabel || insight.previousUnitLabel ? (
                        <p className="mt-1 text-xs text-text-muted">
                          Size:{' '}
                          {insight.latestUnitLabel ?? 'Unknown'} now versus{' '}
                          {insight.previousUnitLabel ?? 'Unknown'} before
                          {insight.sizeChangePct != null
                            ? ` (${formatPercent(insight.sizeChangePct, {
                                decimals: 0,
                                sign: true,
                                nullDisplay: '—',
                              })})`
                            : ''}
                        </p>
                      ) : null}
                      {insight.latestUnitPrice != null &&
                      insight.previousUnitPrice != null ? (
                        <p className="mt-1 text-xs text-text-muted">
                          Unit price:{' '}
                          {formatCurrency(insight.latestUnitPrice, {
                            decimals: 2,
                          })}{' '}
                          now versus{' '}
                          {formatCurrency(insight.previousUnitPrice, {
                            decimals: 2,
                          })}{' '}
                          before
                          {insight.unitPriceChangePct != null
                            ? ` (${formatPercent(insight.unitPriceChangePct, {
                                decimals: 0,
                                sign: true,
                                nullDisplay: '—',
                              })})`
                            : ''}
                        </p>
                      ) : (
                        <p className="mt-1 text-xs text-text-muted">
                          Ticket price change:{' '}
                          {signedCurrency(insight.priceChange, {
                            decimals: 2,
                          })}
                        </p>
                      )}
                      <p className="mt-2 text-sm leading-relaxed text-text-muted">
                        {insight.recommendation}
                      </p>
                    </div>
                  ))}

                  {merchantHighlights.map((merchant) => (
                    <div
                      key={merchant.merchant}
                      className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-text">
                          {merchant.merchant}
                        </p>
                        <span className="text-sm font-semibold tabular-nums text-text">
                          {formatCurrencyWhole(merchant.totalSpend)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-text-muted">
                        {merchant.transactionCount} purchase
                        {merchant.transactionCount === 1 ? '' : 's'} ·{' '}
                        {formatEnumLabel(merchant.cadence)}
                      </p>
                      <p className="mt-2 text-sm leading-relaxed text-text-muted">
                        {merchant.recommendation}
                      </p>
                    </div>
                  ))}
                </>
              )}
            </div>
            </SectionCard>
          </div>
        </div>
      </div>
    </div>
  )
}
