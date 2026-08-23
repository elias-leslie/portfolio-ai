'use client'

import type { HouseholdSpendComparator } from '@/lib/api/household'
import { formatCurrencyWhole, formatPercent } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { formatFullMonthLabel } from './budget-helpers'

export interface MonthComparatorRowProps {
  monthLabel: string
  totalSpend: number | null | undefined
  totalIncome: number | null | undefined
  netCashFlow: number | null | undefined
  oneTimeSpend: number | null | undefined
  everydaySpend: number | null | undefined
  comparators: HouseholdSpendComparator[]
  coverageMonthKeys: string[]
}

function changeTone(change: number) {
  if (Math.abs(change) < 1) return 'text-text-muted'
  return change > 0 ? 'text-loss' : 'text-gain'
}

function changeText(comparator: HouseholdSpendComparator) {
  const direction = comparator.spendChange > 0 ? 'more' : 'less'
  const pct =
    comparator.spendChangePct == null
      ? null
      : formatPercent(Math.abs(comparator.spendChangePct) * 100, {
          decimals: 0,
        })
  if (Math.abs(comparator.spendChange) < 1) {
    return 'about the same'
  }
  return `${formatCurrencyWhole(Math.abs(comparator.spendChange))} ${direction}${
    pct ? ` (${pct})` : ''
  }`
}

/**
 * In, out, and what the month is being read against.
 *
 * Two fixed comparators replace the sliding windows (D3): the month before, and
 * the average of every complete month on record. Both name the months they used,
 * so the arithmetic can be checked rather than trusted.
 */
export function MonthComparatorRow({
  monthLabel,
  totalSpend,
  totalIncome,
  netCashFlow,
  oneTimeSpend,
  everydaySpend,
  comparators,
  coverageMonthKeys,
}: MonthComparatorRowProps) {
  const hasOneTime = (oneTimeSpend ?? 0) >= 1

  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          Money in · {monthLabel}
        </p>
        <p className="mt-3 text-2xl font-semibold text-text">
          {formatCurrencyWhole(totalIncome)}
        </p>
        <p className="mt-1 text-xs text-text-muted">
          Tracked deposits, reversals netted out.
        </p>
      </div>
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          Money out · {monthLabel}
        </p>
        <p className="mt-3 text-2xl font-semibold text-text">
          {formatCurrencyWhole(totalSpend)}
        </p>
        {hasOneTime ? (
          <p className="mt-1 text-xs text-text-muted">
            {formatCurrencyWhole(everydaySpend)} everyday ·{' '}
            {formatCurrencyWhole(oneTimeSpend)} one-time.
          </p>
        ) : (
          <p className="mt-1 text-xs text-text-muted">
            No one-time purchase carried this month.
          </p>
        )}
      </div>
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          Left over
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
          In minus out, this month.
        </p>
      </div>
      {comparators.map((comparator) => (
        <div
          key={comparator.key}
          className="rounded-2xl border border-border/35 bg-surface-muted/10 p-4 md:col-span-3 lg:col-span-1"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
            vs {comparator.label}
          </p>
          <p
            className={cn(
              'mt-3 text-lg font-semibold',
              changeTone(comparator.spendChange),
            )}
          >
            {changeText(comparator)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {formatCurrencyWhole(comparator.totalSpend)} out ·{' '}
            {comparator.basis === 'full_month'
              ? 'full month'
              : comparator.basisLabel}
            .
          </p>
          {comparator.key === 'all_month_average' &&
          coverageMonthKeys.length > 0 ? (
            <p className="mt-1 text-xs text-text-muted/80">
              {coverageMonthKeys.map(formatFullMonthLabel).join(', ')}.
            </p>
          ) : null}
        </div>
      ))}
    </div>
  )
}
