'use client'

import type { HouseholdBudgetVerdict } from '@/lib/api/household'
import { cn } from '@/lib/utils'

export interface MonthVerdictLineProps {
  verdict: HouseholdBudgetVerdict | null | undefined
  isLoading: boolean
}

const TONE: Record<string, string> = {
  under_plan: 'border-gain/40 bg-gain/5',
  over_plan: 'border-loss/40 bg-loss/5',
  plan_incomplete: 'border-border/35 bg-surface-muted/20',
  no_plan: 'border-border/35 bg-surface-muted/20',
}

const HEADLINE_TONE: Record<string, string> = {
  under_plan: 'text-gain',
  over_plan: 'text-loss',
}

/**
 * The sentence the review screen exists to say.
 *
 * "We did good this month, we're under budget overall" is the first thing the
 * household wants back, and until now the screen answered it with ten tiles and
 * no verdict. Both halves are shown: the headline says under or over, and the
 * line beneath it says what that nets out of -- because "over on groceries,
 * under on gas, under overall" is the actual shape of the answer.
 *
 * When most of the month runs through categories with no cap, this says so
 * rather than claiming a verdict over a minority of the money.
 */
export function MonthVerdictLine({
  verdict,
  isLoading,
}: MonthVerdictLineProps) {
  if (!verdict) {
    return (
      <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
        <p className="text-sm text-text-muted">
          {isLoading ? 'Reading the month…' : 'No verdict for this month yet.'}
        </p>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-2xl border p-4',
        TONE[verdict.status] ?? TONE.plan_incomplete,
      )}
    >
      <p
        className={cn(
          'text-base font-semibold',
          HEADLINE_TONE[verdict.status] ?? 'text-text',
        )}
      >
        {verdict.headline}
      </p>
      <p className="mt-1 text-sm text-text-muted">{verdict.detail}</p>
    </div>
  )
}
