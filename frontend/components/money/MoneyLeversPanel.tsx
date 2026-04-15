'use client'

import { useMemo, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  HouseholdPriceInsight,
  HouseholdRecurringCommitment,
} from '@/lib/api/household'
import { useHouseholdSpending } from '@/lib/hooks/useHousehold'
import { formatCurrency, formatEnumLabel, formatPercent } from '@/lib/formatters'

type LeverWindow = '1m' | '3m' | '6m' | '12m' | 'all'

const leverWindows: Array<{ value: LeverWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
  { value: 'all', label: 'All' },
]

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

interface MoneyLeversPanelProps {
  priceInsights: HouseholdPriceInsight[]
  recurringCommitments: HouseholdRecurringCommitment[]
}

export function MoneyLeversPanel({
  priceInsights,
  recurringCommitments,
}: MoneyLeversPanelProps) {
  const [window, setWindow] = useState<LeverWindow>('1m')
  const [search, setSearch] = useState('')
  const {
    data: spending,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdSpending({ window })

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

  const dueSoonCommitments = useMemo(
    () =>
      recurringCommitments
        .filter((row) => row.daysUntilDue != null && row.daysUntilDue <= 14)
        .sort((left, right) => (left.daysUntilDue ?? 999) - (right.daysUntilDue ?? 999)),
    [recurringCommitments],
  )

  const topThreeShare = useMemo(() => {
    const total = spending?.summary.totalSpend ?? 0
    if (total <= 0) {
      return 0
    }
    const topThree = merchantRows.slice(0, 3).reduce((sum, row) => sum + row.totalSpend, 0)
    return topThree / total
  }, [merchantRows, spending?.summary.totalSpend])

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load levers."
        detail="Retry to refresh merchant concentration and price signals."
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
        description="Merchant drag uses same canonical spend rows as Spending. Price moves come from order-history evidence and are labeled separately."
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
        <div className="grid gap-3 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">Window spend</p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(spending?.summary.totalSpend, { decimals: 2 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {spending?.summary.timeframeLabel ?? 'Selected timeframe'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">Top 3 share</p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatPercent(topThreeShare * 100, { decimals: 0 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">Concentration inside spend view</p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">Price signals</p>
            <p className="mt-2 text-base font-semibold text-text">{visiblePriceInsights.length}</p>
            <p className="mt-1 text-xs text-text-muted">Order-history price or shrink signals</p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">Bills due soon</p>
            <p className="mt-2 text-base font-semibold text-text">{dueSoonCommitments.length}</p>
            <p className="mt-1 text-xs text-text-muted">Expected within next 14 days</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Merchant Drag"
        description={`Top merchants from ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. Same canonical spend math as the Spending tab.`}
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[40vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
            <table className="min-w-[980px] w-full border-separate border-spacing-0 text-sm">
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
                    Avg ticket
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Tx
                  </th>
                </tr>
              </thead>
              <tbody>
                {isLoading && !spending ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-10 text-center text-sm text-text-muted">
                      Loading merchant levers...
                    </td>
                  </tr>
                ) : merchantRows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-10 text-center text-sm text-text-muted">
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
                        {formatCurrency(row.totalSpend / row.transactionCount, { decimals: 2 })}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {row.transactionCount}
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
        description="Order-history evidence only. Separate from spend totals so ticket-price insight does not pollute ledger math."
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[36vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
            <table className="min-w-[1180px] w-full border-separate border-spacing-0 text-sm">
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
                {visiblePriceInsights.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-10 text-center text-sm text-text-muted">
                      No price signals match current filters.
                    </td>
                  </tr>
                ) : (
                  visiblePriceInsights.map((row) => (
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
                        <div className="text-xs text-text-muted">{formatLeverDate(row.latestDate)}</div>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.previousPrice, { decimals: 2 })}
                        <div className="text-xs text-text-muted">{formatLeverDate(row.previousDate)}</div>
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
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Bills Due Soon"
        description="Recurring commitments from canonical ledger cadence inference."
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[24vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
            <table className="min-w-[940px] w-full border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                <tr>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Merchant
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Category
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Cadence
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Avg amount
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Due
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {dueSoonCommitments.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-10 text-center text-sm text-text-muted">
                      No near-term bill due signal right now.
                    </td>
                  </tr>
                ) : (
                  dueSoonCommitments.map((row) => (
                    <tr
                      key={`${row.merchant}-${row.lastSeen}`}
                      className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                    >
                      <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                        {row.merchant}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-text">
                        {row.category}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-text">
                        {formatEnumLabel(row.cadence)}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {formatCurrency(row.averageAmount, { decimals: 2 })}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                        {row.daysUntilDue == null
                          ? '—'
                          : row.daysUntilDue === 0
                            ? 'Today'
                            : `${row.daysUntilDue}d`}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5">
                        <Badge
                          variant={
                            row.dueStatus === 'due_soon'
                              ? 'warning'
                              : row.dueStatus === 'overdue'
                                ? 'destructive'
                                : 'outline'
                          }
                        >
                          {formatEnumLabel(row.dueStatus)}
                        </Badge>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
