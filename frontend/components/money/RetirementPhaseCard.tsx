'use client'

import { Badge } from '@/components/ui/badge'
import type { HouseholdRetirementContributionTracker } from '@/lib/api/household'
import { formatCurrencyWhole, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'

export interface RetirementPhaseCardProps {
  block: HouseholdRetirementContributionTracker | null | undefined
  isLoading: boolean
}

const TONE: Record<string, string> = {
  plan_holds: 'border-gain/40 bg-gain/5',
  short: 'border-warning/40 bg-warning/5',
  unmeasurable: 'border-border/35 bg-surface-muted/20',
  phase_unknown: 'border-border/35 bg-surface-muted/20',
}

const HEADLINE_TONE: Record<string, string> = {
  plan_holds: 'text-gain',
}

const STATUS_LABEL: Record<string, string> = {
  plan_holds: 'Plan holds',
  short: 'Short',
  unmeasurable: 'Unmeasurable',
  phase_unknown: 'No phase',
}

const BLIND_SPOT_LABEL: Record<string, string> = {
  no_retirement_account_activity:
    'No account in the ledger is labelled as a retirement account.',
  withdrawal_rate_unset: 'No withdrawal rate is recorded.',
  target_retirement_spend_unset: 'No target retirement spend is recorded.',
}

/**
 * Is the retirement plan still on track — asked in the terms the household's
 * current phase calls for.
 *
 * The block this replaces graded contribution compliance and reported
 * "on track" from a $0 target against $0 contributions, while assets grew at
 * roughly 66× the contribution it was measuring. Accumulating with growth
 * carrying the plan, accumulating with contributions binding, and drawing down
 * are three different questions, and the server decides which one applies from
 * the primary adult's age against the household's own target retirement age.
 *
 * It sits on the review screen because of the two-way link: the plan assumes a
 * monthly retirement spend, the month being reviewed shows what actually goes
 * out, and this is the one screen where the household sees both at once.
 */
export function RetirementPhaseCard({
  block,
  isLoading,
}: RetirementPhaseCardProps) {
  if (!block) {
    return (
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-sm font-semibold text-text">Retirement plan</p>
        <p className="mt-1 text-sm text-text-muted">
          {isLoading ? 'Reading the plan…' : 'No retirement plan to read yet.'}
        </p>
      </div>
    )
  }

  const blindSpots = block.blindSpots
    .map((spot) => BLIND_SPOT_LABEL[spot] ?? formatEnumLabel(spot))
    .filter(Boolean)

  return (
    <div
      className={cn(
        'rounded-2xl border p-4',
        TONE[block.status] ?? TONE.unmeasurable,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-text">Retirement plan</p>
          {block.phaseLabel ? (
            <p className="mt-0.5 text-xs text-text-muted">{block.phaseLabel}</p>
          ) : null}
        </div>
        <Badge variant={block.status === 'plan_holds' ? 'success' : 'warning'}>
          {STATUS_LABEL[block.status] ?? formatEnumLabel(block.status)}
        </Badge>
      </div>

      <p
        className={cn(
          'mt-2 text-sm font-medium',
          HEADLINE_TONE[block.status] ?? 'text-text',
        )}
      >
        {block.headline}
      </p>
      <p className="mt-1 text-sm text-text-muted">{block.detail}</p>

      {block.sustainableMonthlySpend != null ? (
        <dl className="mt-3 space-y-1 border-t border-border/30 pt-3 text-xs">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-text-muted">
              Supported at{' '}
              {block.withdrawalRate != null
                ? `${(block.withdrawalRate * 100).toFixed(1)}%`
                : 'your rule'}{' '}
              of {formatCurrencyWhole(block.investableAssets)}
            </dt>
            <dd className="font-mono tabular-nums text-text-muted">
              {formatCurrencyWhole(block.sustainableMonthlySpend)}/mo
            </dd>
          </div>
          {block.targetMonthlySpend != null ? (
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-text-muted">Plan assumes</dt>
              <dd className="font-mono tabular-nums text-text-muted">
                {formatCurrencyWhole(block.targetMonthlySpend)}/mo
              </dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      {blindSpots.length > 0 ? (
        <div className="mt-2 space-y-1">
          {blindSpots.map((spot) => (
            <p key={spot} className="text-xs text-text-muted/80">
              {spot}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
