'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type {
  HouseholdCardCommitment,
  HouseholdCardCommitments,
} from '@/lib/api/household'
import { formatCurrencyWhole } from '@/lib/formatters'

const WELCOME_LABEL: Record<string, string> = {
  not_started: 'Bonus not started',
  in_progress: 'Bonus open',
  deadline_passed: 'Deadline passed',
  earned: 'Bonus earned',
  missed: 'Bonus missed',
  none: 'No bonus',
}

const WELCOME_VARIANT: Record<string, 'success' | 'warning' | 'outline'> = {
  not_started: 'outline',
  in_progress: 'warning',
  deadline_passed: 'warning',
  earned: 'success',
  missed: 'outline',
  none: 'outline',
}

/** Whose card it is and which one, since two Sapphires share a product name. */
function cardLabel(card: HouseholdCardCommitment): string {
  const parts = [
    card.ownerName ? card.ownerName.split(' ')[0] : null,
    card.accountMask ? `·${card.accountMask}` : null,
  ].filter(Boolean)
  return parts.length > 0
    ? `${card.productName} (${parts.join(' ')})`
    : card.productName
}

/**
 * What the cards commit the plan to, on the screen where the plan is read.
 *
 * The Cards tab has known the renewal dates and the welcome deadlines all
 * along; the Plan screen knew only a balance, and only through the
 * affordability check (P0-20). A fee that posts on a day nobody remembers is
 * money the caps have already been allowed to spend, so the annual fees show
 * here as a monthly accrual — the same figure the cap plan subtracts one card
 * up, so the two cannot disagree about what keeping these cards costs.
 */
export function CardCommitmentsCard({
  commitments,
  isLoading = false,
}: {
  commitments: HouseholdCardCommitments | null | undefined
  isLoading?: boolean
}) {
  if (!commitments || commitments.status === 'no_cards') {
    return (
      <SectionCard variant="surface" title="What the cards commit you to">
        <p className="text-sm text-text-muted">
          {isLoading && !commitments
            ? 'Reading balances, fees and bonus deadlines…'
            : (commitments?.detail ??
              'No open cards are recorded, so nothing here is tracking a balance, a fee or a deadline.')}
        </p>
      </SectionCard>
    )
  }

  const openBonus = commitments.welcomeOpenCount > 0

  return (
    <SectionCard
      variant="surface"
      title="What the cards commit you to"
      description={commitments.headline}
      actions={
        <Badge variant={openBonus ? 'warning' : 'outline'}>
          {openBonus
            ? `${commitments.welcomeOpenCount} bonus open`
            : `${formatCurrencyWhole(commitments.annualFeeMonthly)}/mo of fees`}
        </Badge>
      }
    >
      <p className="text-sm text-text-muted">{commitments.detail}</p>
      <p className="mt-1 text-sm text-text-muted">
        {commitments.nextFeeDetail}
      </p>
      {commitments.welcomeDetail ? (
        <p
          className={`mt-1 text-sm ${openBonus ? 'text-warning' : 'text-text-muted'}`}
        >
          {commitments.welcomeDetail}
        </p>
      ) : null}

      <div className="mt-3 space-y-2 border-t border-border/30 pt-3">
        {commitments.cards.map((card) => (
          <div
            key={card.cardId}
            className="rounded-2xl border border-border/35 bg-surface-muted/15 p-3"
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-text">
                {cardLabel(card)}
              </p>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm tabular-nums text-text">
                  {card.balanceOwed != null
                    ? formatCurrencyWhole(card.balanceOwed)
                    : 'Not reporting'}
                </span>
                <Badge
                  variant={WELCOME_VARIANT[card.welcomeStatus] ?? 'outline'}
                >
                  {WELCOME_LABEL[card.welcomeStatus] ?? card.welcomeStatus}
                </Badge>
              </div>
            </div>
            <p className="mt-1 text-xs text-text-muted">{card.balanceDetail}</p>
            <p className="mt-1 text-xs text-text-muted">
              {card.annualFeeDetail}
            </p>
            <p className="mt-1 text-xs text-text-muted">{card.welcomeDetail}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
