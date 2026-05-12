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
    <div className="overflow-hidden rounded-2xl border border-border bg-gradient-to-b from-surface to-bg">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-text-muted/70">
        <span>Add a claim · the committee scores it</span>
        {state.feedback.length > 0 ? (
          <span className="font-mono text-text-muted">
            {state.feedback.filter((f) => f.resolved).length}/
            {state.feedback.length} resolved
          </span>
        ) : null}
      </div>
      <form
        className="space-y-2 px-3 py-3"
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
        <textarea
          className="min-h-[64px] w-full rounded-xl border border-border-subtle bg-surface px-3 py-2 text-[12px] text-text placeholder:text-text-muted/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
          placeholder="e.g. China tariff news shifts the bear case…"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={disabled} size="sm">
            {sending ? 'Sending…' : 'Add claim'}
          </Button>
        </div>
        {state.feedback.length > 0 ? (
          <div className="flex flex-col gap-2 pt-2">
            {state.feedback.map((entry) => (
              <div
                key={`${entry.round}-${entry.input_id ?? 'noid'}`}
                className="rounded-xl border border-border-subtle bg-bg/60 p-2.5 text-[12px] text-text-muted"
              >
                <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-text-muted/70">
                  Round {entry.round}
                  {entry.resolved
                    ? entry.decision_shifted
                      ? ' · decision shifted'
                      : ' · unchanged'
                    : ' · pending'}
                </p>
                <p className="mt-1 text-text">{entry.user_input}</p>
                {entry.rebuttal_md ? (
                  <p className="mt-1.5 whitespace-pre-wrap rounded-lg border border-warning/30 bg-warning/10 px-2 py-1.5 text-text">
                    {entry.rebuttal_md}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </form>
    </div>
  )
}
