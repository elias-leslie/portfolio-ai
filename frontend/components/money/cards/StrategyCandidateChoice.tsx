'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { CardCandidate } from '@/lib/api/cards/strategy'
import { formatCurrency } from '@/lib/formatters'
import { useStrategyActions } from '@/lib/hooks/useCardStrategy'

export function StrategyCandidateChoice({
  candidate,
  label = 'Review proposal',
}: {
  candidate: CardCandidate
  label?: string
}) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const proposal = useStrategyActions().proposal
  return (
    <div className="space-y-3">
      <Button
        size="sm"
        variant="outline"
        className="h-auto max-w-full whitespace-normal"
        disabled={proposal.isPending}
        onClick={() => {
          if (candidate.spendingGap > 0) setOpen(!open)
          else proposal.mutate({ key: candidate.key })
        }}
      >
        {label}
      </Button>
      {open ? (
        <form
          className="space-y-3 rounded-lg border border-warning/40 p-3"
          onSubmit={(event) => {
            event.preventDefault()
            proposal.mutate({
              key: candidate.key,
              additionalSpendPlan: note.trim(),
            })
          }}
        >
          <p className="text-sm">
            This option needs {formatCurrency(candidate.spendingGap)} beyond the
            calculated spending for its window, including the seven-day buffer.
          </p>
          <label className="block text-sm">
            Which already-planned purchases cover the difference?
            <textarea
              className="mt-1 block w-full rounded-md border border-border bg-surface p-2"
              required
              minLength={10}
              maxLength={500}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Describe purchases already in your budget"
            />
          </label>
          <p className="text-xs text-text-muted">
            This records your plan. The calculated spending and
            transaction-based forecast stay unchanged until purchases are
            observed.
          </p>
          <Button
            size="sm"
            disabled={proposal.isPending || note.trim().length < 10}
          >
            Prepare this higher-spend proposal
          </Button>
        </form>
      ) : null}
      {proposal.error ? (
        <p role="alert" className="text-sm text-loss">
          {proposal.error.message}
        </p>
      ) : null}
    </div>
  )
}
