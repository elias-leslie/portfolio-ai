'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { HouseholdCapPlan } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'
import { cn } from '@/lib/utils'

const SOURCE_LABEL: Record<string, string> = {
  essential: 'Essential',
  shaped: 'Shaped by history',
  sinking_fund: 'Sinking fund',
  no_history: 'No history',
}

/**
 * Where the suggested caps come from — income first, history only for shape.
 *
 * The suggestion this replaces was each category's own run-rate nudged by a
 * percentage, which summed to more than the household takes home: a month could
 * clear every cap and still lose money (D6). The subtraction is printed in full
 * because the answer is uncomfortable — these categories currently run above
 * what the anchor supports, and a plan that hid that would just be the old
 * suggestion with better manners.
 */
export function CapPlanCard({
  plan,
  isLoading = false,
}: {
  plan: HouseholdCapPlan | null | undefined
  isLoading?: boolean
}) {
  if (!plan) {
    return (
      <SectionCard variant="surface" title="Where the caps come from">
        <p className="text-sm text-text-muted">
          {isLoading
            ? 'Pricing caps against the income anchor…'
            : 'No cap plan is available yet.'}
        </p>
      </SectionCard>
    )
  }

  const overspending = plan.gapToTrailing < 0
  const lines = [
    {
      label: 'Income anchor',
      amount: plan.anchorMonthlyIncome ?? 0,
      subtract: false,
    },
    { label: 'less Saving', amount: plan.savingsTarget, subtract: true },
    {
      label: 'less Sinking fund accruals',
      amount: plan.sinkingFundTotal,
      subtract: true,
    },
    {
      label: 'less Essentials at cost',
      amount: plan.essentialsTotal,
      subtract: true,
    },
  ]

  return (
    <SectionCard
      variant="surface"
      title="Where the caps come from"
      description={plan.headline}
      actions={
        <Badge variant={overspending ? 'warning' : 'success'}>
          {overspending
            ? `${formatCurrencyWhole(Math.abs(plan.gapToTrailing))} over`
            : `${formatCurrencyWhole(plan.gapToTrailing)} of room`}
        </Badge>
      }
    >
      <p className="text-sm text-text-muted">{plan.detail}</p>
      {plan.driftDetail ? (
        <p
          className={cn(
            'mt-1 text-sm',
            overspending ? 'text-warning' : 'text-text-muted',
          )}
        >
          {plan.driftDetail}
        </p>
      ) : null}

      <dl className="mt-3 space-y-1 border-t border-border/30 pt-3 text-xs">
        {lines.map((line) => (
          <div
            key={line.label}
            className="flex items-baseline justify-between gap-3"
          >
            <dt className="text-text-muted">{line.label}</dt>
            <dd className="font-mono tabular-nums text-text-muted">
              {line.subtract ? '−' : ''}
              {formatCurrencyWhole(line.amount)}
            </dd>
          </div>
        ))}
        <div className="flex items-baseline justify-between gap-3 border-t border-border/30 pt-1 font-medium">
          <dt className="text-text">Left to divide</dt>
          <dd className="font-mono tabular-nums text-text">
            {formatCurrencyWhole(plan.discretionaryPool)}
          </dd>
        </div>
      </dl>

      {plan.rows.length > 0 ? (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-text-muted">
              <tr>
                <th className="py-1 pr-3 font-medium">Category</th>
                <th className="py-1 pr-3 font-medium">Basis</th>
                <th className="py-1 pr-3 text-right font-medium">Runs at</th>
                <th className="py-1 text-right font-medium">Proposed cap</th>
              </tr>
            </thead>
            <tbody>
              {plan.rows
                .filter((row) => row.proposedCap > 0 || row.trailingMonthly > 0)
                .map((row) => (
                  <tr key={row.category} className="border-t border-border/20">
                    <td className="py-1 pr-3 text-text">{row.category}</td>
                    <td className="py-1 pr-3 text-text-muted">
                      {SOURCE_LABEL[row.source] ?? row.source}
                    </td>
                    <td className="py-1 pr-3 text-right font-mono tabular-nums text-text-muted">
                      {formatCurrencyWhole(row.trailingMonthly)}
                    </td>
                    <td
                      className={cn(
                        'py-1 text-right font-mono tabular-nums',
                        row.changeFromTrailing < 0
                          ? 'text-warning'
                          : 'text-text',
                      )}
                    >
                      {formatCurrencyWhole(row.proposedCap)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </SectionCard>
  )
}
