import type { HouseholdLedgerEntry } from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'

export type LedgerWindow = 'all' | '1m' | '3m' | '6m' | '12m'
export type LedgerKind = 'all' | 'transactions' | 'imports'
export type LedgerStatus = 'canonical' | 'all' | 'duplicates'
export type LedgerSortKey =
  | 'date'
  | 'account'
  | 'detail'
  | 'category'
  | 'status'
  | 'amount'

export const LEDGER_PAGE_SIZE = 50

export const ledgerWindows: Array<{ value: LedgerWindow; label: string }> = [
  { value: 'all', label: 'All' },
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
]

export const ledgerKinds: Array<{ value: LedgerKind; label: string }> = [
  { value: 'transactions', label: 'Transactions' },
  { value: 'imports', label: 'Import rows' },
  { value: 'all', label: 'All rows' },
]

export const ledgerStatuses: Array<{ value: LedgerStatus; label: string }> = [
  { value: 'canonical', label: 'Counted view' },
  { value: 'all', label: 'All source rows' },
  { value: 'duplicates', label: 'Duplicates only' },
]

/**
 * Format a ledger date for display. Ledger dates are stored at UTC midnight, so
 * formatting is pinned to the UTC timezone — a 00:00Z date must NOT render as the
 * previous calendar day in US (negative-offset) timezones. A recent fix depends
 * on this UTC pinning; do not change it.
 */
export function formatLedgerDate(value?: string | null) {
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

/**
 * Reduce a timestamp to its UTC calendar day (YYYY-MM-DD). Used for the Future
 * badge / future-day comparison so the comparison happens on the UTC calendar
 * day, matching {@link formatLedgerDate}.
 */
export function utcDateKey(value?: string | null): string | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date.toISOString().slice(0, 10)
}

export function entryDate(entry: {
  postedDate?: string | null
  date?: string | null
  uploadedAt?: string | null
}) {
  return entry.postedDate ?? entry.date ?? entry.uploadedAt ?? null
}

export function ledgerRowKey(entry: { kind: string; id: string }) {
  return `${entry.kind}-${entry.id}`
}

export function ledgerAmountLabel(entry: {
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

export type { HouseholdLedgerEntry }
