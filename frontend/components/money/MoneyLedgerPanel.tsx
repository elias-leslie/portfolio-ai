'use client'

import { useMemo, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HouseholdLedger, HouseholdLedgerEntry } from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'

type LedgerFilter = 'all' | 'transactions' | 'imports'

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

function fingerprint(value: string) {
  return value.slice(0, 12)
}

function entryDate(entry: HouseholdLedgerEntry) {
  return entry.postedDate ?? entry.date ?? entry.uploadedAt ?? null
}

function filterEntry(entry: HouseholdLedgerEntry, filter: LedgerFilter) {
  if (filter === 'transactions') {
    return entry.kind === 'transaction'
  }
  if (filter === 'imports') {
    return entry.kind === 'import_row'
  }
  return true
}

export function MoneyLedgerPanel({
  ledger,
  isLoading,
  error,
  onRetry,
  isRetrying,
}: {
  ledger?: HouseholdLedger
  isLoading: boolean
  error: Error | null
  onRetry: () => void
  isRetrying: boolean
}) {
  const [filter, setFilter] = useState<LedgerFilter>('all')

  const visibleEntries = useMemo(
    () => (ledger?.entries ?? []).filter((entry) => filterEntry(entry, filter)),
    [filter, ledger?.entries],
  )

  if (error) {
    return (
      <LoadErrorState
        title="Failed to load the ledger."
        detail="Retry to refresh transaction provenance and imported rows."
        onRetry={onRetry}
        isRetrying={isRetrying}
      />
    )
  }

  if (isLoading && !ledger) {
    return (
      <SectionCard
        variant="surface"
        title="Ledger"
        description="Canonical audit surface for household transactions and imported rows."
      >
        <p className="text-sm text-text-muted">Loading ledger...</p>
      </SectionCard>
    )
  }

  return (
    <SectionCard
      variant="surface"
      title="Ledger"
      description="One audit surface. Every applied transaction and imported row with source provenance and fingerprint."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {(['all', 'transactions', 'imports'] as const).map((value) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={filter === value ? 'default' : 'outline'}
              onClick={() => setFilter(value)}
            >
              {value === 'all'
                ? 'All'
                : value === 'transactions'
                  ? 'Transactions'
                  : 'Import rows'}
            </Button>
          ))}
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Transactions
          </p>
          <p className="mt-2 text-2xl font-semibold text-text">
            {ledger?.transactionCount ?? 0}
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Import Rows
          </p>
          <p className="mt-2 text-2xl font-semibold text-text">
            {ledger?.importRowCount ?? 0}
          </p>
        </div>
        <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
          <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
            Last Refresh
          </p>
          <p className="mt-2 text-sm font-medium text-text">
            {formatLedgerDate(ledger?.generatedAt)}
          </p>
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-border/40 bg-surface/45">
        <div className="max-h-[68vh] overflow-y-auto">
          {visibleEntries.length === 0 ? (
            <div className="px-5 py-10 text-sm text-text-muted">
              No ledger rows match this filter.
            </div>
          ) : (
            <div className="divide-y divide-border/30">
              {visibleEntries.map((entry) => (
                <div
                  key={`${entry.kind}-${entry.id}`}
                  className="grid gap-3 px-5 py-4 lg:grid-cols-[120px_minmax(0,1.2fr)_160px_170px]"
                >
                  <div className="space-y-2">
                    <p className="text-xs uppercase tracking-[0.18em] text-text-muted">
                      {formatLedgerDate(entryDate(entry))}
                    </p>
                    <Badge
                      variant={
                        entry.kind === 'transaction' ? 'success' : 'outline'
                      }
                      className="w-fit"
                    >
                      {entry.kind === 'transaction'
                        ? 'Transaction'
                        : 'Import row'}
                    </Badge>
                  </div>

                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">
                      {entry.merchant || entry.description}
                    </p>
                    <p className="mt-1 text-sm text-text-muted">
                      {entry.description}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-muted">
                      {entry.accountLabel ? (
                        <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                          {entry.accountLabel}
                        </span>
                      ) : null}
                      {entry.category ? (
                        <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                          {formatEnumLabel(entry.category)}
                        </span>
                      ) : null}
                      {entry.essentiality ? (
                        <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                          {formatEnumLabel(entry.essentiality)}
                        </span>
                      ) : null}
                      {entry.datasetType ? (
                        <span className="rounded-full border border-border/40 bg-surface px-2.5 py-1">
                          {formatEnumLabel(entry.datasetType)}
                        </span>
                      ) : null}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <p
                      className={cn(
                        'text-right text-base font-semibold tabular-nums text-text',
                        (entry.amount ?? 0) < 0 ? 'text-loss' : 'text-gain',
                      )}
                    >
                      {formatCurrency(entry.amount)}
                    </p>
                    <p className="text-right text-xs text-text-muted">
                      {entry.currency ?? 'USD'}
                    </p>
                  </div>

                  <div className="min-w-0 text-xs text-text-muted">
                    <p className="truncate font-medium text-text">
                      {entry.sourceDocumentFilename ?? 'Unknown source'}
                    </p>
                    <p className="mt-1 truncate">
                      {[
                        entry.sourceType ? formatEnumLabel(entry.sourceType) : null,
                        entry.documentType
                          ? formatEnumLabel(entry.documentType)
                          : null,
                      ]
                        .filter(Boolean)
                        .join(' · ') || 'Stored evidence'}
                    </p>
                    <p className="mt-2 font-mono text-[11px] text-text-muted/90">
                      {fingerprint(entry.rowHash)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </SectionCard>
  )
}
