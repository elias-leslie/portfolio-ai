'use client'

import { formatCurrencyWhole } from '@/lib/formatters'
import { shortDate } from './overview-helpers'

export interface BudgetStatRowProps {
  unknownTransactionCount: number
  unknownSpend: number
  foundBudgetTotal: number
  foundBudgetCategoryCount: number
  connectedMonthToDateSpend: number | null | undefined
  monthToDateSpend: number | null | undefined
  connectedPendingCount: number
  connectedPendingSpend: number
  evidenceMonthToDateSpend: number
  monthToDateAsOfDate: string | null
}

/**
 * Three tiles, where there were ten.
 *
 * The other seven were each a true number that some other element on this
 * screen already says better: the run-rate and monthly income are in the
 * comparator row, net cash flow and the savings rate are Left over, and the
 * cap totals, budgeted-category count and over-budget count are the verdict
 * line's own arithmetic. Ten tiles of undisputed facts is how a screen ends up
 * with no answer on it.
 *
 * What survives is what nothing else answers, and each is a thing to do:
 * purchases with no category, caps offered but not accepted, and how much of
 * the month came from a linked feed rather than a receipt.
 */
export function BudgetStatRow({
  unknownTransactionCount,
  unknownSpend,
  foundBudgetTotal,
  foundBudgetCategoryCount,
  connectedMonthToDateSpend,
  monthToDateSpend,
  connectedPendingCount,
  connectedPendingSpend,
  evidenceMonthToDateSpend,
  monthToDateAsOfDate,
}: BudgetStatRowProps) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          Unknown purchases
        </p>
        <p className="mt-3 text-2xl font-semibold text-text">
          {unknownTransactionCount}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          purchase{unknownTransactionCount === 1 ? '' : 's'} to categorize ·{' '}
          {formatCurrencyWhole(unknownSpend)}
        </p>
      </div>
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          Caps waiting on you
        </p>
        <p className="mt-3 text-2xl font-semibold text-text">
          {foundBudgetCategoryCount}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          suggested row{foundBudgetCategoryCount === 1 ? '' : 's'} not accepted
          yet · {formatCurrencyWhole(foundBudgetTotal)}
        </p>
      </div>
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          Connected MTD spend
        </p>
        <p className="mt-3 text-2xl font-semibold text-text">
          {formatCurrencyWhole(connectedMonthToDateSpend ?? monthToDateSpend)}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          Plaid/SnapTrade through {shortDate(monthToDateAsOfDate)}.
          {connectedPendingCount > 0
            ? ` ${connectedPendingCount} pending transaction${connectedPendingCount === 1 ? '' : 's'} included (${formatCurrencyWhole(connectedPendingSpend)}).`
            : ' No pending linked transactions.'}
        </p>
        {Math.abs(evidenceMonthToDateSpend) >= 1 ? (
          <p className="mt-1 text-xs text-text-muted/80">
            Receipt/order evidence excluded here:{' '}
            {formatCurrencyWhole(evidenceMonthToDateSpend)}.
          </p>
        ) : null}
        {monthToDateSpend != null &&
        connectedMonthToDateSpend != null &&
        Math.abs(monthToDateSpend - connectedMonthToDateSpend) >= 1 ? (
          <p className="mt-1 text-xs text-text-muted/80">
            All-source MTD before evidence exclusion:{' '}
            {formatCurrencyWhole(monthToDateSpend)}.
          </p>
        ) : null}
      </div>
    </div>
  )
}
