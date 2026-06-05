'use client'

import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { Fragment, useDeferredValue, useEffect, useState } from 'react'
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
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { useHouseholdLedger } from '@/lib/hooks/useHousehold'
import { cn } from '@/lib/utils'

type LedgerWindow = 'all' | '1m' | '3m' | '6m' | '12m'
type LedgerKind = 'all' | 'transactions' | 'imports'
type LedgerStatus = 'canonical' | 'all' | 'duplicates'
type LedgerSortKey =
  | 'date'
  | 'account'
  | 'detail'
  | 'category'
  | 'status'
  | 'amount'

const LEDGER_PAGE_SIZE = 50

const ledgerWindows: Array<{ value: LedgerWindow; label: string }> = [
  { value: 'all', label: 'All' },
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
]

const ledgerKinds: Array<{ value: LedgerKind; label: string }> = [
  { value: 'transactions', label: 'Transactions' },
  { value: 'imports', label: 'Import rows' },
  { value: 'all', label: 'All rows' },
]

const ledgerStatuses: Array<{ value: LedgerStatus; label: string }> = [
  { value: 'canonical', label: 'Counted view' },
  { value: 'all', label: 'All source rows' },
  { value: 'duplicates', label: 'Duplicates only' },
]

function formatLedgerDate(value?: string | null) {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  // Ledger dates are stored at UTC midnight; format in UTC so a 00:00Z date does
  // not render as the previous calendar day in US (negative-offset) timezones.
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date)
}

function utcDateKey(value?: string | null): string | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date.toISOString().slice(0, 10)
}

