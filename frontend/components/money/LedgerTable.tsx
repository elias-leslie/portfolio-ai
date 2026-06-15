import { Button } from '@/components/ui/button'
import { formatCurrency } from '@/lib/formatters'
import type { InlineComboboxCommitOptions } from './InlineComboboxField'
import { LedgerRow } from './LedgerRow'
import {
  type HouseholdLedgerEntry,
  LEDGER_PAGE_SIZE,
  type LedgerSortKey,
  type LedgerStatus,
} from './ledger-helpers'
import { SortableTableHeader } from './SortableTableHeader'

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
  categoryOptions: string[]
  categorizePending: boolean
  onCommitCategory: (
    entry: HouseholdLedgerEntry,
    category: string,
    options?: InlineComboboxCommitOptions,
  ) => void
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
  categoryOptions,
  categorizePending,
  onCommitCategory,
}: LedgerTableProps) {
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
                <SortableTableHeader
                  field="date"
                  label="Date"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={onToggleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="account"
                  label="Account"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={onToggleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="detail"
                  label="Merchant"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={onToggleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="category"
                  label="Category"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={onToggleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="amount"
                  label="Amount"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={onToggleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="status"
                  label="Status"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={onToggleSort}
                />
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
                    categoryOptions={categoryOptions}
                    categorizePending={categorizePending}
                    onCommitCategory={
                      categorizable
                        ? (category, options) =>
                            onCommitCategory(entry, category, options)
                        : undefined
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
