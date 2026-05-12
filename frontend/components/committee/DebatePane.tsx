'use client'

import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

export function DebatePane({ state }: { state: CommitteeUiState }) {
  if (state.debate_rounds.length === 0) {
    return (
      <div className="rounded-2xl border border-border-subtle bg-surface/40 p-6 text-center text-sm text-text-muted">
        Debate begins after analysts finish.
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {state.debate_rounds.map((round) => (
        <div
          key={round.round}
          className="rounded-2xl border border-border-subtle bg-surface/40 p-4"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted/60">
            Round {round.round + 1}
            {round.completed ? ' · Resolved' : ' · Live'}
          </p>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <Column side="bull" agent={round.bull} score={round.bull_score} />
            <Column side="bear" agent={round.bear} score={round.bear_score} />
          </div>
        </div>
      ))}
    </div>
  )
}

function Column({
  side,
  agent,
  score,
}: {
  side: 'bull' | 'bear'
  agent: CommitteeUiState['agents'][string] | undefined
  score: number | null
}) {
  const surface =
    side === 'bull' ? 'bg-gain/15 border-gain/40' : 'bg-loss/15 border-loss/40'
  const accent = side === 'bull' ? 'text-gain-strong' : 'text-loss-strong'
  return (
    <div className={cn('rounded-xl border p-3', surface)}>
      <div className="flex items-center justify-between">
        <p
          className={cn(
            'text-[10px] font-semibold uppercase tracking-[0.2em]',
            accent,
          )}
        >
          {side === 'bull' ? 'Bull' : 'Bear'}
        </p>
        <span className="font-mono text-xs text-text-muted">
          {score !== null ? score.toFixed(2) : '—'}
        </span>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-text">
        {agent?.content_md || (
          <span className="text-text-muted/60">Awaiting argument…</span>
        )}
      </p>
    </div>
  )
}
