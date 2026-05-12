'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { CommitteeUiState } from '@/lib/committee/reducer'

export function ChatComposer({
  state,
  onSubmit,
}: {
  state: CommitteeUiState
  onSubmit: (text: string) => Promise<void>
}) {
  const [value, setValue] = useState('')
  const [sending, setSending] = useState(false)
  const disabled =
    sending ||
    !value.trim() ||
    state.status === 'aborted' ||
    state.status === 'failed'

  return (
    <form
      className="space-y-2"
      onSubmit={async (e) => {
        e.preventDefault()
        if (disabled) return
        setSending(true)
        try {
          await onSubmit(value)
          setValue('')
        } finally {
          setSending(false)
        }
      }}
    >
      <label className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted/60">
        Add a claim — the committee will score it
      </label>
      <textarea
        className="min-h-[80px] w-full rounded-2xl border border-border-subtle bg-surface px-3 py-2 text-sm text-text placeholder:text-text-muted/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
        placeholder="e.g. China tariff news shifts the bear case…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <div className="flex flex-wrap gap-3">
        {state.feedback.map((entry) => (
          <div
            key={`${entry.round}-${entry.input_id ?? 'noid'}`}
            className="flex-1 rounded-xl border border-border-subtle bg-surface-elev/60 p-2 text-xs text-text-muted"
          >
            <p className="font-semibold uppercase tracking-[0.16em] text-text-muted/60">
              Round {entry.round}
              {entry.resolved
                ? entry.decision_shifted
                  ? ' · shifted'
                  : ' · unchanged'
                : ' · pending'}
            </p>
            <p className="mt-1 text-text">{entry.user_input}</p>
            {entry.rebuttal_md ? (
              <p className="mt-1 whitespace-pre-wrap text-text-muted">
                {entry.rebuttal_md}
              </p>
            ) : null}
          </div>
        ))}
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={disabled} size="sm">
          {sending ? 'Sending…' : 'Add claim'}
        </Button>
      </div>
    </form>
  )
}