function entryDate(entry: {
  postedDate?: string | null
  date?: string | null
  uploadedAt?: string | null
}) {
  return entry.postedDate ?? entry.date ?? entry.uploadedAt ?? null
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

function ledgerRowKey(entry: { kind: string; id: string }) {
  return `${entry.kind}-${entry.id}`
}

function ledgerAmountLabel(entry: {
  amount?: number | null
  direction: string
}) {
  if (entry.amount == null) {
    return formatCurrency(entry.amount, { decimals: 2 })
  }
  if (entry.direction === 'debit') {
    return `-${formatCurrency(Math.abs(entry.amount), { decimals: 2 })}`
  }
  if (entry.direction === 'credit') {
    return `+${formatCurrency(Math.abs(entry.amount), { decimals: 2 })}`
  }
  return formatCurrency(entry.amount, { decimals: 2 })
}

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

  function toggleSort(nextKey: LedgerSortKey) {
    if (sortKey === nextKey) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(nextKey)
    setSortDirection(nextKey === 'date' ? 'desc' : 'asc')
  }

  function headerButton(
    label: string,
    key: LedgerSortKey,
    align: 'left' | 'right' = 'left',
  ) {
    const active = sortKey === key
    return (
      <button
        type="button"
        onClick={() => toggleSort(key)}
        className={cn(
          'flex w-full items-center gap-1 font-semibold uppercase tracking-[0.16em] text-text-muted/80 transition-colors hover:text-text',
          align === 'right' ? 'justify-end' : 'justify-start',
        )}
      >
        <span>{label}</span>
        {sortIcon(active, sortDirection)}
      </button>
    )
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
      <div className="grid gap-3 xl:grid-cols-5">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Window
          </p>
          <p className="mt-2 text-base font-semibold text-text">
            {ledger?.timeframeLabel ?? 'Loading'}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {ledger?.startDate
              ? `${formatLedgerDate(ledger.startDate)} to ${formatLedgerDate(ledger.endDate)}`
              : 'Full ledger history'}
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Debits
          </p>
          <p className="mt-2 text-base font-semibold tabular-nums text-text">
            {formatCurrency(visibleDebitTotal, { decimals: 2 })}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Visible debits in current view
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Credits
          </p>
          <p className="mt-2 text-base font-semibold tabular-nums text-text">
            {formatCurrency(visibleCreditTotal, { decimals: 2 })}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Visible credits in current view
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Net
          </p>
          <p className="mt-2 text-base font-semibold tabular-nums text-text">
            {formatCurrency(Math.abs(visibleNetMovement), { decimals: 2 })}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {visibleNetMovement >= 0 ? 'Net debit' : 'Net credit'}
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Rows
          </p>
          <p className="mt-2 text-base font-semibold text-text">
            {filteredCount}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {includedCount} counted · {excludedCount} excluded
          </p>
        </div>
      </div>

      <div className="mt-5 overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
        <div className="flex flex-col gap-2 border-b border-border/40 px-4 py-3 text-xs text-text-muted md:flex-row md:items-center md:justify-between">
          <span>
            {ledger?.timeframeLabel ?? 'All dates'} · {filteredCount} matching
            row
            {filteredCount === 1 ? '' : 's'}
            {status === 'canonical'
              ? ' · proven duplicate overlap hidden'
              : ledger && filteredCount !== ledger.totalEntryCount
                ? ` of ${ledger.totalEntryCount}`
                : ''}
          </span>
          <span>
            Showing {pageStart}-{pageEnd} of {filteredCount}
          </span>
        </div>
        <div className="max-h-[72vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
          <table className="min-w-[1120px] w-full border-separate border-spacing-0 text-sm">
            <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
              <tr className="border-b border-border/40">
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Date', 'date')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Account', 'account')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Merchant', 'detail')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Category', 'category')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                  {headerButton('Amount', 'amount', 'right')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Status', 'status')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Evidence
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading && !ledger ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-10 text-center text-sm text-text-muted"
                  >
                    Loading ledger...
                  </td>
                </tr>
              ) : pageEntries.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-10 text-center text-sm text-text-muted"
                  >
                    No rows match current filters.
                  </td>
                </tr>
              ) : (
                pageEntries.map((entry) => {
                  const effectiveDate = entryDate(entry)
                  const effectiveDateKey = utcDateKey(effectiveDate)
                  const isFuture =
                    effectiveDateKey != null &&
                    effectiveDateKey > new Date().toISOString().slice(0, 10)
                  const rowKey = ledgerRowKey(entry)
                  const auditOpen = expandedAuditRow === rowKey
                  const evidenceLabel = entry.sourceDocumentId
                    ? 'Evidence linked'
                    : 'No evidence'
                  const evidenceDetail =
                    [
                      entry.sourceType
                        ? formatEnumLabel(entry.sourceType)
                        : null,
                      entry.documentType
                        ? formatEnumLabel(entry.documentType)
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ') || 'Stored row'
                  const isCredit = entry.direction === 'credit'
                  return (
                    <Fragment key={rowKey}>
                      <tr
                        data-ledger-row="entry"
                        className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                      >
                        <td className="border-b border-border/20 px-3 py-2.5 align-top">
                          <div className="font-medium text-text">
                            {formatLedgerDate(effectiveDate)}
                          </div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            <Badge
                              variant={
                                entry.kind === 'transaction'
                                  ? 'default'
                                  : 'outline'
                              }
                              className="w-fit"
                            >
                              {entry.kind === 'transaction'
                                ? formatEnumLabel(
                                    entry.flowType ?? 'transaction',
                                  )
                                : formatEnumLabel(
                                    entry.datasetType ?? 'import_row',
                                  )}
                            </Badge>
                            {isFuture ? (
                              <Badge variant="destructive">Future</Badge>
                            ) : null}
                            {entry.pending ? (
                              <Badge variant="warning">Pending</Badge>
                            ) : null}
                          </div>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 align-top">
                          <div className="font-medium text-text">
                            {entry.accountLabel ?? '—'}
                          </div>
                          <div className="text-xs text-text-muted">
                            {entry.currency ?? 'USD'}
                          </div>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 align-top">
                          <div className="font-medium text-text">
                            {entry.merchant || entry.description}
                          </div>
                          {entry.description &&
                          entry.description !== entry.merchant ? (
                            <div className="text-xs text-text-muted">
                              {entry.description}
                            </div>
                          ) : null}
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 align-top">
                          <div className="font-medium text-text">
                            {entry.category
                              ? formatEnumLabel(entry.category)
                              : '—'}
                          </div>
                          <div className="text-xs text-text-muted">
                            {entry.essentiality
                              ? formatEnumLabel(entry.essentiality)
                              : '—'}
                          </div>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 text-right align-top">
                          <div
                            className={cn(
                              'font-mono font-medium tabular-nums',
                              isCredit ? 'text-gain' : 'text-text',
                            )}
                          >
                            {ledgerAmountLabel(entry)}
                          </div>
                          <div className="mt-1 text-xs text-text-muted">
                            {isCredit ? 'Credit' : 'Debit'}
                          </div>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 align-top">
                          <div className="flex flex-wrap gap-1">
                            <Badge
                              variant={
                                entry.includedInSpend ? 'default' : 'outline'
                              }
                              className="w-fit"
                            >
                              {entry.includedInSpend ? 'Counted' : 'Excluded'}
                            </Badge>
                          </div>
                          <div className="mt-1 text-xs text-text-muted">
                            {entry.exclusionReason
                              ? formatEnumLabel(entry.exclusionReason)
                              : 'Included in canonical spend'}
                          </div>
                        </td>
                        <td className="border-b border-border/20 px-3 py-2.5 align-top">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant={
                                entry.sourceDocumentId ? 'outline' : 'secondary'
                              }
                            >
                              {evidenceLabel}
                            </Badge>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-xs"
                              aria-expanded={auditOpen}
                              aria-controls={`ledger-audit-${rowKey}`}
                              onClick={() =>
                                setExpandedAuditRow(auditOpen ? null : rowKey)
                              }
                            >
                              Audit
                            </Button>
                          </div>
                          <div className="mt-1 text-xs text-text-muted">
                            {evidenceDetail}
                          </div>
                        </td>
                      </tr>
                      {auditOpen ? (
                        <tr
                          id={`ledger-audit-${rowKey}`}
                          data-ledger-row="audit"
                          className="bg-surface-muted/10"
                        >
                          <td
                            colSpan={7}
                            className="border-b border-border/20 px-3 py-3"
                          >
                            <div className="rounded-xl border border-border/35 bg-surface/70 p-4">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-semibold text-text">
                                    Audit detail
                                  </p>
                                  <p className="mt-1 text-xs text-text-muted">
                                    Provenance and debug identifiers for this
                                    ledger row.
                                  </p>
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setExpandedAuditRow(null)}
                                >
                                  Hide audit
                                </Button>
                              </div>
                              <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Source file
                                  </dt>
                                  <dd className="mt-1 break-all text-text">
                                    {entry.sourceDocumentFilename ??
                                      'Unknown source'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Source type
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {evidenceDetail}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Document id
                                  </dt>
                                  <dd className="mt-1 break-all text-text">
                                    {entry.sourceDocumentId ?? '—'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Row hash
                                  </dt>
                                  <dd className="mt-1 break-all font-mono text-text">
                                    {entry.rowHash}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    External row id
                                  </dt>
                                  <dd className="mt-1 break-all text-text">
                                    {entry.externalRowId ?? '—'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Balance after
                                  </dt>
                                  <dd className="mt-1 font-mono tabular-nums text-text">
                                    {formatCurrency(entry.balanceAfter, {
                                      decimals: 2,
                                      nullDisplay: '—',
                                    })}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Uploaded
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {formatLedgerDate(entry.uploadedAt)}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Exclusion reason
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {entry.exclusionReason
                                      ? formatEnumLabel(entry.exclusionReason)
                                      : 'Included in canonical spend'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Settlement
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {entry.pending ? 'Pending' : 'Posted'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Categorized by
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {entry.categorizationSource
                                      ? formatEnumLabel(
                                          entry.categorizationSource,
                                        )
                                      : '—'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Original category
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {entry.originalCategory
                                      ? formatEnumLabel(entry.originalCategory)
                                      : '—'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="font-semibold uppercase tracking-[0.14em] text-text-muted">
                                    Recategorized
                                  </dt>
                                  <dd className="mt-1 text-text">
                                    {entry.categoryUpdatedBy
                                      ? `${entry.categoryUpdatedBy}${
                                          entry.categoryUpdatedAt
                                            ? ` · ${formatLedgerDate(entry.categoryUpdatedAt)}`
                                            : ''
                                        }`
                                      : '—'}
                                  </dd>
                                </div>
                              </dl>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  )
                })
              )}
            </tbody>
            <tfoot className="sticky bottom-0 z-20 bg-bg/95 backdrop-blur">
              <tr>
                <td className="border-t border-border/40 px-3 py-2 font-semibold text-text">
                  Total
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-text-muted">
                  {filteredCount} row
                  {filteredCount === 1 ? '' : 's'}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-text-muted">
                  {status === 'canonical'
                    ? 'Canonical non-duplicate rows'
                    : 'Visible ledger rows'}
                </td>
                <td className="border-t border-border/40 px-3 py-2" />
                <td className="border-t border-border/40 px-3 py-2 text-right text-text-muted">
                  {visibleNetMovement >= 0 ? 'Net debit' : 'Net credit'}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-right font-mono tabular-nums text-text">
                  {formatCurrency(Math.abs(visibleNetMovement), {
                    decimals: 2,
                  })}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-xs text-text-muted">
                  Debits {formatCurrency(visibleDebitTotal, { decimals: 2 })} ·
                  Credits {formatCurrency(visibleCreditTotal, { decimals: 2 })}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t border-border/40 px-4 py-3 text-xs text-text-muted md:flex-row md:items-center md:justify-between">
          <span>
            Page {boundedPage} of {totalPages} · {LEDGER_PAGE_SIZE} rows max per
            page
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={boundedPage <= 1}
              onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={boundedPage >= totalPages}
              onClick={() =>
                setCurrentPage((page) => Math.min(totalPages, page + 1))
              }
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
