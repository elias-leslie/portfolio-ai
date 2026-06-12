'use client'

import Link from 'next/link'
import { type ReactNode, useMemo, useState } from 'react'
import { CategoryPressureTable } from '@/components/money/CategoryPressureTable'
import { buildLevers } from '@/components/money/lever-helpers'
import { MerchantDragTable } from '@/components/money/MerchantDragTable'
import { aggregateMerchants } from '@/components/money/merchant-aggregation'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import { formatCurrency, formatPercent } from '@/lib/formatters'
import { useHouseholdSpending } from '@/lib/hooks/useHousehold'

type LeverWindow = '1m' | '3m' | '6m' | '12m' | 'all'

const leverWindows: Array<{ value: LeverWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
  { value: 'all', label: 'All' },
]

function UnlockPanel({
  title,
  detail,
  action,
}: {
  title: string
  detail: string
  action?: ReactNode
}) {
  return (
    <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6">
      <p className="text-sm font-semibold text-text">{title}</p>
      <p className="mt-2 text-sm text-text-muted">{detail}</p>
      {action ? <div className="mt-4">{action}</div> : null}
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
    return Array.from(aggregateMerchants(spending?.transactions).values())
      .filter((row) =>
        search.trim()
          ? `${row.merchant} ${row.category} ${row.essentiality}`
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          : true,
      )
      .sort((left, right) => right.totalSpend - left.totalSpend)
  }, [search, spending?.transactions])

  // Search also narrows category surfaces: a category stays visible when its own
  // text matches, or when a search-matched merchant rolls up into it (Amazon ⊂ Retail).
  const visibleCategoryRows = useMemo(() => {
    const term = search.trim().toLowerCase()
    if (!term) {
      return categoryRows
    }
    const matchedMerchantCategories = new Set(
      merchantRows.map((row) => row.category),
    )
    return categoryRows.filter(
      (row) =>
        `${row.category} ${row.essentiality}`.toLowerCase().includes(term) ||
        matchedMerchantCategories.has(row.category),
    )
  }, [categoryRows, merchantRows, search])

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
      visibleCategoryRows.find(
        (row) =>
          row.essentiality === 'discretionary' && row.averageMonthlySpend > 0,
      ) ?? null,
    [visibleCategoryRows],
  )

  const topDiscretionaryMerchant = useMemo(
    () =>
      merchantRows.find(
        (row) => row.essentiality === 'discretionary' && row.totalSpend > 0,
      ) ?? null,
    [merchantRows],
  )

  const subscriptionCategory = useMemo(
    () =>
      visibleCategoryRows.find((row) => row.category === 'Subscriptions') ??
      null,
    [visibleCategoryRows],
  )

  const bestPriceSignal = useMemo(
    () =>
      [...visiblePriceInsights]
        .filter(
          (row) =>
            row.signalType === 'price_up' ||
            row.signalType === 'unit_price_up' ||
            row.signalType === 'shrinkflation',
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

  const levers = useMemo(
    () =>
      buildLevers({
        subscriptionCategory,
        topDiscretionaryCategory,
        topDiscretionaryMerchant,
        topThreeShare,
        averageMonthlySpend,
        coverageMonths: spending?.summary.coverageMonths,
        bestPriceSignal,
      }),
    [
      averageMonthlySpend,
      bestPriceSignal,
      spending?.summary.coverageMonths,
      subscriptionCategory,
      topDiscretionaryCategory,
      topDiscretionaryMerchant,
      topThreeShare,
    ],
  )

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
              {formatCurrency(totalSpend, { decimals: 0 })}
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
              {formatCurrency(averageMonthlySpend, { decimals: 0 })}
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
              {visibleCategoryRows.length}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {search.trim()
                ? 'Spend categories matching search'
                : 'Spend categories in this window'}
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Best Levers Right Now"
        description="Trim, pause, or watch signals ranked for this window. Savings use fixed rule-of-thumb trim rates (shown on each lever), not measured elasticities."
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
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant={lever.tone}>
                      {formatCurrency(lever.monthlySavings, { decimals: 0 })}/mo
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      Modeled
                    </Badge>
                  </div>
                </div>
                <p className="mt-3 text-sm text-text-muted">{lever.detail}</p>
                <p className="mt-3 text-sm font-medium text-text">
                  Annual room:{' '}
                  {formatCurrency(lever.annualSavings, { decimals: 0 })}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {lever.id === 'price-signal' || lever.id === 'concentration'
                    ? `Modeled at ${formatPercent(lever.trimRate * 100, { decimals: 0 })} of monthly spend — rule of thumb, not a guaranteed saving.`
                    : `Modeled at ${formatPercent(lever.trimRate * 100, { decimals: 0 })} trim — rule of thumb, not a guaranteed saving.`}
                </p>
                {lever.note ? (
                  <p className="mt-2 rounded-lg border border-border/40 bg-surface-muted/20 px-3 py-2 text-xs text-text-muted">
                    {lever.note}
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        ) : search.trim() ? (
          <UnlockPanel
            title="No levers match this search."
            detail="Clear the search or widen the window to see ranked trim levers."
          />
        ) : (
          <UnlockPanel
            title="Not enough spend history in this window to rank trims."
            detail="Upload statements or connect an account in Intake, or widen the window above — ranked levers appear once categories and merchants have coverage."
            action={
              <Button asChild size="sm" variant="outline">
                <Link href="/money?tab=intake">Go to Intake</Link>
              </Button>
            }
          />
        )}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Category Pressure"
        description={`Where monthly spend is actually hardening inside ${spending?.summary.timeframeLabel ?? 'this window'}.`}
      >
        <CategoryPressureTable
          rows={visibleCategoryRows}
          isLoading={isLoading}
          hasData={Boolean(spending)}
        />
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Merchant Drag"
        description={`Top merchants from ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. Same canonical spend math as the Spending tab.`}
      >
        <MerchantDragTable
          rows={merchantRows}
          totalSpend={totalSpend}
          isLoading={isLoading}
          hasData={Boolean(spending)}
        />
      </SectionCard>
    </div>
  )
}
