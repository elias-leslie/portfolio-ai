'use client'

import { useMemo, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  HouseholdPriceInsight,
  HouseholdSpendingCategory,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import { useHouseholdSpending } from '@/lib/hooks/useHousehold'

type LeverWindow = '1m' | '3m' | '6m' | '12m' | 'all'

type LeverOpportunity = {
  id: string
  title: string
  playbook: string
  monthlySavings: number
  annualSavings: number
  detail: string
  tone: 'success' | 'warning' | 'outline'
  additive: boolean
}

const leverWindows: Array<{ value: LeverWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
  { value: 'all', label: 'All' },
]

const modeledTrimRates: Record<string, number> = {
  Subscriptions: 0.2,
  Dining: 0.15,
  Retail: 0.12,
  Travel: 0.1,
  Fitness: 0.15,
  Home: 0.12,
  Household: 0.06,
}

function formatLeverDate(value?: string | null) {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function categoryPlaybook(category: string, essentiality: string) {
  if (category === 'Subscriptions') {
    return 'Sweep recurring line items'
  }
  if (category === 'Retail') {
    return 'Batch orders and set cap'
  }
  if (category === 'Travel') {
    return 'Pre-approve trips before booking'
  }
  if (category === 'Dining') {
    return 'Cap convenience spend'
  }
  if (essentiality === 'discretionary') {
    return 'Trim by rule, not memory'
  }
  if (essentiality === 'mixed') {
    return 'Split wants from needs'
  }
  return 'Protect, monitor, renegotiate'
}

function trimRateForCategory(category: string, essentiality: string) {
  if (category in modeledTrimRates) {
    return modeledTrimRates[category]
  }
  if (essentiality === 'discretionary') {
    return 0.1
  }
  if (essentiality === 'mixed') {
    return 0.05
  }
  return 0.0
}

function merchantPlaybook(
  category: string,
  essentiality: string,
  transactionCount: number,
) {
  if (category === 'Subscriptions') {
    return 'Cancel, downgrade, or annualize'
  }
  if (transactionCount >= 8 && essentiality === 'discretionary') {
    return 'Add a merchant cap'
  }
  if (essentiality === 'discretionary') {
    return 'Reduce frequency first'
  }
  if (essentiality === 'mixed') {
    return 'Separate staples from drift'
  }
  return 'Keep, then price-check'
}

function UnlockPanel({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6">
      <p className="text-sm font-semibold text-text">{title}</p>
      <p className="mt-2 text-sm text-text-muted">{detail}</p>
    </div>
  )
}

interface MoneyLeversPanelProps {
  priceInsights: HouseholdPriceInsight[]
}

export function MoneyLeversPanel({ priceInsights }: MoneyLeversPanelProps) {
  const [window, setWindow] = useState<LeverWindow>('3m')
  const [search, setSearch] = useState('')
  const {
    data: spending,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdSpending({ window })

  const totalSpend = spending?.summary.totalSpend ?? 0
  const averageMonthlySpend = spending?.summary.averageMonthlySpend ?? 0
  const categoryRows = useMemo(
    () =>
      [...(spending?.categories ?? [])].sort(
        (left, right) => right.averageMonthlySpend - left.averageMonthlySpend,
      ),
    [spending?.categories],
  )

  const merchantRows = useMemo(() => {
    const buckets = new Map<
      string,
      {
        merchant: string
        totalSpend: number
        transactionCount: number
        category: string
        essentiality: string
      }
    >()
    for (const row of spending?.transactions ?? []) {
      const key = row.merchant.trim().toLowerCase()
      const current = buckets.get(key)
      if (current) {
        current.totalSpend += row.amount
        current.transactionCount += 1
        continue
      }
      buckets.set(key, {
        merchant: row.merchant,
        totalSpend: row.amount,
        transactionCount: 1,
        category: row.category,
        essentiality: row.essentiality,
      })
    }
    return Array.from(buckets.values())
      .filter((row) =>
        search.trim()
          ? `${row.merchant} ${row.category} ${row.essentiality}`
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          : true,
      )
      .sort((left, right) => right.totalSpend - left.totalSpend)
  }, [search, spending?.transactions])

  const visiblePriceInsights = useMemo(
    () =>
      priceInsights.filter((row) =>
        search.trim()
          ? `${row.merchant} ${row.itemName} ${row.signalType}`
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          : true,
      ),
    [priceInsights, search],
  )

  const topThreeShare = useMemo(() => {
    if (totalSpend <= 0) {
      return 0
    }
    const topThree = merchantRows
      .slice(0, 3)
      .reduce((sum, row) => sum + row.totalSpend, 0)
    return topThree / totalSpend
  }, [merchantRows, totalSpend])

  const topDiscretionaryCategory = useMemo(
    () =>
      categoryRows.find(
        (row) =>
          row.essentiality === 'discretionary' && row.averageMonthlySpend > 0,
      ) ?? null,
    [categoryRows],
  )

  const topDiscretionaryMerchant = useMemo(
    () =>
      merchantRows.find(
        (row) => row.essentiality === 'discretionary' && row.totalSpend > 0,
      ) ?? null,
    [merchantRows],
  )

  const subscriptionCategory = useMemo(
    () => categoryRows.find((row) => row.category === 'Subscriptions') ?? null,
    [categoryRows],
  )

  const bestPriceSignal = useMemo(
    () =>
      [...visiblePriceInsights]
        .filter(
          (row) =>
            row.signalType === 'price_up' || row.signalType === 'shrinkflation',
        )
        .sort((left, right) => {
          const leftScore = Math.max(
            Math.abs(left.unitPriceChangePct ?? 0),
            Math.abs(left.priceChangePct ?? 0),
          )
          const rightScore = Math.max(
            Math.abs(right.unitPriceChangePct ?? 0),
            Math.abs(right.priceChangePct ?? 0),
          )
          return rightScore - leftScore
        })[0] ?? null,
    [visiblePriceInsights],
  )

  const levers = useMemo(() => {
    const opportunities: LeverOpportunity[] = []

    const push = (value: LeverOpportunity | null) => {
      if (!value || value.monthlySavings <= 0) {
        return
      }
      opportunities.push(value)
    }

    if (subscriptionCategory) {
      const monthlySavings = subscriptionCategory.averageMonthlySpend * 0.2
      push({
        id: 'subscriptions',
        title: 'Subscription sweep first',
        playbook: 'Cancel, downgrade, or annualize',
        monthlySavings,
        annualSavings: monthlySavings * 12,
        detail: `${subscriptionCategory.transactionCount} subscription charges are running about ${formatCurrency(subscriptionCategory.averageMonthlySpend, { decimals: 0 })}/mo. A 20% trim frees real room fast.`,
        tone: 'warning',
        additive: true,
      })
    }

    if (topDiscretionaryCategory) {
      const trimRate = trimRateForCategory(
        topDiscretionaryCategory.category,
        topDiscretionaryCategory.essentiality,
      )
      const monthlySavings =
        topDiscretionaryCategory.averageMonthlySpend * trimRate
      push({
        id: 'category',
        title: `${topDiscretionaryCategory.category} is biggest trim lever`,
        playbook: categoryPlaybook(
          topDiscretionaryCategory.category,
          topDiscretionaryCategory.essentiality,
        ),
        monthlySavings,
        annualSavings: monthlySavings * 12,
        detail: `${topDiscretionaryCategory.category} is ${formatCurrency(topDiscretionaryCategory.averageMonthlySpend, { decimals: 0 })}/mo and ${formatPercent(topDiscretionaryCategory.shareOfSpend * 100, { decimals: 0 })} of this window.`,
        tone: 'warning',
        additive: topDiscretionaryCategory.category !== 'Subscriptions',
      })
    }

    if (topDiscretionaryMerchant) {
      const monthlyMerchantSpend =
        spending?.summary.coverageMonths && spending.summary.coverageMonths > 0
          ? topDiscretionaryMerchant.totalSpend /
            spending.summary.coverageMonths
          : topDiscretionaryMerchant.totalSpend
      const monthlySavings = monthlyMerchantSpend * 0.15
      push({
        id: 'merchant',
        title: `${topDiscretionaryMerchant.merchant} is merchant drag`,
        playbook: merchantPlaybook(
          topDiscretionaryMerchant.category,
          topDiscretionaryMerchant.essentiality,
          topDiscretionaryMerchant.transactionCount,
        ),
        monthlySavings,
        annualSavings: monthlySavings * 12,
        detail: `${topDiscretionaryMerchant.transactionCount} charges in this window. Merchant alone ran ${formatCurrency(topDiscretionaryMerchant.totalSpend, { decimals: 0 })}.`,
        tone: 'outline',
        additive: false,
      })
    }

    if (topThreeShare >= 0.35 && averageMonthlySpend > 0) {
      const monthlySavings = averageMonthlySpend * 0.05
      push({
        id: 'concentration',
        title: 'Top merchants are too concentrated',
        playbook: 'Set merchant caps and pre-approve outliers',
        monthlySavings,
        annualSavings: monthlySavings * 12,
        detail: `Top 3 merchants drive ${formatPercent(topThreeShare * 100, { decimals: 0 })} of spend here. A 5% reset on those names saves more than scattered cuts.`,
        tone: 'outline',
        additive: false,
      })
    }

    if (bestPriceSignal) {
      const signalChange = Math.max(
        Math.abs(bestPriceSignal.unitPriceChangePct ?? 0),
        Math.abs(bestPriceSignal.priceChangePct ?? 0),
      )
      const monthlySavings = averageMonthlySpend * 0.02
      push({
        id: 'price-signal',
        title: `${bestPriceSignal.itemName} price drift needs a check`,
        playbook: bestPriceSignal.shrinkflationFlag
          ? 'Swap or size-check before rebuy'
          : 'Price-compare before next order',
        monthlySavings,
        annualSavings: monthlySavings * 12,
        detail: `${bestPriceSignal.merchant} shows ${formatPercent(signalChange, { decimals: 0, sign: true })} drift by ticket or unit math. Use it as a trigger to compare, not autopilot.`,
        tone: 'warning',
        additive: false,
      })
    }

    return opportunities
      .sort((left, right) => right.monthlySavings - left.monthlySavings)
      .slice(0, 4)
  }, [
    averageMonthlySpend,
    bestPriceSignal,
    spending?.summary.coverageMonths,
    subscriptionCategory,
    topDiscretionaryCategory,
    topDiscretionaryMerchant,
    topThreeShare,
  ])

  const modeledTrimTotal = useMemo(
    () =>
      levers
        .filter((row) => row.additive)
        .reduce((sum, row) => sum + row.monthlySavings, 0),
    [levers],
  )

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load levers."
        detail="Retry to refresh merchant concentration and trim opportunities."
        onRetry={() => {
          void refetch()
        }}
        isRetrying={isFetching}
      />
    )
  }

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Savings Levers"
        description="Canonical spend rows first. Modeled trims are explicit rules of thumb, not fake certainty."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {leverWindows.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={window === option.value ? 'default' : 'outline'}
                onClick={() => setWindow(option.value)}
              >
                {option.label}
              </Button>
            ))}
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search merchant, item, or signal"
              aria-label="Search savings levers"
              className="w-[280px]"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                void refetch()
              }}
              disabled={isFetching}
            >
              Refresh
            </Button>
          </div>
        }
      >
        <div className="grid gap-3 xl:grid-cols-5">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Window spend
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(totalSpend, { decimals: 2 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {spending?.summary.timeframeLabel ?? 'Selected timeframe'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Avg monthly
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(averageMonthlySpend, { decimals: 2 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Canonical monthly run-rate
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Top 3 share
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatPercent(topThreeShare * 100, { decimals: 0 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Merchant concentration
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Additive trim
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(modeledTrimTotal, { decimals: 0 })}/mo
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Non-overlapping category rules
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Tracked pressure
            </p>
            <p className="mt-2 text-base font-semibold text-text">
              {categoryRows.length}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Spend categories in this window
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Best Levers Right Now"
        description="Trim, pause, or watch signals ranked for this window."
      >
        {levers.length > 0 ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {levers.map((lever) => (
              <article
                key={lever.id}
                className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {lever.title}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-text-muted">
                      {lever.playbook}
                    </p>
                  </div>
                  <Badge variant={lever.tone}>
                    {formatCurrency(lever.monthlySavings, { decimals: 0 })}/mo
                  </Badge>
                </div>
                <p className="mt-3 text-sm text-text-muted">{lever.detail}</p>
                <p className="mt-3 text-sm font-medium text-text">
                  Annual room:{' '}
                  {formatCurrency(lever.annualSavings, { decimals: 0 })}
                </p>
              </article>
            ))}
          </div>
        ) : (
          <UnlockPanel
            title="Need more spend density before ranking trims."
            detail="Once canonical transactions cover enough categories and merchants in this window, Portfolio AI can rank the best trim candidates instead of just listing rows."
          />
        )}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Category Pressure"
        description={`Where monthly spend is actually hardening inside ${spending?.summary.timeframeLabel ?? 'this window'}.`}
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[34vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
            <table className="w-full min-w-[1100px] border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                <tr>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Category
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Type
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Monthly
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Share
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Tx
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Trim rule
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Move
                  </th>
                </tr>
              </thead>
              <tbody>
                {isLoading && !spending ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      Loading category levers...
                    </td>
                  </tr>
                ) : categoryRows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      No category pressure in this window.
                    </td>
                  </tr>
                ) : (
                  categoryRows.map((row: HouseholdSpendingCategory) => {
                    const trimRate = trimRateForCategory(
                      row.category,
                      row.essentiality,
                    )
                    return (
                      <tr
                        key={`${row.category}-${row.essentiality}`}
                        className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                      >
                        <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                          {row.category}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5">
                          <Badge
                            variant={
                              row.essentiality === 'essential'
                                ? 'success'
                                : row.essentiality === 'discretionary'
                                  ? 'warning'
                                  : 'outline'
                            }
                          >
                            {formatEnumLabel(row.essentiality)}
                          </Badge>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                          {formatCurrency(row.averageMonthlySpend, {
                            decimals: 2,
                          })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                          {formatPercent(row.shareOfSpend * 100, {
                            decimals: 0,
                          })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                          {row.transactionCount}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                          {trimRate > 0
                            ? formatCurrency(
                                row.averageMonthlySpend * trimRate,
                                {
                                  decimals: 0,
                                },
                              )
                            : '—'}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                          {categoryPlaybook(row.category, row.essentiality)}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Merchant Drag"
        description={`Top merchants from ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. Same canonical spend math as the Spending tab.`}
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[40vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
            <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                <tr>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Merchant
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Category
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Type
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Total
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Share
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Avg ticket
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Tx
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Move
                  </th>
                </tr>
              </thead>
              <tbody>
                {isLoading && !spending ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      Loading merchant levers...
                    </td>
                  </tr>
                ) : merchantRows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      No merchant levers in this timeframe.
                    </td>
                  </tr>
                ) : (
                  merchantRows.slice(0, 50).map((row) => (
                    <tr
                      key={row.merchant}
                      className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                    >
                      <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                        {row.merchant}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-text">
                        {row.category}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5">
                        <Badge
                          variant={
                            row.essentiality === 'essential'
                              ? 'success'
                              : row.essentiality === 'discretionary'
                                ? 'warning'
                                : 'outline'
                          }
                        >
                          {formatEnumLabel(row.essentiality)}
                        </Badge>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.totalSpend, { decimals: 2 })}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {totalSpend > 0
                          ? formatPercent((row.totalSpend / totalSpend) * 100, {
                              decimals: 0,
                            })
                          : '—'}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.totalSpend / row.transactionCount, {
                          decimals: 2,
                        })}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {row.transactionCount}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                        {merchantPlaybook(
                          row.category,
                          row.essentiality,
                          row.transactionCount,
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Price Signals"
        description="Order-history evidence only. Ticket or unit drift belongs here, not in ledger totals."
      >
        {visiblePriceInsights.length > 0 ? (
          <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
            <div className="max-h-[32vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
              <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
                <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                  <tr>
                    <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Item
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Merchant
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Signal
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Latest
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Prior
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Delta
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Confidence
                    </th>
                    <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Notes
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visiblePriceInsights.map((row) => (
                    <tr
                      key={`${row.merchant}-${row.itemName}`}
                      className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                    >
                      <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                        {row.itemName}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-text">
                        {row.merchant}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5">
                        <Badge
                          variant={
                            row.signalType === 'shrinkflation'
                              ? 'destructive'
                              : row.signalType === 'price_down'
                                ? 'success'
                                : 'warning'
                          }
                        >
                          {formatEnumLabel(row.signalType)}
                        </Badge>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.latestPrice, { decimals: 2 })}
                        <div className="text-xs text-text-muted">
                          {formatLeverDate(row.latestDate)}
                        </div>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.previousPrice, { decimals: 2 })}
                        <div className="text-xs text-text-muted">
                          {formatLeverDate(row.previousDate)}
                        </div>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.priceChange, { decimals: 2 })}
                        <div className="text-xs text-text-muted">
                          {formatPercent(row.priceChangePct ?? 0, {
                            decimals: 0,
                            sign: true,
                          })}
                        </div>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatPercent(row.confidence * 100, { decimals: 0 })}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                        {row.recommendation}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <UnlockPanel
            title="No price-drift evidence yet."
            detail="Add receipt or order-history evidence and this section will flag ticket creep, unit-price jumps, and shrinkflation before they silently harden."
          />
        )}
      </SectionCard>
    </div>
  )
}
