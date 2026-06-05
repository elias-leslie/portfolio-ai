import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { formatCurrencyWhole, formatEnumLabel } from '@/lib/formatters'
import { paceBadgeVariant } from './overview-helpers'
import type { useDecisionBoard } from './useDecisionBoard'

type DecisionBoardData = ReturnType<typeof useDecisionBoard>

export function RecurringBillsCard({
  dueSoonCommitments,
}: Pick<DecisionBoardData, 'dueSoonCommitments'>) {
  return (
    <SectionCard
      variant="surface"
      title="Recurring Bills"
      description="Known commitments and near-term due dates."
    >
      <div className="space-y-3">
        {dueSoonCommitments.length === 0 ? (
          <p className="text-sm text-text-muted">
            No recurring bill pattern is visible yet.
          </p>
        ) : (
          dueSoonCommitments.map((commitment) => (
            <div
              key={`${commitment.merchant}-${commitment.lastSeen}`}
              className="rounded-xl border border-border/30 bg-surface-muted/15 p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-text">
                  {commitment.merchant}
                </p>
                <Badge variant={paceBadgeVariant(commitment.dueStatus)}>
                  {formatEnumLabel(commitment.dueStatus)}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-text-muted">
                {formatCurrencyWhole(commitment.averageAmount)} ·{' '}
                {formatEnumLabel(commitment.cadence)}
              </p>
              <p className="mt-1 text-xs text-text-muted">
                {commitment.daysUntilDue == null
                  ? 'No due-date estimate yet.'
                  : commitment.daysUntilDue === 0
                    ? 'Expected today.'
                    : `Expected in ${commitment.daysUntilDue} day${commitment.daysUntilDue === 1 ? '' : 's'}.`}
              </p>
            </div>
          ))
        )}
      </div>
    </SectionCard>
  )
}
