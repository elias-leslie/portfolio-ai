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
            Income minus tracked spend, this window.
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
            Month-to-date spend
          </p>
          <p className="mt-3 text-2xl font-semibold text-text">
            {formatCurrencyWhole(monthToDateSpend)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            Spent so far this calendar month.
          </p>
        </div>
      </div>
    </>
  )
}
