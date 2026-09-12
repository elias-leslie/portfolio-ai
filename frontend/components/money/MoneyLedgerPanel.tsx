'use client'

import { X } from 'lucide-react'
import Link from 'next/link'
import { useDeferredValue, useEffect, useState } from 'react'
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
import { formatCurrency } from '@/lib/formatters'
import {
  useCategorizeHouseholdTransaction,
  useHouseholdLedger,
  useSetHouseholdTransactionSpendOverride,
} from '@/lib/hooks/useHousehold'
import { buildCategoryOptions } from './category-options'
import type { InlineComboboxCommitOptions } from './InlineComboboxField'
import { LedgerSummaryCards } from './LedgerSummaryCards'
import { LedgerTable } from './LedgerTable'
import {
  type HouseholdLedgerEntry,
  LEDGER_PAGE_SIZE,
  type LedgerKind,
  type LedgerSortKey,
  type LedgerStatus,
  type LedgerWindow,
  ledgerKinds,
  ledgerStatuses,
  ledgerWindows,
} from './ledger-helpers'
import { setMoneyQuery, useMoneyQuery } from './useMoneyQuery'

export function MoneyLedgerPanel() {
  const [window] = useMoneyQuery<LedgerWindow>('ledgerWindow', 'all', [
    'all',
    '1m',
    '3m',
    '6m',
    '12m',
  ])
  const [month, setMonth] = useMoneyQuery('month', '')
  const setWindow = (value: LedgerWindow) => {
    setMoneyQuery({ month: null, ledgerWindow: value, ledgerPage: null })
  }
  const [kind, setKind] = useMoneyQuery<LedgerKind>(
    'ledgerKind',
    'transactions',
    ['transactions', 'imports', 'all'],
  )
  const [status, setStatus] = useMoneyQuery<LedgerStatus>(
    'ledgerStatus',
    'canonical',
    ['canonical', 'duplicates', 'all'],
  )
  const [account, setAccount] = useMoneyQuery('ledgerAccount', 'all')
  const [category, setCategory] = useMoneyQuery('ledgerCategory', 'all')
  const [source, setSource] = useMoneyQuery('ledgerSource', 'all')
  const [inclusion, setInclusion] = useMoneyQuery('ledgerInclusion', 'all')
  const [query, setQuery] = useMoneyQuery('ledgerSearch', '')
  const [sortKey, setSortKey] = useMoneyQuery<LedgerSortKey>(
    'ledgerSort',
    'date',
    ['date', 'account', 'detail', 'category', 'status', 'amount'],
  )
  const [sortDirection, setSortDirection] = useMoneyQuery<'asc' | 'desc'>(
    'ledgerDirection',
    'desc',
    ['asc', 'desc'],
  )
  const [page, setPage] = useMoneyQuery('ledgerPage', '1')
  const currentPage = Math.max(1, Number.parseInt(page, 10) || 1)
  const setCurrentPage = (value: number) => setPage(String(value))
  const [expandedAuditRow, setExpandedAuditRow] = useState<string | null>(null)
  const categorizeTransaction = useCategorizeHouseholdTransaction()
  const spendOverride = useSetHouseholdTransactionSpendOverride()
  const deferredQuery = useDeferredValue(query.trim())
  const offset = (currentPage - 1) * LEDGER_PAGE_SIZE
  const {
    data: ledger,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdLedger({
    window,
    month: month || undefined,
    category,
    source,
    inclusion,
    kind,
    status,
    account,
    search: deferredQuery,
    sort: sortKey,
    sortDir: sortDirection,
    limit: LEDGER_PAGE_SIZE,
    offset,
  })

  // Server returns the full set of account labels for the window so the filter
  // dropdown stays complete even though only a page of rows is fetched.
  const accountOptions = Array.from(
    new Set([
      ...(ledger?.accountOptions ?? []),
      ...(account !== 'all' && account !== '__unassigned__' ? [account] : []),
    ]),
  )

  // Filtering, sorting and paging now happen server-side; the client only renders
  // the returned page and the server-computed summary counts.
  const pageEntries = ledger?.entries ?? []
  const filteredCount = ledger?.filteredCount ?? 0
  const includedCount = ledger?.includedCount ?? 0
  const excludedCount = ledger?.excludedCount ?? 0
  const visibleDebitTotal = ledger?.debitTotal ?? 0
  const visibleCreditTotal = ledger?.creditTotal ?? 0
  const visibleNetMovement = visibleDebitTotal - visibleCreditTotal
  const totalPages = Math.max(1, Math.ceil(filteredCount / LEDGER_PAGE_SIZE))
  const boundedPage = Math.min(currentPage, totalPages)
  const pageStart = filteredCount === 0 ? 0 : offset + 1
  const pageEnd = offset + pageEntries.length

  useEffect(() => {
    if (ledger && !isFetching && currentPage > totalPages) {
      setMoneyQuery({ ledgerPage: String(totalPages) }, true)
      setExpandedAuditRow(null)
    }
  }, [currentPage, totalPages, ledger, isFetching])

  // Chips for every non-default filter so the active slice stays visible even
  // when the filter controls themselves are off-screen or collapsed.
  const activeFilters: Array<{
    key: string
    label: string
    onClear: () => void
  }> = []
  for (const [key, value, clear] of [
    ['month', month, () => setMonth('')],
    ['category', category === 'all' ? '' : category, () => setCategory('all')],
    ['source', source === 'all' ? '' : source, () => setSource('all')],
    [
      'inclusion',
      inclusion === 'all' ? '' : inclusion,
      () => setInclusion('all'),
    ],
  ] as const) {
    if (value)
      activeFilters.push({ key, label: `${key}: ${value}`, onClear: clear })
  }
  if (window !== 'all' && !month) {
    activeFilters.push({
      key: 'window',
      label: ledgerWindows.find((o) => o.value === window)?.label ?? window,
      onClear: () => setWindow('all'),
    })
  }
  if (kind !== 'transactions') {
    activeFilters.push({
      key: 'type',
      label: ledgerKinds.find((o) => o.value === kind)?.label ?? kind,
      onClear: () => setKind('transactions'),
    })
  }
  if (status !== 'canonical') {
    activeFilters.push({
      key: 'status',
      label: ledgerStatuses.find((o) => o.value === status)?.label ?? status,
      onClear: () => setStatus('canonical'),
    })
  }
  if (account !== 'all') {
    activeFilters.push({
      key: 'account',
      label: account === '__unassigned__' ? 'Unassigned' : account,
      onClear: () => setAccount('all'),
    })
  }
  if (query.trim() !== '') {
    activeFilters.push({
      key: 'search',
      label: `"${query.trim()}"`,
      onClear: () => setQuery(''),
    })
  }

  function clearAllFilters() {
    setMoneyQuery(
      Object.fromEntries(
        [
          'month',
          'ledgerWindow',
          'ledgerKind',
          'ledgerStatus',
          'ledgerAccount',
          'ledgerCategory',
          'ledgerSource',
          'ledgerInclusion',
          'ledgerSearch',
          'ledgerPage',
        ].map((key) => [key, null]),
      ),
    )
  }

  // The server returns category options across the whole window (only a page of
  // rows is fetched); the standard taxonomy fills in categories not yet in use.
  const categoryOptions = buildCategoryOptions(ledger?.categoryOptions ?? [])

  async function saveCategory(
    entry: HouseholdLedgerEntry,
    category: string,
    options?: InlineComboboxCommitOptions,
  ) {
    const trimmed = category.trim()
    if (!trimmed) {
      return
    }
    await categorizeTransaction.mutateAsync({
      transactionId: entry.id,
      category: trimmed,
      essentiality: entry.essentiality || 'mixed',
      applyToMerchant: options?.applyRule === true,
    })
  }

  function toggleSort(nextKey: LedgerSortKey) {
    if (sortKey === nextKey) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
      return
    }
    setSortKey(nextKey)
    setSortDirection(nextKey === 'date' ? 'desc' : 'asc')
  }

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load the ledger."
        detail="Retry to refresh the raw household ledger."
        onRetry={() => {
          void refetch()
        }}
        isRetrying={isFetching}
      />
    )
  }

  return (
    <SectionCard
      variant="surface"
      title="General Ledger"
      description="Paged household transactions with evidence and duplicate status. Source files and debug identifiers stay behind row audit details."
      actions={
        <details className="w-full md:w-auto">
          <summary className="cursor-pointer rounded-xl border border-border/35 px-3 py-2 text-sm">
            Filters and dates
          </summary>
          <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
            <div className="flex flex-wrap items-center gap-2">
              {ledgerWindows.map((option) => (
                <Button
                  key={option.value}
                  type="button"
                  size="sm"
                  variant={
                    !month && window === option.value ? 'default' : 'outline'
                  }
                  onClick={() => setWindow(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <Input
              type="month"
              value={month}
              onChange={(event) => {
                setMoneyQuery({ month: event.target.value, ledgerPage: null })
              }}
              aria-label="Ledger calendar month"
              className="w-44"
            />
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger
                className="w-44"
                aria-label="Filter ledger category"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {categoryOptions.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={source} onValueChange={setSource}>
              <SelectTrigger className="w-40" aria-label="Filter ledger source">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All sources</SelectItem>
                {(ledger?.sourceOptions ?? []).map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={inclusion} onValueChange={setInclusion}>
              <SelectTrigger
                className="w-44"
                aria-label="Filter spend inclusion"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Included + excluded</SelectItem>
                <SelectItem value="included">Included in spending</SelectItem>
                <SelectItem value="excluded">Excluded from spending</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={kind}
              onValueChange={(value) => setKind(value as LedgerKind)}
            >
              <SelectTrigger
                className="w-[160px]"
                aria-label="Filter ledger row type"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ledgerKinds.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={status}
              onValueChange={(value) => setStatus(value as LedgerStatus)}
            >
              <SelectTrigger
                className="w-[170px]"
                aria-label="Filter ledger row set"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ledgerStatuses.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={account} onValueChange={setAccount}>
              <SelectTrigger
                className="w-[200px]"
                aria-label="Filter ledger by account"
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
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search merchant, amount, account, category, or evidence"
              aria-label="Search ledger rows"
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
        </details>
      }
    >
      {activeFilters.length > 0 ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {activeFilters.map((filter) => (
            <Badge
              key={filter.key}
              variant="secondary"
              className="gap-1 pr-1.5"
            >
              {filter.label}
              <button
                type="button"
                aria-label={`Clear ${filter.key} filter`}
                className="rounded-sm p-0.5 text-text-muted transition-colors hover:text-text"
                onClick={filter.onClear}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={clearAllFilters}
          >
            Clear all
          </Button>
        </div>
      ) : null}

      {month ? (
        <div className="mb-4 space-y-1 rounded-xl border border-border/35 p-3">
          <Link
            href={`/money?tab=spending&month=${encodeURIComponent(month)}`}
            className="text-sm text-primary underline"
          >
            Return to this month's review
          </Link>
          <p className="font-medium">
            {isFetching
              ? 'Updating…'
              : ledger?.reviewSpendTotal != null
                ? `${formatCurrency(ledger.reviewSpendTotal, { decimals: 2 })} included spending${ledger.reviewCategory ? ` · ${ledger.reviewCategory}` : ''}`
                : 'Loading review totals…'}
          </p>
          <p className="text-xs text-text-muted">
            Transaction dates match Review. Refunds reduce spending; itemized
            purchases contribute only the selected category. Totals cover all
            filtered rows, across pages.
          </p>
        </div>
      ) : null}
      {ledger?.scanTruncated ? (
        <p role="alert" className="mb-3 text-warning">
          This date range exceeds the ledger limit. Choose a shorter period
          before reconciling totals.
        </p>
      ) : null}
      {isLoading ? (
        <p role="status">Loading ledger totals…</p>
      ) : (
        <LedgerSummaryCards
          timeframeLabel={ledger?.timeframeLabel}
          startDate={ledger?.startDate}
          endDate={ledger?.endDate}
          visibleDebitTotal={visibleDebitTotal}
          visibleCreditTotal={visibleCreditTotal}
          visibleNetMovement={visibleNetMovement}
          filteredCount={filteredCount}
          includedCount={includedCount}
          excludedCount={excludedCount}
        />
      )}

      <LedgerTable
        timeframeLabel={ledger?.timeframeLabel}
        pageEntries={pageEntries}
        filteredCount={filteredCount}
        totalEntryCount={ledger?.totalEntryCount}
        visibleDebitTotal={visibleDebitTotal}
        visibleCreditTotal={visibleCreditTotal}
        visibleNetMovement={visibleNetMovement}
        status={status}
        sortKey={sortKey}
        sortDirection={sortDirection}
        onToggleSort={toggleSort}
        isLoading={isLoading}
        hasLedger={Boolean(ledger)}
        pageStart={pageStart}
        pageEnd={pageEnd}
        boundedPage={boundedPage}
        totalPages={totalPages}
        expandedAuditRow={expandedAuditRow}
        onToggleAudit={setExpandedAuditRow}
        categoryOptions={categoryOptions}
        categorizePending={categorizeTransaction.isPending}
        onCommitCategory={(entry, category, options) =>
          void saveCategory(entry, category, options)
        }
        spendOverridePending={spendOverride.isPending}
        onSetSpendOverride={(entry, countsAsSpend) =>
          void spendOverride.mutateAsync({
            transactionId: entry.id,
            countsAsSpend,
          })
        }
        onPreviousPage={() => setCurrentPage(Math.max(1, currentPage - 1))}
        onNextPage={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
      />
    </SectionCard>
  )
}
