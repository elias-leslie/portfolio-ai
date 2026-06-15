import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { formatCurrency } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { LedgerRow } from './LedgerRow'
import {
  type HouseholdLedgerEntry,
  LEDGER_PAGE_SIZE,
  type LedgerSortKey,
  type LedgerStatus,
} from './ledger-helpers'

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

interface LedgerTableProps {
  timeframeLabel?: string | null
  pageEntries: HouseholdLedgerEntry[]
  filteredCount: number
  totalEntryCount?: number
  visibleDebitTotal: number
  visibleCreditTotal: number
  visibleNetMovement: number
  status: LedgerStatus
  sortKey: LedgerSortKey
  sortDirection: 'asc' | 'desc'
  onToggleSort: (nextKey: LedgerSortKey) => void
  isLoading: boolean
  hasLedger: boolean
  pageStart: number
  pageEnd: number
  boundedPage: number
  totalPages: number
  expandedAuditRow: string | null
  onToggleAudit: (rowKey: string | null) => void
  onPreviousPage: () => void
  onNextPage: () => void
  /** Start editing a categorizable transaction row's category. */
  onStartCategorize: (entry: HouseholdLedgerEntry) => void
  /** Returns the shared category editor while the entry is being edited, else null. */
  categoryEditorFor: (entry: HouseholdLedgerEntry) => ReactNode | null
}

export function LedgerTable({
  timeframeLabel,
  pageEntries,
  filteredCount,
  totalEntryCount,
  visibleDebitTotal,
  visibleCreditTotal,
  visibleNetMovement,
  status,
  sortKey,
  sortDirection,
  onToggleSort,
  isLoading,
  hasLedger,
  pageStart,
  pageEnd,
  boundedPage,
  totalPages,
  expandedAuditRow,
  onToggleAudit,
  onPreviousPage,
  onNextPage,
  onStartCategorize,
  categoryEditorFor,
}: LedgerTableProps) {
  function headerButton(
    label: string,
    key: LedgerSortKey,
    align: 'left' | 'right' = 'left',
  ) {
    const active = sortKey === key
    return (
      <button
        type="button"
        onClick={() => onToggleSort(key)}
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

  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="flex flex-col gap-2 border-b border-border/40 px-4 py-3 text-xs text-text-muted md:flex-row md:items-center md:justify-between">
        <span>
          {timeframeLabel ?? 'All dates'} · {filteredCount} matching row
          {filteredCount === 1 ? '' : 's'}
          {status === 'canonical'
            ? ' · proven duplicate overlap hidden'
            : hasLedger && filteredCount !== totalEntryCount
              ? ` of ${totalEntryCount}`
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
            {isLoading && !hasLedger ? (
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
                const rowKey = `${entry.kind}-${entry.id}`
                const categorizable =
                  entry.kind === 'transaction' && !entry.removed
                return (
                  <LedgerRow
                    key={rowKey}
                    entry={entry}
                    auditOpen={expandedAuditRow === rowKey}
                    onToggleAudit={onToggleAudit}
                    onStartCategorize={
                      categorizable ? () => onStartCategorize(entry) : undefined
                    }
                    categoryEditor={
                      categorizable ? categoryEditorFor(entry) : null
                    }
                  />
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
            onClick={onPreviousPage}
          >
            Previous
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={boundedPage >= totalPages}
            onClick={onNextPage}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
