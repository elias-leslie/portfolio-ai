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
import { useHouseholdLedger } from '@/lib/hooks/useHousehold'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'

type LedgerWindow = 'all' | '1m' | '3m' | '6m' | '12m'
type LedgerKind = 'all' | 'transactions' | 'imports'

const ledgerWindows: Array<{ value: LedgerWindow; label: string }> = [
  { value: 'all', label: 'All' },
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
]

const ledgerKinds: Array<{ value: LedgerKind; label: string }> = [
  { value: 'all', label: 'All rows' },
  { value: 'transactions', label: 'Transactions' },
  { value: 'imports', label: 'Import rows' },
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

function debitAmount(amount?: number | null) {
  return amount != null && amount > 0 ? amount : null
}

function creditAmount(amount?: number | null) {
  return amount != null && amount < 0 ? Math.abs(amount) : null
}

function shortHash(value: string) {
  return value.slice(0, 10)
}

export function MoneyLedgerPanel() {
  const [window, setWindow] = useState<LedgerWindow>('all')
  const [kind, setKind] = useState<LedgerKind>('transactions')
  const [account, setAccount] = useState<string>('all')
  const [query, setQuery] = useState('')
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
    limit: 10000,
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

  const visibleEntries = useMemo(() => {
    const entries = ledger?.entries ?? []
    return entries.filter((entry) => {
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
        entry.rowHash,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(deferredQuery))
    })
  }, [account, deferredQuery, ledger?.entries])

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
      description="Canonical transaction ledger first. Supporting import rows separate. Full-width audit table with exact provenance."
      actions={
        <div className="flex flex-wrap items-center gap-2">
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
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
          <div className="space-y-4">
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
            <div className="flex flex-wrap items-center gap-2">
              {ledgerKinds.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={kind === option.value ? 'default' : 'outline'}
                onClick={() => setKind(option.value)}
              >
                {option.label}
                </Button>
              ))}
            </div>
            <p className="text-xs text-text-muted">
              Transactions drive accounting totals. Import rows stay available for audit and source tracing.
            </p>
          </div>
          <div className="space-y-2">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search merchant, account, category, source, or hash"
              aria-label="Search ledger rows"
            />
            <Select value={account} onValueChange={setAccount}>
              <SelectTrigger aria-label="Filter ledger by account">
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
            <p className="text-xs text-text-muted">
              {ledger?.timeframeLabel ?? 'All dates'} · {visibleEntries.length}{' '}
            visible row{visibleEntries.length === 1 ? '' : 's'}
            {ledger && visibleEntries.length !== ledger.totalEntryCount
              ? ` of ${ledger.totalEntryCount}`
              : ''}
          </p>
        </div>
      </div>

        <div className="mt-5 grid gap-3 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Timeframe
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
            {formatCurrency(ledger?.debitTotal, { decimals: 2 })}
          </p>
            <p className="mt-1 text-xs text-text-muted">
              Outflows in current ledger filter
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/15 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Credits
          </p>
          <p className="mt-2 text-base font-semibold tabular-nums text-text">
            {formatCurrency(ledger?.creditTotal, { decimals: 2 })}
          </p>
            <p className="mt-1 text-xs text-text-muted">
              Inflows and credits in current ledger filter
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
              {ledger?.totalEntryCount ?? 0} total · {ledger?.transactionCount ?? 0} tx · {ledger?.importRowCount ?? 0} import
            </p>
          </div>
        </div>

      <div className="mt-5 overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
        <div className="overflow-x-auto">
          <Table className="min-w-[1220px]">
          <TableHeader>
            <TableRow>
              <TableHead className="sticky top-0 z-10 bg-bg/95">Date</TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95">
                Account
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95">
                Detail
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95">
                Category
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95 text-right">
                Debit
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95 text-right">
                Credit
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95 text-right">
                Balance
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95">
                Source
              </TableHead>
              <TableHead className="sticky top-0 z-10 bg-bg/95">
                Hash
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && !ledger ? (
              <TableRow>
                <TableCell colSpan={9} className="py-10 text-center text-sm text-text-muted">
                  Loading ledger...
                </TableCell>
              </TableRow>
            ) : visibleEntries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="py-10 text-center text-sm text-text-muted">
                  No rows match current filters.
                </TableCell>
              </TableRow>
            ) : (
              visibleEntries.map((entry) => {
                const effectiveDate = entryDate(entry)
                const isFuture =
                  effectiveDate != null &&
                  new Date(effectiveDate).getTime() > Date.now()
                return (
                  <TableRow key={`${entry.kind}-${entry.id}`}>
                    <TableCell className="align-top whitespace-nowrap">
                      <div className="font-medium text-text">
                        {formatLedgerDate(effectiveDate)}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                          <Badge
                            variant={
                              entry.kind === 'transaction' ? 'default' : 'outline'
                            }
                            className="w-fit"
                          >
                            {entry.kind === 'transaction'
                              ? formatEnumLabel(entry.flowType ?? 'transaction')
                              : formatEnumLabel(entry.datasetType ?? 'import_row')}
                          </Badge>
                          {isFuture ? (
                            <Badge variant="destructive">Future</Badge>
                          ) : null}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[220px] align-top">
                      <div className="truncate font-medium text-text">
                        {entry.accountLabel ?? '—'}
                      </div>
                      <div className="truncate text-xs text-text-muted">
                        {entry.currency ?? 'USD'}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[420px] align-top">
                      <div className="truncate font-medium text-text">
                        {entry.merchant || entry.description}
                      </div>
                      <div className="truncate text-xs text-text-muted">
                        {entry.description}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-[200px] align-top">
                      <div className="truncate font-medium text-text">
                        {entry.category ? formatEnumLabel(entry.category) : '—'}
                      </div>
                      <div className="truncate text-xs text-text-muted">
                        {entry.essentiality
                          ? formatEnumLabel(entry.essentiality)
                          : '—'}
                      </div>
                    </TableCell>
                    <TableCell className="text-right align-top font-mono tabular-nums">
                      {formatCurrency(debitAmount(entry.amount), {
                        decimals: 2,
                        nullDisplay: '—',
                      })}
                    </TableCell>
                    <TableCell className="text-right align-top font-mono tabular-nums">
                      {formatCurrency(creditAmount(entry.amount), {
                        decimals: 2,
                        nullDisplay: '—',
                      })}
                    </TableCell>
                    <TableCell className="text-right align-top font-mono tabular-nums">
                      <span
                        className={cn(
                          entry.balanceAfter == null ? 'text-text-muted' : 'text-text',
                        )}
                      >
                        {formatCurrency(entry.balanceAfter, {
                          decimals: 2,
                          nullDisplay: '—',
                        })}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-[220px] align-top">
                      <div className="truncate font-medium text-text">
                        {entry.sourceDocumentFilename ?? 'Unknown source'}
                      </div>
                      <div className="truncate text-xs text-text-muted">
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
                    </TableCell>
                    <TableCell className="align-top font-mono text-xs text-text-muted">
                      {shortHash(entry.rowHash)}
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
  )
}
