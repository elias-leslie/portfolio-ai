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
  | 'debit'
  | 'credit'
  | 'balance'
  | 'source'

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
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function entryDate(entry: {
  postedDate?: string | null
  date?: string | null
  uploadedAt?: string | null
}) {
  return entry.postedDate ?? entry.date ?? entry.uploadedAt ?? null
}

function isCreditFlow(flowType?: string | null) {
  return ['income', 'refund', 'transfer_in'].includes(
    (flowType ?? '').trim().toLowerCase(),
  )
}

function isDebitFlow(flowType?: string | null) {
  return ['expense', 'payment', 'transfer_out', 'investment'].includes(
    (flowType ?? '').trim().toLowerCase(),
  )
}

function debitAmount(amount?: number | null, flowType?: string | null) {
  if (amount == null) {
    return null
  }
  if (isCreditFlow(flowType)) {
    return null
  }
  if (isDebitFlow(flowType) || amount > 0) {
    return Math.abs(amount)
  }
  return null
}

function creditAmount(amount?: number | null, flowType?: string | null) {
  if (amount == null) {
    return null
  }
  if (isCreditFlow(flowType)) {
    return Math.abs(amount)
  }
  if (!isDebitFlow(flowType) && amount < 0) {
    return Math.abs(amount)
  }
  return null
}

