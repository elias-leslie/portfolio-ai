'use client'

import { formatCurrencyWhole, formatPercent } from '@/lib/formatters'
import { cn } from '@/lib/utils'

export interface BudgetStatRowProps {
  averageMonthlySpend: number | null | undefined
  foundBudgetTotal: number
  foundBudgetCategoryCount: number
  confirmedBudgetTotal: number
  unknownTransactionCount: number
  unknownSpend: number
  budgetedCategoryCount: number
  confirmedBudgetCategoryCount: number
  overBudgetCount: number
  foundOverBudgetCount: number
  confirmedOverBudgetCount: number
  averageMonthlyIncome: number | null | undefined
  netCashFlow: number | null | undefined
  savingsRate: number | null | undefined
  monthToDateSpend: number | null | undefined
  connectedMonthToDateSpend: number | null | undefined
  connectedPendingCount: number
  connectedPendingSpend: number
  evidenceMonthToDateSpend: number
  monthToDateAsOfDate: string | null
  observedMonthlyDetail: string
  /** Selected budget window label (1M/3M/6M) so net cash flow names its window. */
  windowLabel: string
}

function shortDate(value: string | null) {
  if (!value) return 'today'
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

export function BudgetStatRow({
  averageMonthlySpend,
  foundBudgetTotal,
  foundBudgetCategoryCount,
  confirmedBudgetTotal,
  unknownTransactionCount,
  unknownSpend,
  budgetedCategoryCount,
  confirmedBudgetCategoryCount,
  overBudgetCount,
  foundOverBudgetCount,
  confirmedOverBudgetCount,
  averageMonthlyIncome,
  netCashFlow,
  savingsRate,
  monthToDateSpend,
  connectedMonthToDateSpend,
  connectedPendingCount,
  connectedPendingSpend,
  evidenceMonthToDateSpend,
  monthToDateAsOfDate,
  observedMonthlyDetail,
  windowLabel,
}: BudgetStatRowProps) {
  return (
    <>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Observed monthly spend
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {formatCurrencyWhole(averageMonthlySpend)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {observedMonthlyDetail}
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Suggested cap total
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {formatCurrencyWhole(foundBudgetTotal)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {foundBudgetCategoryCount} suggested row
            {foundBudgetCategoryCount === 1 ? '' : 's'} not accepted yet.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Confirmed cap total
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {formatCurrencyWhole(confirmedBudgetTotal)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Manual or accepted category caps.
          </p>
        </div>
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
            Budgeted categories
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {budgetedCategoryCount}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {foundBudgetCategoryCount} suggested ·{' '}
            {confirmedBudgetCategoryCount} confirmed.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Over budget
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {overBudgetCount}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {foundOverBudgetCount} suggested · {confirmedOverBudgetCount}{' '}
            confirmed.
          </p>
        </div>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Monthly income
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {formatCurrencyWhole(averageMonthlyIncome)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Tracked inflow, averaged.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Net cash flow
          </p>
          <p
            className={cn(
              'mt-3 text-2xl font-semibold',
              (netCashFlow ?? 0) >= 0 ? 'text-gain' : 'text-loss',
            )}
          >
            {formatCurrencyWhole(netCashFlow)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Income minus tracked spend over this {windowLabel} window.
          </p>
        </div>
        <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            Savings rate
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {savingsRate != null
              ? formatPercent(savingsRate * 100, {
                  decimals: 0,
                })
              : '—'}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Share of income not spent.
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
    </>
  )
}
