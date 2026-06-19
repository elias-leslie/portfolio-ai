'use client'

import Link from 'next/link'
import { type ReactNode, useMemo, useState } from 'react'
import { CategoryPressureTable } from '@/components/money/CategoryPressureTable'
import { LeversTrendline } from '@/components/money/LeversTrendline'
import { buildLevers } from '@/components/money/lever-helpers'
import {
  buildSavingsActions,
  type SavingsAction,
  type SavingsActionKind,
  topTrendSeries,
} from '@/components/money/levers-action-model'
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
import {
  useHouseholdProducts,
  usePriceCheckStatus,
  useTriggerPriceCheck,
} from '@/lib/hooks/useHouseholdPurchases'

type LeverWindow = '1m' | '3m' | '6m' | '12m' | 'all'

const leverWindows: Array<{ value: LeverWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
  { value: 'all', label: 'All' },
]

const leverWindowMonths: Record<LeverWindow, number | null> = {
  '1m': 1,
  '3m': 3,
  '6m': 6,
  '12m': 12,
  all: null,
}

const actionLanes: Array<{
  key: SavingsActionKind
  title: string
  empty: string
}> = [
  {
    key: 'verified',
    title: 'Verified item savings',
    empty: 'No verified cheaper vendor options yet.',
  },
  {
    key: 'recurring_item',
    title: 'Recurring item price checks',
    empty: 'No recurring item drift above threshold in this window.',
  },
  {
    key: 'cut_candidate',
    title: 'Cut first',
    empty: 'No frequent non-essential merchant stands out.',
  },
  {
    key: 'deviation',
    title: 'Outside the norm',
    empty: 'No category or price deviations above threshold.',
  },
  {
    key: 'modeled',
    title: 'Modeled pressure',
    empty: 'No modeled category or merchant pressure yet.',
  },
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

function SavingsActionCard({ action }: { action: SavingsAction }) {
  return (
    <article className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">{action.title}</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-text-muted">
            {action.playbook}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant={action.tone}>{action.amountLabel}</Badge>
          <Badge variant="outline" className="text-[10px]">
            {action.evidenceLabel}
          </Badge>
        </div>
      </div>
      <p className="mt-3 text-sm text-text-muted">{action.detail}</p>
      {action.footnote ? (
        <p className="mt-2 rounded-lg border border-border/40 bg-surface-muted/20 px-3 py-2 text-xs text-text-muted">
          {action.footnote}
        </p>
      ) : null}
      {action.trend && action.trend.length > 0 ? (
        <div className="mt-3">
          <LeversTrendline
            series={action.trend}
            width={360}
            height={90}
            className="rounded-xl bg-surface/30 p-2"
          />
        </div>
      ) : null}
    </article>
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
  const { data: priceCheck } = usePriceCheckStatus()
  const { data: productsData } = useHouseholdProducts({
    sort: 'frequency',
    limit: 100,
  })
  const triggerPriceCheck = useTriggerPriceCheck()

  const totalSpend = spending?.summary.totalSpend ?? 0
  const averageMonthlySpend = spending?.summary.averageMonthlySpend ?? 0
  const averageCoverageMonths = spending?.summary.coverageMonths ?? 0
  const requestedCoverageMonths = leverWindowMonths[window]
  const hasShortCoverage =
    requestedCoverageMonths != null &&
    averageCoverageMonths > 0 &&
    averageCoverageMonths < requestedCoverageMonths
  const averageMonthlyDetail =
    averageCoverageMonths > 0
      ? hasShortCoverage
        ? `${averageCoverageMonths} complete month${averageCoverageMonths === 1 ? '' : 's'} with data`
        : 'Complete-month run-rate'
      : 'No complete spend coverage'
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

  const visiblePriceFindings = useMemo(
    () =>
      (priceCheck?.openFindings ?? []).filter((row) =>
        search.trim()
          ? `${row.productName ?? ''} ${row.vendorKey ?? ''} ${row.kind}`
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          : true,
      ),
    [priceCheck?.openFindings, search],
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
        priceFindings: [],
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

  const savingsActions = useMemo(
    () =>
      buildSavingsActions({
        priceFindings: visiblePriceFindings,
        products: productsData?.products ?? [],
        transactions: spending?.transactions ?? [],
        merchantRows,
        categoryMonthlyTrend: spending?.categoryMonthlyTrend ?? [],
        modeledLevers: levers,
        priceInsights: visiblePriceInsights,
        coverageMonths: spending?.summary.coverageMonths ?? 0,
      }),
    [
      levers,
      merchantRows,
      productsData?.products,
      spending?.categoryMonthlyTrend,
      spending?.summary.coverageMonths,
      spending?.transactions,
      visibleCategoryRows,
      visiblePriceFindings,
      visiblePriceInsights,
    ],
  )

  const actionTrendSeries = useMemo(
    () => topTrendSeries(savingsActions),
    [savingsActions],
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
              {averageMonthlyDetail}
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
        {hasShortCoverage ? (
          <p className="mt-3 rounded-xl border border-warning/35 bg-warning/10 px-3 py-2 text-xs text-text">
            This household does not have {requestedCoverageMonths} complete
            months of spend data in the selected window. Monthly averages and
            modeled trims use the {averageCoverageMonths} complete covered month
            {averageCoverageMonths === 1 ? '' : 's'} instead of dividing by{' '}
            {requestedCoverageMonths}.
          </p>
        ) : null}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Savings Action Board"
        description="Priority order: verified cheaper options, recurring-item price checks, non-essential cuts, deviations from normal, then modeled pressure."
        actions={
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => triggerPriceCheck.mutate({})}
            disabled={triggerPriceCheck.isPending}
          >
            Run price check
          </Button>
        }
      >
        <div className="mb-4 grid gap-3 lg:grid-cols-3">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Last price check
            </p>
            <p className="mt-2 text-sm font-semibold text-text">
              {priceCheck?.latestRun?.finishedAt
                ? new Date(priceCheck.latestRun.finishedAt).toLocaleDateString()
                : 'Not run yet'}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {priceCheck?.latestRun
                ? `${priceCheck.latestRun.status} · ${priceCheck.latestRun.quoteCount} quote${priceCheck.latestRun.quoteCount === 1 ? '' : 's'} · ${priceCheck.latestRun.findingCount} finding${priceCheck.latestRun.findingCount === 1 ? '' : 's'}`
                : 'Run a price check to find verified cheaper vendors.'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4 lg:col-span-2">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Trendlines to inspect
            </p>
            <div className="mt-2">
              <LeversTrendline series={actionTrendSeries} />
            </div>
          </div>
        </div>

        {savingsActions.length > 0 ? (
          <div className="space-y-5">
            {actionLanes.map((lane) => {
              const laneActions = savingsActions
                .filter((action) => action.kind === lane.key)
                .slice(0, 4)
              return (
                <div key={lane.key} className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-text">
                      {lane.title}
                    </p>
                    <Badge variant="outline">{laneActions.length}</Badge>
                  </div>
                  {laneActions.length > 0 ? (
                    <div className="grid gap-3 xl:grid-cols-2">
                      {laneActions.map((action) => (
                        <SavingsActionCard key={action.id} action={action} />
                      ))}
                    </div>
                  ) : (
                    <p className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-4 text-sm text-text-muted">
                      {lane.empty}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        ) : search.trim() ? (
          <UnlockPanel
            title="No savings actions match this search."
            detail="Clear the search or widen the window to see prioritized savings work."
          />
        ) : (
          <UnlockPanel
            title="Not enough spend history to prioritize savings."
            detail="Upload statements or connect an account in Intake, or widen the window above."
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
        title="Price Signals moved to Purchases"
        description="Levers summarizes material price pressure; the item catalog, vendor quotes, findings, and shopping-list optimizer now live in Purchases."
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-text-muted">
            {visiblePriceInsights.length} price signal
            {visiblePriceInsights.length === 1 ? '' : 's'} match this lever
            window.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href="/money?tab=purchases">Open Purchases</Link>
          </Button>
        </div>
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
