'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HouseholdCreditCard } from '@/lib/api/cards'
import { useUpdateCard } from '@/lib/hooks/useCards'
import { playerLabel } from './cards-helpers'

export function CardHistoryEditor({ card }: { card: HouseholdCreditCard }) {
  const update = useUpdateCard()
  const [draft, setDraft] = useState({
    player: card.player,
    annualFee: card.product?.annualFee.toString() ?? '',
    openedDate: card.openedDate?.slice(0, 10) ?? '',
    annualFeeDueDate: card.annualFeeDueDate?.slice(0, 10) ?? '',
    closedDate: card.closedDate?.slice(0, 10) ?? '',
    welcomeEarnedDate: card.welcomeEarnedDate?.slice(0, 10) ?? '',
    welcomeStatus: card.welcomeStatus,
    welcomeMinSpend: card.product?.welcomeMinSpend?.toString() ?? '',
    welcomeDeadline: card.welcomeDeadline?.slice(0, 10) ?? '',
  })
  const fields = [
    ['openedDate', 'Opened'],
    ['annualFeeDueDate', 'Next annual fee'],
    ['welcomeEarnedDate', 'Bonus received'],
    ['closedDate', 'Closed'],
    ['welcomeDeadline', 'Welcome spending deadline'],
  ] as const
  return (
    <details className="basis-full text-sm">
      <summary className="cursor-pointer text-text-muted">
        Owner and card history
      </summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <label>
          Owner
          <select
            className="mt-1 block w-full rounded border border-border bg-surface p-2"
            value={draft.player}
            onChange={(e) => setDraft({ ...draft, player: e.target.value })}
          >
            <option value="p1">{playerLabel('p1')}</option>
            <option value="p2">{playerLabel('p2')}</option>
          </select>
        </label>
        {fields.map(([key, label]) => (
          <label key={key}>
            {label}
            <Input
              type="date"
              className="mt-1"
              value={draft[key]}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
            />
          </label>
        ))}
        <label>
          This card’s annual fee
          <Input
            type="number"
            min="0"
            value={draft.annualFee}
            onChange={(e) => setDraft({ ...draft, annualFee: e.target.value })}
          />
        </label>
        <label>
          Original offer minimum spend
          <Input
            type="number"
            min="0"
            value={draft.welcomeMinSpend}
            placeholder="Confirm from your offer"
            onChange={(e) =>
              setDraft({ ...draft, welcomeMinSpend: e.target.value })
            }
          />
        </label>
        <label>
          Welcome bonus
          <select
            className="mt-1 block w-full rounded border border-border bg-surface p-2"
            value={draft.welcomeStatus}
            onChange={(e) =>
              setDraft({ ...draft, welcomeStatus: e.target.value })
            }
          >
            <option value="not_started">Not started</option>
            <option value="in_progress">In progress</option>
            <option value="spend_met">Spending met · awaiting bonus</option>
            <option value="earned">Received</option>
            <option value="expired">Expired</option>
            <option value="not_eligible">Not eligible</option>
          </select>
        </label>
      </div>
      <p className="my-2 text-xs text-text-muted">
        Record what happened on this owner’s card. These dates update the plan;
        they do not open or close an account with the issuer.
      </p>
      <Button
        size="sm"
        disabled={update.isPending}
        onClick={() =>
          update.mutate({
            cardId: card.id,
            payload: {
              ...draft,
              annualFee:
                draft.annualFee === '' ? null : Number(draft.annualFee),
              openedDate: draft.openedDate || null,
              annualFeeDueDate: draft.annualFeeDueDate || null,
              closedDate: draft.closedDate || null,
              welcomeEarnedDate: draft.welcomeEarnedDate || null,
              welcomeDeadline: draft.welcomeDeadline || null,
              welcomeMinSpend:
                draft.welcomeMinSpend === ''
                  ? null
                  : Number(draft.welcomeMinSpend),
            },
          })
        }
      >
        Save history
      </Button>
    </details>
  )
}
