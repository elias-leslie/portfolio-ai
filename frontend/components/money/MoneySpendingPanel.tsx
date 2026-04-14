'use client'

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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useHouseholdSpending } from '@/lib/hooks/useHousehold'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

type SpendingWindow = '1m' | '3m' | '6m' | '12m' | 'all'

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

export function MoneySpendingPanel() {
  const [window, setWindow] = useState<SpendingWindow>('1m')
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [selectedAccount, setSelectedAccount] = useState<string>('all')
  const [search, setSearch] = useState('')
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
    if (!spending?.categories.some((entry) => entry.category === selectedCategory)) {
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
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(deferredSearch))
    })
  }, [deferredSearch, selectedAccount, selectedCategory, spending?.transactions])

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
  }, [spending?.summary.endDate, spending?.summary.startDate, spending?.summary.totalSpend])

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
        description="Canonical bank and card transactions only. Same timeframe drives totals, categories, and rows."
        actions={
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
        }
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="space-y-4">
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
            </div>
            <p className="text-sm text-text-muted">
              {spending?.summary.timeframeLabel ?? 'Past 30 days'}
              {spending?.summary.startDate
                ? ` · ${formatSpendingDate(spending.summary.startDate)} to ${formatSpendingDate(
                    spending.summary.endDate ?? spending.summary.startDate,
                  )}`
                : ''}
            </p>
            <p className="text-xs text-text-muted">
              Canonical expense rows only. Transfers, payroll, card payments,
              duplicate overlaps, and raw import lines stay out of spend totals.
              Returns and refunds net against spend automatically.
            </p>
          </div>
          <div className="space-y-2">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search merchant, account, description, or category"
              aria-label="Search spending transactions"
            />
            <Select value={selectedAccount} onValueChange={setSelectedAccount}>
              <SelectTrigger aria-label="Filter spending by account">
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
              <SelectTrigger aria-label="Filter spending by category">
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
            <p className="text-xs text-text-muted">
              {visibleTransactions.length} visible transaction
              {visibleTransactions.length === 1 ? '' : 's'}
              {selectedCategory ? ` · ${selectedCategory}` : ''}
              {selectedAccount !== 'all'
                ? ` · ${selectedAccount === '__unassigned__' ? 'Unassigned' : selectedAccount}`
                : ''}
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Spend in period
            </p>
            <p className="mt-2 text-base font-semibold tabular-nums text-text">
              {formatCurrency(spending?.summary.totalSpend, { decimals: 2 })}
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
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Avg / day
            </p>
            <p className="mt-2 text-base font-semibold text-text">
              {formatCurrency(dailyAverage, { decimals: 2 })}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
              Counted rows
            </p>
            <p className="mt-2 text-base font-semibold text-text">
              {spending?.summary.transactionCount ?? 0}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {spending?.summary.accountCount ?? 0} account
              {(spending?.summary.accountCount ?? 0) === 1 ? '' : 's'}
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Where Money Went"
        description={`Category totals for ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. Click a row or use the filter to drill into every matching transaction.`}
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="overflow-x-auto">
            <Table className="min-w-[920px]">
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="text-right">Avg / month</TableHead>
                <TableHead className="text-right">Share</TableHead>
                <TableHead className="text-right">Tx</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && !spending ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-sm text-text-muted">
                    Loading spending...
                  </TableCell>
                </TableRow>
              ) : (spending?.categories ?? []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="py-10 text-center text-sm text-text-muted">
                    No spending categories in this timeframe.
                  </TableCell>
                </TableRow>
              ) : (
                spending?.categories.map((category) => {
                  const isActive = selectedCategory === category.category
                  return (
                    <TableRow
                      key={`${category.category}-${category.essentiality}`}
                      className={isActive ? 'bg-primary/10' : undefined}
                    >
                      <TableCell>
                        <button
                          type="button"
                          onClick={() =>
                            setSelectedCategory((current) =>
                              current === category.category ? null : category.category,
                            )
                          }
                          className="text-left font-medium text-text"
                        >
                          {category.category}
                        </button>
                      </TableCell>
                      <TableCell>
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
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {formatCurrency(category.totalSpend, { decimals: 2 })}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {formatCurrency(category.averageMonthlySpend, {
                          decimals: 2,
                        })}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {formatPercent(category.shareOfSpend * 100, {
                          decimals: 0,
                        })}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {category.transactionCount}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
            </Table>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title={selectedCategory ? `${selectedCategory} transactions` : 'Transactions'}
        description={`Every matching transaction in ${spending?.summary.timeframeLabel ?? 'the selected timeframe'}. No hidden recent slice.`}
        actions={
          selectedCategory || selectedAccount !== 'all' || search.trim() ? (
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
              Clear filters
            </Button>
          ) : undefined
        }
      >
        <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
          <div className="overflow-x-auto">
            <Table className="min-w-[1280px]">
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Merchant</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Account</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Amount</TableHead>
                <TableHead>Source</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && !spending ? (
                <TableRow>
                  <TableCell colSpan={8} className="py-10 text-center text-sm text-text-muted">
                    Loading transactions...
                  </TableCell>
                </TableRow>
              ) : visibleTransactions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="py-10 text-center text-sm text-text-muted">
                    No transactions match current filters.
                  </TableCell>
                </TableRow>
              ) : (
                visibleTransactions.map((row) => (
                  <TableRow
                    key={`${row.date}-${row.sourceDocumentId ?? 'none'}-${row.merchant}-${row.amount}-${row.description}`}
                  >
                    <TableCell className="align-top font-medium text-text">
                      {formatSpendingDate(row.date)}
                    </TableCell>
                    <TableCell className="max-w-[260px] align-top">
                      <div className="line-clamp-2 whitespace-normal font-medium text-text">
                        {row.merchant}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[460px] align-top text-xs text-text-muted">
                      <div className="line-clamp-2 whitespace-normal">
                        {row.description}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[240px] align-top">
                      <div className="line-clamp-2 whitespace-normal text-text">
                        {row.accountLabel ?? '—'}
                      </div>
                    </TableCell>
                    <TableCell className="align-top">
                      <div className="truncate text-text">
                        {row.category}
                      </div>
                    </TableCell>
                    <TableCell className="align-top">
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
                    </TableCell>
                    <TableCell className="text-right align-top font-mono tabular-nums text-text">
                      {formatCurrency(row.amount, { decimals: 2 })}
                    </TableCell>
                    <TableCell className="align-top text-xs text-text-muted">
                      {[row.sourceType, row.documentType]
                        .filter(Boolean)
                        .map((value) => formatEnumLabel(String(value)))
                        .join(' · ') || 'Ledger'}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
            </Table>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
