import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { HouseholdSpendExclusions } from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'

/**
 * What the spend filters held out of every total on this page.
 *
 * The filters used to run silently against a hardcoded string list, so a Zelle
 * payment to a tutor left the totals with nothing to point at. The number is
 * only checkable if the household can see what sits behind it.
 */
export function ExcludedFromSpendCard({
  exclusions,
}: {
  exclusions: HouseholdSpendExclusions
}) {
  const { rules } = exclusions
  const appealable = rules.filter((rule) => rule.appealable)

  return (
    <SectionCard
      variant="surface"
      title="Left out of spend"
      description="Rows these totals do not count, and why."
    >
      {exclusions.excludedCount === 0 ? (
        <p className="text-sm text-text-muted">{exclusions.summary}</p>
      ) : (
        <div className="space-y-3">
          <div className="flex items-baseline gap-3">
            <p className="text-2xl font-semibold text-text">
              {formatCurrencyWhole(exclusions.excludedAmount)}
            </p>
            <p className="text-xs text-text-muted">
              across {exclusions.excludedCount.toLocaleString()} of{' '}
              {(
                exclusions.excludedCount + exclusions.includedCount
              ).toLocaleString()}{' '}
              rows
            </p>
          </div>
          <p className="text-sm text-text-muted">{exclusions.summary}</p>

          <ul className="space-y-2">
            {rules.map((rule) => (
              <li
                key={rule.rule}
                className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-text">{rule.label}</p>
                  <p className="text-sm text-text-muted">
                    {formatCurrencyWhole(rule.totalAmount)}
                  </p>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <p className="text-xs text-text-muted">
                    {rule.transactionCount.toLocaleString()}{' '}
                    {rule.transactionCount === 1 ? 'row' : 'rows'}
                    {rule.sampleMerchants.length > 0
                      ? ` · ${rule.sampleMerchants.join(', ')}`
                      : ''}
                  </p>
                  {rule.appealable ? (
                    <Badge variant="warning">Often wrong</Badge>
                  ) : null}
                </div>
                {rule.restoredCount > 0 ? (
                  <p className="mt-1 text-xs text-primary">
                    {rule.restoredCount.toLocaleString()} of these now count as
                    spend because you said so (
                    {formatCurrencyWhole(rule.restoredAmount)}).
                  </p>
                ) : null}
              </li>
            ))}
          </ul>

          {appealable.length > 0 ? (
            <p className="text-xs text-text-muted/80">
              A rule marked <span className="text-warning">Often wrong</span>{' '}
              matches on wording alone — a Zelle payment can be rent or a tutor,
              and cash becomes whatever it bought. Open the Ledger to count any
              of these rows as spend.
            </p>
          ) : null}
        </div>
      )}
    </SectionCard>
  )
}
