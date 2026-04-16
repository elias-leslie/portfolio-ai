'use client'

import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import { useHouseholdSpending } from '@/lib/hooks/useHousehold'
import { cn } from '@/lib/utils'

type SpendingWindow = '1m' | '3m' | '6m' | '12m' | 'all'
type CategorySortKey = 'category' | 'type' | 'total' | 'avg' | 'share' | 'count'
type TransactionSortKey =
  | 'date'
  | 'merchant'
  | 'account'
  | 'category'
  | 'type'
  | 'amount'
  | 'source'

const spendingWindows: Array<{ value: SpendingWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
  { value: 'all', label: 'All' },
]

function formatSpendingDate(value: string) {
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

function compareText(
  left: string | null | undefined,
  right: string | null | undefined,
) {
  return (left ?? '').localeCompare(right ?? '')
}

function compareNumber(
  left: number | null | undefined,
  right: number | null | undefined,
) {
  return (left ?? 0) - (right ?? 0)
}

function sortIcon(active: boolean, direction: 'asc' | 'desc') {
  if (!active) {
    return <ArrowUpDown className="h-3.5 w-3.5 text-text-muted" />
  }
  return direction === 'asc' ? (
    <ArrowUp className="h-3.5 w-3.5 text-text" />
  ) : (
    <ArrowDown className="h-3.5 w-3.5 text-text" />
  )
}

export function MoneySpendingPanel() {
  const [window, setWindow] = useState<SpendingWindow>('1m')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedAccount, setSelectedAccount] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [categorySortKey, setCategorySortKey] =
    useState<CategorySortKey>('total')
  const [categorySortDirection, setCategorySortDirection] = useState<
    'asc' | 'desc'
  >('desc')
  const [transactionSortKey, setTransactionSortKey] =
    useState<TransactionSortKey>('date')
  const [transactionSortDirection, setTransactionSortDirection] = useState<
    'asc' | 'desc'
  >('desc')
  const deferredSearch = useDeferredValue(search.trim().toLowerCase())
  const {
    data: spending,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdSpending({ window })

  useEffect(() => {
    if (!selectedCategory) {
      return
    }
    if (
      !spending?.categories.some((entry) => entry.category === selectedCategory)
    ) {
      setSelectedCategory(null)
    }
  }, [selectedCategory, spending?.categories])

  const accountOptions = useMemo(() => {
    const labels = new Set<string>()
    for (const row of spending?.transactions ?? []) {
      const label = row.accountLabel?.trim()
      if (label) {
        labels.add(label)
      }
    }
    return Array.from(labels).sort((left, right) => left.localeCompare(right))
  }, [spending?.transactions])

  useEffect(() => {
    if (selectedAccount === 'all' || selectedAccount === '__unassigned__') {
      return
    }
    if (!accountOptions.includes(selectedAccount)) {
      setSelectedAccount('all')
    }
  }, [accountOptions, selectedAccount])

  const visibleTransactions = useMemo(() => {
    const rows = spending?.transactions ?? []
    return rows.filter((row) => {
      if (selectedCategory && row.category !== selectedCategory) {
        return false
      }
      if (
        selectedAccount !== 'all' &&
        (row.accountLabel?.trim() ?? '__unassigned__') !== selectedAccount
      ) {
        return false
      }
      if (!deferredSearch) {
        return true
      }
      return [
        row.merchant,
        row.description,
        row.accountLabel,
        row.category,
        row.essentiality,
        row.sourceType,
        row.documentType,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(deferredSearch))
    })
  }, [
    deferredSearch,
    selectedAccount,
    selectedCategory,
    spending?.transactions,
  ])

  const sortedCategories = useMemo(() => {
    const rows = [...(spending?.categories ?? [])]
    rows.sort((left, right) => {
      let result = 0
      switch (categorySortKey) {
        case 'category':
          result = compareText(left.category, right.category)
          break
        case 'type':
          result = compareText(left.essentiality, right.essentiality)
          break
        case 'total':
          result = compareNumber(left.totalSpend, right.totalSpend)
          break
        case 'avg':
          result = compareNumber(
            left.averageMonthlySpend,
            right.averageMonthlySpend,
          )
          break
        case 'share':
          result = compareNumber(left.shareOfSpend, right.shareOfSpend)
          break
        case 'count':
          result = compareNumber(left.transactionCount, right.transactionCount)
          break
      }
      return categorySortDirection === 'asc' ? result : -result
    })
    return rows
  }, [categorySortDirection, categorySortKey, spending?.categories])

  const sortedTransactions = useMemo(() => {
    const rows = [...visibleTransactions]
    rows.sort((left, right) => {
      let result = 0
      switch (transactionSortKey) {
        case 'date':
          result = compareText(left.date, right.date)
          break
        case 'merchant':
          result = compareText(left.merchant, right.merchant)
          break
        case 'account':
          result = compareText(left.accountLabel, right.accountLabel)
          break
        case 'category':
          result = compareText(left.category, right.category)
          break
        case 'type':
          result = compareText(left.essentiality, right.essentiality)
          break
        case 'amount':
          result = compareNumber(left.amount, right.amount)
          break
        case 'source':
          result = compareText(
            [left.sourceType, left.documentType].filter(Boolean).join(' · '),
            [right.sourceType, right.documentType].filter(Boolean).join(' · '),
          )
          break
      }
      if (result === 0) {
        result = compareText(left.date, right.date)
      }
      return transactionSortDirection === 'asc' ? result : -result
    })
    return rows
  }, [transactionSortDirection, transactionSortKey, visibleTransactions])

  const visibleTransactionTotal = useMemo(
    () => sortedTransactions.reduce((sum, row) => sum + (row.amount ?? 0), 0),
    [sortedTransactions],
  )

  const dailyAverage = useMemo(() => {
    const startDate = spending?.summary.startDate
    const endDate = spending?.summary.endDate
    const totalSpend = spending?.summary.totalSpend ?? 0
    if (!startDate || !endDate) {
      return totalSpend
    }
    const start = new Date(startDate)
    const end = new Date(endDate)
    const diff = Math.max(
      1,
      Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1,
    )
    return totalSpend / diff
  }, [
    spending?.summary.endDate,
    spending?.summary.startDate,
    spending?.summary.totalSpend,
  ])

  function toggleCategorySort(nextKey: CategorySortKey) {
    if (categorySortKey === nextKey) {
      setCategorySortDirection((current) =>
        current === 'asc' ? 'desc' : 'asc',
      )
      return
    }
    setCategorySortKey(nextKey)
    setCategorySortDirection(
      nextKey === 'category' || nextKey === 'type' ? 'asc' : 'desc',
    )
  }

  function toggleTransactionSort(nextKey: TransactionSortKey) {
    if (transactionSortKey === nextKey) {
      setTransactionSortDirection((current) =>
        current === 'asc' ? 'desc' : 'asc',
      )
      return
    }
    setTransactionSortKey(nextKey)
    setTransactionSortDirection(
      nextKey === 'date' || nextKey === 'amount' ? 'desc' : 'asc',
    )
  }

  function categoryHeader(
    label: string,
    key: CategorySortKey,
    align: 'left' | 'right' = 'left',
  ) {
    const active = categorySortKey === key
    return (
      <button
        type="button"
        onClick={() => toggleCategorySort(key)}
        className={cn(
          'flex w-full items-center gap-1 font-semibold uppercase tracking-[0.16em] text-text-muted/80 transition-colors hover:text-text',
          align === 'right' ? 'justify-end' : 'justify-start',
        )}
      >
        <span>{label}</span>
        {sortIcon(active, categorySortDirection)}
      </button>
    )
  }

  function transactionHeader(
    label: string,
    key: TransactionSortKey,
    align: 'left' | 'right' = 'left',
  ) {
    const active = transactionSortKey === key
    return (
      <button
        type="button"
        onClick={() => toggleTransactionSort(key)}
        className={cn(
          'flex w-full items-center gap-1 font-semibold uppercase tracking-[0.16em] text-text-muted/80 transition-colors hover:text-text',
          align === 'right' ? 'justify-end' : 'justify-start',
        )}
      >
        <span>{label}</span>
        {sortIcon(active, transactionSortDirection)}
      </button>
    )
  }

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load spending."
        detail="Retry to refresh the household spending ledger."
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
        title="Spending"
        description="Canonical bank and card transactions only. Same timeframe drives totals, categories, and row drill-down."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {spendingWindows.map((option) => (
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
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Window
            </p>
            <p className="mt-2 text-base font-semibold text-text">
              {spending?.summary.timeframeLabel ?? 'Past 30 days'}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {spending?.summary.startDate
                ? `${formatSpendingDate(spending.summary.startDate)} to ${formatSpendingDate(
                    spending.summary.endDate ?? spending.summary.startDate,
                  )}`
                : 'No current range'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Spend
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(spending?.summary.totalSpend, { decimals: 2 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {spending?.summary.transactionCount ?? 0} counted row
              {(spending?.summary.transactionCount ?? 0) === 1 ? '' : 's'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Avg / month
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(spending?.summary.averageMonthlySpend, {
                decimals: 2,
              })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {spending?.summary.accountCount ?? 0} account
              {(spending?.summary.accountCount ?? 0) === 1 ? '' : 's'}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Avg / day
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(dailyAverage, { decimals: 2 })}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Transfers, payroll, card payments, duplicate overlap, and raw
              import lines stay out.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Where Money Went"
        description={`Category totals for ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. Click row to drill into every matching transaction.`}
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[34vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
            <table className="min-w-[920px] w-full border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                <tr>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {categoryHeader('Category', 'category')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {categoryHeader('Type', 'type')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                    {categoryHeader('Total', 'total', 'right')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                    {categoryHeader('Avg / month', 'avg', 'right')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                    {categoryHeader('Share', 'share', 'right')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                    {categoryHeader('Tx', 'count', 'right')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {isLoading && !spending ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      Loading spending...
                    </td>
                  </tr>
                ) : sortedCategories.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      No spending categories in this timeframe.
                    </td>
                  </tr>
                ) : (
                  sortedCategories.map((category) => {
                    const isActive = selectedCategory === category.category
                    return (
                      <tr
                        key={`${category.category}-${category.essentiality}`}
                        className={cn(
                          'border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20',
                          isActive && 'bg-primary/10',
                        )}
                      >
                        <td className="border-b border-border/20 px-3 py-2.5">
                          <button
                            type="button"
                            onClick={() =>
                              setSelectedCategory((current) =>
                                current === category.category
                                  ? null
                                  : category.category,
                              )
                            }
                            className="font-medium text-text"
                          >
                            {category.category}
                          </button>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5">
                          <Badge
                            variant={
                              category.essentiality === 'essential'
                                ? 'success'
                                : category.essentiality === 'discretionary'
                                  ? 'warning'
                                  : 'outline'
                            }
                          >
                            {formatEnumLabel(category.essentiality)}
                          </Badge>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                          {formatCurrency(category.totalSpend, { decimals: 2 })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                          {formatCurrency(category.averageMonthlySpend, {
                            decimals: 2,
                          })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                          {formatPercent(category.shareOfSpend * 100, {
                            decimals: 0,
                          })}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                          {category.transactionCount}
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
        title={
          selectedCategory ? `${selectedCategory} transactions` : 'Transactions'
        }
        description={`Every matching transaction in ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. Filters live here, next to the table they affect.`}
        actions={
          <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
            <Select value={selectedAccount} onValueChange={setSelectedAccount}>
              <SelectTrigger
                className="w-[200px]"
                aria-label="Filter spending by account"
              >
                <SelectValue placeholder="All accounts" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All accounts</SelectItem>
                <SelectItem value="__unassigned__">Unassigned</SelectItem>
                {accountOptions.map((label) => (
                  <SelectItem key={label} value={label}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={selectedCategory ?? 'all'}
              onValueChange={(value) =>
                setSelectedCategory(value === 'all' ? null : value)
              }
            >
              <SelectTrigger
                className="w-[180px]"
                aria-label="Filter spending by category"
              >
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {(spending?.categories ?? []).map((entry) => (
                  <SelectItem key={entry.category} value={entry.category}>
                    {entry.category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search merchant, description, account, or source"
              aria-label="Search spending transactions"
              className="w-[300px]"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setSelectedCategory(null)
                setSelectedAccount('all')
                setSearch('')
              }}
            >
              Clear
            </Button>
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
          <span>
            {sortedTransactions.length} visible transaction
            {sortedTransactions.length === 1 ? '' : 's'}
          </span>
          {selectedCategory ? <span>· {selectedCategory}</span> : null}
          {selectedAccount !== 'all' ? (
            <span>
              ·{' '}
              {selectedAccount === '__unassigned__'
                ? 'Unassigned'
                : selectedAccount}
            </span>
          ) : null}
        </div>
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="max-h-[72vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
            <table className="min-w-[1360px] w-full border-separate border-spacing-0 text-sm">
              <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
                <tr>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {transactionHeader('Date', 'date')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {transactionHeader('Merchant', 'merchant')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                      Description
                    </span>
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {transactionHeader('Account', 'account')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {transactionHeader('Category', 'category')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {transactionHeader('Type', 'type')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                    {transactionHeader('Amount', 'amount', 'right')}
                  </th>
                  <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                    {transactionHeader('Source', 'source')}
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
                      Loading transactions...
                    </td>
                  </tr>
                ) : sortedTransactions.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-3 py-10 text-center text-sm text-text-muted"
                    >
                      No transactions match current filters.
                    </td>
                  </tr>
                ) : (
                  sortedTransactions.map((row) => (
                    <tr
                      key={`${row.date}-${row.sourceDocumentId ?? 'none'}-${row.merchant}-${row.amount}-${row.description}`}
                      className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                    >
                      <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                        {formatSpendingDate(row.date)}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                        {row.merchant}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                        {row.description}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-text">
                        {row.accountLabel ?? '—'}
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
                        {formatCurrency(row.amount, { decimals: 2 })}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                        {[row.sourceType, row.documentType]
                          .filter(Boolean)
                          .map((value) => formatEnumLabel(String(value)))
                          .join(' · ') || 'Ledger'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot className="sticky bottom-0 z-20 bg-bg/95 backdrop-blur">
                <tr>
                  <td className="border-t border-border/40 px-3 py-2 font-semibold text-text">
                    Total
                  </td>
                  <td className="border-t border-border/40 px-3 py-2 text-text-muted">
                    {sortedTransactions.length} row
                    {sortedTransactions.length === 1 ? '' : 's'}
                  </td>
                  <td className="border-t border-border/40 px-3 py-2 text-text-muted">
                    {selectedCategory
                      ? `${selectedCategory} drill-down`
                      : 'All visible spend'}
                  </td>
                  <td className="border-t border-border/40 px-3 py-2" />
                  <td className="border-t border-border/40 px-3 py-2" />
                  <td className="border-t border-border/40 px-3 py-2" />
                  <td className="border-t border-border/40 px-3 py-2 text-right font-mono tabular-nums text-text">
                    {formatCurrency(visibleTransactionTotal, { decimals: 2 })}
                  </td>
                  <td className="border-t border-border/40 px-3 py-2" />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
