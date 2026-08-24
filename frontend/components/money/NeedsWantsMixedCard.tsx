'use client'

import { Badge } from '@/components/ui/badge'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { formatCurrencyWhole, formatPercent } from '@/lib/formatters'
import { formatCategoryPreview } from './overview-helpers'

export interface NeedsWantsMixedCardProps {
  dashboard: HouseholdFinanceDashboard | null | undefined
  isLoading: boolean
}

/**
 * Needs, wants and mixed — on the screen where categories are actually edited.
 *
 * Two things about this card are load-bearing. It shows **three** shares, not
 * two: the mixed bucket was computed nowhere and displayed nowhere, so the card
 * summed to 90% while a quarter of the money sat outside it (P1-8). And it
 * names what mixed means, because a Household or Cash row genuinely can be a
 * repair or a treat and the household is the only one who can say which.
 *
 * It reads the trailing monthly average, so it is a shape-of-spending answer
 * rather than a verdict on the month being reviewed — the verdict line above
 * owns that.
 */
export function NeedsWantsMixedCard({
  dashboard,
  isLoading,
}: NeedsWantsMixedCardProps) {
  if (!dashboard?.reports) {
    return (
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-sm font-semibold text-text">
          Needs, wants and mixed
        </p>
        <p className="mt-1 text-sm text-text-muted">
          {isLoading ? 'Reading the split…' : 'No category split yet.'}
        </p>
      </div>
    )
  }

  const { executive, categoryBreakdown } = dashboard.reports
  const needsAmount = executive.averageMonthlyEssentials
  const wantsAmount = executive.averageMonthlyDiscretionary
  const mixedAmount = executive.averageMonthlyMixed
  const trackedMonthlySpend = executive.averageMonthlySpend
  const share = (amount: number) =>
    trackedMonthlySpend > 0 ? (amount / trackedMonthlySpend) * 100 : null

  const rows = [
    {
      label: 'Needs',
      amount: needsAmount,
      share: share(needsAmount),
      categories: categoryBreakdown.filter(
        (category) => category.essentiality === 'essential',
      ),
    },
    {
      label: 'Wants',
      amount: wantsAmount,
      share: share(wantsAmount),
      categories: categoryBreakdown.filter(
        (category) => category.essentiality === 'discretionary',
      ),
    },
    {
      label: 'Mixed',
      amount: mixedAmount,
      share: share(mixedAmount),
      categories: categoryBreakdown.filter(
        (category) =>
          category.essentiality !== 'essential' &&
          category.essentiality !== 'discretionary',
      ),
    },
  ]

  return (
    <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">
            Needs, wants and mixed
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            {formatCurrencyWhole(trackedMonthlySpend)}/mo typical, split three
            ways.
          </p>
        </div>
        {rows[0].share != null ? (
          <Badge variant={wantsAmount > needsAmount ? 'warning' : 'secondary'}>
            {wantsAmount > needsAmount
              ? `Wants leading ${formatPercent(rows[1].share ?? 0, { decimals: 0 })}`
              : `Needs leading ${formatPercent(rows[0].share ?? 0, { decimals: 0 })}`}
          </Badge>
        ) : null}
      </div>

      <dl className="mt-3 space-y-2 border-t border-border/30 pt-3">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <dt className="font-medium text-text">
                {row.label}{' '}
                <span className="text-text-muted">
                  {formatPercent(row.share, { decimals: 0, nullDisplay: '—' })}
                </span>
              </dt>
              <dd className="font-mono tabular-nums text-text">
                {formatCurrencyWhole(row.amount)}
              </dd>
            </div>
            <p className="mt-0.5 text-xs text-text-muted">
              {formatCategoryPreview(row.categories)}
            </p>
          </div>
        ))}
      </dl>

      {mixedAmount > 0 ? (
        <p className="mt-3 text-xs text-text-muted/80">
          Mixed is spending that is genuinely neither — a Household or Cash row
          can be a repair or a treat. It is shown so the three shares account
          for every tracked dollar.
        </p>
      ) : null}
    </div>
  )
}
