'use client'

import Link from 'next/link'
import { useState } from 'react'
import { AccountClosureButton } from '@/components/money/AccountClosureButton'
import { CardBonusControls } from '@/components/money/cards/CardBonusControls'
import type { AccountResolutionTarget } from '@/lib/api/household/account-lifecycle'
import { useOwnedCards } from '@/lib/hooks/useCards'

function CardOptions({ accountId }: { accountId: string }) {
  const cards = useOwnedCards()
  const card = cards.data?.find((item) => item.householdAccountId === accountId)
  if (cards.isLoading)
    return (
      <p role="status" className="text-xs text-text-muted">
        Loading card details…
      </p>
    )
  if (cards.error)
    return (
      <p role="alert" className="text-xs">
        Card details unavailable.{' '}
        <button
          type="button"
          className="underline"
          onClick={() => cards.refetch()}
        >
          Retry
        </button>
      </p>
    )
  return card ? (
    <>
      <CardBonusControls card={card} />
      <Link
        className="block text-xs underline"
        href={`/money?tab=cards#card-${card.id}`}
      >
        Card history and rotation plan
      </Link>
    </>
  ) : null
}

export function HomeAccountOptions({
  target,
}: {
  target: AccountResolutionTarget
}) {
  const [open, setOpen] = useState(false)
  return (
    <details
      className="basis-full text-sm"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer text-text-muted">
        Account options
      </summary>
      {open ? (
        <div className="mt-3 space-y-3">
          {target.kind === 'registered' &&
          target.accountType === 'credit_card' ? (
            <CardOptions accountId={target.id} />
          ) : null}
          <AccountClosureButton target={target} />
        </div>
      ) : null}
    </details>
  )
}
