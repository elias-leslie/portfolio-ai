'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  type AccountResolutionTarget,
  recordAccountClosed,
} from '@/lib/api/household/account-lifecycle'

function ClosureForm({
  target,
  onCancel,
}: {
  target: AccountResolutionTarget
  onCancel: () => void
}) {
  const [closedDate, setClosedDate] = useState('')
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: () => recordAccountClosed(target, closedDate || null),
    onSuccess: async () => {
      await Promise.all(
        ['household', 'home', 'cards'].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      )
      toast.success(`${target.label} recorded as closed. History preserved.`)
      onCancel()
    },
  })
  return (
    <form
      className="w-full space-y-3 rounded-lg border border-border p-3"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate()
      }}
    >
      <p className="text-sm font-medium">Record {target.label} as closed?</p>
      <p className="text-xs text-text-muted">
        Keeps past transactions and stops requests for new activity. This
        records a closure that already happened; it does not contact the bank.
      </p>
      <label className="block text-xs">
        Closure date (optional)
        <Input
          type="date"
          value={closedDate}
          onChange={(event) => setClosedDate(event.target.value)}
          disabled={save.isPending}
        />
      </label>
      <p className="text-xs text-text-muted">
        Leave the date blank if you don’t know it.
      </p>
      {save.error ? (
        <p role="alert" className="text-sm text-loss">
          {save.error.message}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" type="submit" disabled={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save closed account'}
        </Button>
        <Button
          size="sm"
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={save.isPending}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function AccountClosureButton({
  target,
}: {
  target: AccountResolutionTarget
}) {
  const [confirming, setConfirming] = useState(false)
  return confirming ? (
    <ClosureForm target={target} onCancel={() => setConfirming(false)} />
  ) : (
    <Button
      size="sm"
      type="button"
      variant="outline"
      onClick={() => setConfirming(true)}
    >
      {target.kind === 'discovered'
        ? 'Already closed'
        : 'Record account closed'}
    </Button>
  )
}
