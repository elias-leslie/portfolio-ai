'use client'

import { X } from 'lucide-react'
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
import { useHouseholdLedger } from '@/lib/hooks/useHousehold'
import { LedgerSummaryCards } from './LedgerSummaryCards'
import { LedgerTable } from './LedgerTable'
import {
  LEDGER_PAGE_SIZE,
  type LedgerKind,
  type LedgerSortKey,
  type LedgerStatus,
  type LedgerWindow,
  ledgerKinds,
  ledgerStatuses,
  ledgerWindows,
} from './ledger-helpers'

export function MoneyLedgerPanel() {
  const [window, setWindow] = useState<LedgerWindow>('all')
  const [kind, setKind] = useState<LedgerKind>('transactions')
  const [status, setStatus] = useState<LedgerStatus>('canonical')
  const [account, setAccount] = useState<string>('all')
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<LedgerSortKey>('date')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [currentPage, setCurrentPage] = useState(1)
  const [expandedAuditRow, setExpandedAuditRow] = useState<string | null>(null)
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
  const accountOptions = ledger?.accountOptions ?? []

  useEffect(() => {
    if (account === 'all' || account === '__unassigned__') {
      return
    }
    if (ledger && !accountOptions.includes(account)) {
      setAccount('all')
    }
  }, [account, accountOptions, ledger])

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
    setCurrentPage(1)
    setExpandedAuditRow(null)
  }, [account, deferredQuery, kind, sortDirection, sortKey, status, window])

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages)
      setExpandedAuditRow(null)
    }
  }, [currentPage, totalPages])

  // Chips for every non-default filter so the active slice stays visible even
  // when the filter controls themselves are off-screen or collapsed.
  const activeFilters: Array<{
    key: string
    label: string
    onClear: () => void
  }> = []
  if (window !== 'all') {
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
    setWindow('all')
    setKind('transactions')
    setStatus('canonical')
    setAccount('all')
    setQuery('')
  }

  function toggleSort(nextKey: LedgerSortKey) {
    if (sortKey === nextKey) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
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
        <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {ledgerWindows.map((option) => (
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
            placeholder="Search merchant, account, category, or evidence"
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
        onPreviousPage={() => setCurrentPage((page) => Math.max(1, page - 1))}
        onNextPage={() =>
          setCurrentPage((page) => Math.min(totalPages, page + 1))
        }
      />
    </SectionCard>
  )
}
