'use client'

import { Button } from '@/components/ui/button'
import type { HouseholdCreditCard } from '@/lib/api/cards'
import { useUpdateCard } from '@/lib/hooks/useCards'

export function CardBonusControls({ card }: { card: HouseholdCreditCard }) {
  const update = useUpdateCard()
  if (
    card.status === 'candidate' ||
    card.status === 'closed' ||
    card.role === 'keeper'
  )
    return null
  return (
    <div className="basis-full space-y-2 text-xs">
      <p className="text-text-muted">
        {card.welcomeStatus === 'earned'
          ? 'Bonus received. You can direct new spending toward the next card; keep this account’s history up to date.'
          : card.welcomeStatus === 'spend_met'
            ? 'Required spending met. Waiting for the bonus to arrive.'
            : 'Already finished the welcome offer?'}
      </p>
      {card.welcomeStatus !== 'earned' ? (
        <div className="flex flex-wrap gap-2">
          {card.welcomeStatus !== 'spend_met' ? (
            <Button
              size="sm"
              variant="outline"
              disabled={update.isPending}
              onClick={() =>
                update.mutate({
                  cardId: card.id,
                  payload: { welcomeStatus: 'spend_met' },
                })
              }
            >
              Spending requirement met
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                cardId: card.id,
                payload: { welcomeStatus: 'earned' },
              })
            }
          >
            Bonus received
          </Button>
        </div>
      ) : null}
      {update.error ? (
        <p role="alert" className="text-loss">
          {update.error.message}
        </p>
      ) : null}
    </div>
  )
}