function shortHash(value: string) {
  return value.slice(0, 10)
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

export function MoneyLedgerPanel() {
  const [window, setWindow] = useState<LedgerWindow>('all')
  const [kind, setKind] = useState<LedgerKind>('transactions')
  const [status, setStatus] = useState<LedgerStatus>('canonical')
  const [account, setAccount] = useState<string>('all')
  const [query, setQuery] = useState('')
  const [sortKey, setSortKey] = useState<LedgerSortKey>('date')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const deferredQuery = useDeferredValue(query.trim().toLowerCase())
  const {
    data: ledger,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useHouseholdLedger({
    window,
    kind,
    limit: 50000,
  })

  const accountOptions = useMemo(() => {
    const labels = new Set<string>()
    for (const entry of ledger?.entries ?? []) {
      const label = entry.accountLabel?.trim()
      if (label) {
        labels.add(label)
      }
    }
    return Array.from(labels).sort((left, right) => left.localeCompare(right))
  }, [ledger?.entries])

  useEffect(() => {
    if (account === 'all' || account === '__unassigned__') {
      return
    }
    if (!accountOptions.includes(account)) {
      setAccount('all')
    }
  }, [account, accountOptions])

  const filteredEntries = useMemo(() => {
    const entries = ledger?.entries ?? []
    return entries.filter((entry) => {
      const isDuplicate = (entry.exclusionReason ?? '').startsWith('duplicate')
      if (status === 'canonical' && isDuplicate) {
        return false
      }
      if (status === 'duplicates' && !isDuplicate) {
        return false
      }
      if (
        account !== 'all' &&
        (entry.accountLabel?.trim() ?? '__unassigned__') !== account
      ) {
        return false
      }
      if (!deferredQuery) {
        return true
      }
      return [
        entry.accountLabel,
        entry.merchant,
        entry.description,
        entry.category,
        entry.essentiality,
        entry.sourceDocumentFilename,
        entry.sourceType,
        entry.documentType,
        entry.flowType,
        entry.exclusionReason,
        entry.rowHash,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(deferredQuery))
    })
  }, [account, deferredQuery, ledger?.entries, status])

  const visibleEntries = useMemo(() => {
    const entries = [...filteredEntries]
    entries.sort((left, right) => {
      let result = 0
      switch (sortKey) {
        case 'date':
          result = compareText(entryDate(left), entryDate(right))
          break
        case 'account':
          result = compareText(left.accountLabel, right.accountLabel)
          break
        case 'detail':
          result = compareText(
            left.merchant || left.description,
            right.merchant || right.description,
          )
          break
        case 'category':
          result = compareText(left.category, right.category)
          break
        case 'status':
          result = compareText(left.exclusionReason, right.exclusionReason)
          break
        case 'debit':
          result = compareNumber(
            debitAmount(left.amount, left.flowType),
            debitAmount(right.amount, right.flowType),
          )
          break
        case 'credit':
          result = compareNumber(
            creditAmount(left.amount, left.flowType),
            creditAmount(right.amount, right.flowType),
          )
          break
        case 'balance':
          result = compareNumber(left.balanceAfter, right.balanceAfter)
          break
        case 'source':
          result = compareText(
            left.sourceDocumentFilename,
            right.sourceDocumentFilename,
          )
          break
      }
      if (result === 0) {
        result = compareText(entryDate(left), entryDate(right))
      }
      return sortDirection === 'asc' ? result : -result
    })
    return entries
  }, [filteredEntries, sortDirection, sortKey])

  const includedCount = useMemo(
    () => visibleEntries.filter((entry) => entry.includedInSpend).length,
    [visibleEntries],
  )
  const excludedCount = visibleEntries.length - includedCount
  const visibleDebitTotal = useMemo(
    () =>
      visibleEntries.reduce(
        (sum, entry) => sum + (debitAmount(entry.amount, entry.flowType) ?? 0),
        0,
      ),
    [visibleEntries],
  )
  const visibleCreditTotal = useMemo(
    () =>
      visibleEntries.reduce(
        (sum, entry) => sum + (creditAmount(entry.amount, entry.flowType) ?? 0),
        0,
      ),
    [visibleEntries],
  )
  const visibleNetMovement = visibleDebitTotal - visibleCreditTotal

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
      description="Debit, credit, balance, source, and duplicate status from one accounting surface. Canonical view hides only proven duplicate overlap."
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
            placeholder="Search row, merchant, account, source, or hash"
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
            {visibleEntries.length}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {includedCount} counted · {excludedCount} excluded
          </p>
        </div>
      </div>

      <div className="mt-5 overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
        <div className="border-b border-border/40 px-4 py-3 text-xs text-text-muted">
          {ledger?.timeframeLabel ?? 'All dates'} · {visibleEntries.length}{' '}
          visible row
          {visibleEntries.length === 1 ? '' : 's'}
          {status === 'canonical'
            ? ' · proven duplicate overlap hidden'
            : ledger && visibleEntries.length !== ledger.totalEntryCount
              ? ` of ${ledger.totalEntryCount}`
              : ''}
        </div>
        <div className="max-h-[72vh] overflow-scroll [scrollbar-gutter:stable_both-edges]">
          <table className="min-w-[1500px] w-full border-separate border-spacing-0 text-sm">
            <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
              <tr className="border-b border-border/40">
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Date', 'date')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Account', 'account')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Detail', 'detail')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Category', 'category')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Status', 'status')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                  {headerButton('Debit', 'debit', 'right')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                  {headerButton('Credit', 'credit', 'right')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                  {headerButton('Balance', 'balance', 'right')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  {headerButton('Source', 'source')}
                </th>
                <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                    Hash
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading && !ledger ? (
                <tr>
                  <td
                    colSpan={10}
                    className="px-3 py-10 text-center text-sm text-text-muted"
                  >
                    Loading ledger...
                  </td>
                </tr>
              ) : visibleEntries.length === 0 ? (
                <tr>
                  <td
                    colSpan={10}
                    className="px-3 py-10 text-center text-sm text-text-muted"
                  >
                    No rows match current filters.
                  </td>
                </tr>
              ) : (
                visibleEntries.map((entry) => {
                  const effectiveDate = entryDate(entry)
                  const isFuture =
                    effectiveDate != null &&
                    new Date(effectiveDate).getTime() > Date.now()
                  return (
                    <tr
                      key={`${entry.kind}-${entry.id}`}
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
                              ? formatEnumLabel(entry.flowType ?? 'transaction')
                              : formatEnumLabel(
                                  entry.datasetType ?? 'import_row',
                                )}
                          </Badge>
                          {isFuture ? (
                            <Badge variant="destructive">Future</Badge>
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
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                        {formatCurrency(
                          debitAmount(entry.amount, entry.flowType),
                          {
                            decimals: 2,
                            nullDisplay: '—',
                          },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                        {formatCurrency(
                          creditAmount(entry.amount, entry.flowType),
                          {
                            decimals: 2,
                            nullDisplay: '—',
                          },
                        )}
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums">
                        <span
                          className={cn(
                            entry.balanceAfter == null
                              ? 'text-text-muted'
                              : 'text-text',
                          )}
                        >
                          {formatCurrency(entry.balanceAfter, {
                            decimals: 2,
                            nullDisplay: '—',
                          })}
                        </span>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 align-top">
                        <div className="font-medium text-text">
                          {entry.sourceDocumentFilename ?? 'Unknown source'}
                        </div>
                        <div className="text-xs text-text-muted">
                          {[
                            entry.sourceType
                              ? formatEnumLabel(entry.sourceType)
                              : null,
                            entry.documentType
                              ? formatEnumLabel(entry.documentType)
                              : null,
                          ]
                            .filter(Boolean)
                            .join(' · ') || 'Stored evidence'}
                        </div>
                      </td>
                      <td className="border-b border-border/20 px-3 py-2.5 font-mono text-xs text-text-muted">
                        {shortHash(entry.rowHash)}
                      </td>
                    </tr>
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
                  {visibleEntries.length} row
                  {visibleEntries.length === 1 ? '' : 's'}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-text-muted">
                  {status === 'canonical'
                    ? 'Canonical non-duplicate rows'
                    : 'Visible ledger rows'}
                </td>
                <td className="border-t border-border/40 px-3 py-2" />
                <td className="border-t border-border/40 px-3 py-2 text-text-muted">
                  {visibleNetMovement >= 0 ? 'Net debit' : 'Net credit'}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-right font-mono tabular-nums text-text">
                  {formatCurrency(visibleDebitTotal, { decimals: 2 })}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-right font-mono tabular-nums text-text">
                  {formatCurrency(visibleCreditTotal, { decimals: 2 })}
                </td>
                <td className="border-t border-border/40 px-3 py-2 text-right font-mono tabular-nums text-text">
                  {formatCurrency(Math.abs(visibleNetMovement), {
                    decimals: 2,
                  })}
                </td>
                <td className="border-t border-border/40 px-3 py-2" />
                <td className="border-t border-border/40 px-3 py-2" />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </SectionCard>
  )
}
