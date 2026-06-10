'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { HouseholdCreditCard } from '@/lib/api/cards'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'
import {
  daysBetween,
  formatShortDate,
  parseIsoDate,
  playerLabel,
} from './cards-helpers'

/**
 * MSR (minimum-spend requirement) pace card for the active in-progress
 * welcome bonus. The backend stores only the cumulative progress amount —
 * no per-day trajectory — so this renders an honest pace stat strip instead
 * of fabricating a time series.
 */
export function WelcomeProgressChart({
  cards,
}: {
  cards: HouseholdCreditCard[]
}) {
  const inProgress = cards.filter(
    (card) =>
      !card.closedDate &&
      card.welcomeStatus === 'in_progress' &&
      (card.product?.welcomeMinSpend ?? 0) > 0,
  )

  if (inProgress.length === 0) return null

  const today = new Date()

  return (
    <SectionCard
      variant="surface"
      title="Welcome bonus pace"
      description="Minimum-spend requirement progress vs the pace needed to hit the deadline."
    >
      <div className="space-y-6">
        {inProgress.map((card) => {
          const minSpend = card.product?.welcomeMinSpend ?? 0
          const progress = card.welcomeProgressAmount
          const remaining = Math.max(0, minSpend - progress)
          const deadline = parseIsoDate(card.welcomeDeadline)
          const opened = parseIsoDate(card.openedDate)
          const daysLeft = deadline ? daysBetween(today, deadline) : null
          const daysElapsed = opened
            ? Math.max(1, daysBetween(opened, today))
            : null
          const currentPace = daysElapsed ? progress / daysElapsed : null
          const requiredPace =
            daysLeft != null && daysLeft > 0 ? remaining / daysLeft : null
          const projectedDays =
            currentPace && currentPace > 0
              ? Math.ceil(remaining / currentPace)
              : null
          const projectedDate =
            projectedDays != null
              ? new Date(today.getTime() + projectedDays * 86_400_000)
              : null
          const onTrack =
            remaining === 0 ||
            (projectedDate != null &&
              deadline != null &&
              projectedDate <= deadline)

          return (
            <div key={card.id} className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-text">
                  {card.product?.productName ?? 'Card'}
                </span>
                <Badge variant="outline">{playerLabel(card.player)}</Badge>
                <Badge variant={onTrack ? 'success' : 'warning'}>
                  {onTrack ? 'On pace' : 'Behind pace'}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2">
                  <p className="text-xs text-text-muted">Spend to date</p>
                  <p className="font-medium tabular-nums text-text">
                    {formatCurrencyWhole(progress)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2">
                  <p className="text-xs text-text-muted">Remaining to MSR</p>
                  <p className="font-medium tabular-nums text-text">
                    {formatCurrencyWhole(remaining)} of{' '}
                    {formatCurrencyWhole(minSpend)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2">
                  <p className="text-xs text-text-muted">Days to deadline</p>
                  <p className="font-medium tabular-nums text-text">
                    {daysLeft != null ? daysLeft : '—'}
                    {card.welcomeDeadline
                      ? ` (${formatShortDate(card.welcomeDeadline)})`
                      : ''}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2">
                  <p className="text-xs text-text-muted">Required pace</p>
                  <p className="font-medium tabular-nums text-text">
                    {requiredPace != null
                      ? `${formatCurrency(requiredPace, { decimals: 0 })}/day`
                      : '—'}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/40 bg-surface-muted/20 px-3 py-2">
                  <p className="text-xs text-text-muted">
                    Projected completion
                  </p>
                  <p className="font-medium tabular-nums text-text">
                    {remaining === 0
                      ? 'Done'
                      : projectedDate
                        ? projectedDate.toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })
                        : 'No spend yet'}
                  </p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </SectionCard>
  )
}
