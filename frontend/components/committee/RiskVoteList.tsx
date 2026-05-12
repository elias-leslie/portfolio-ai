'use client'

import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const VOTE_TONE: Record<string, string> = {
  approve: 'text-gain border-gain/40 bg-gain/10',
  downgrade: 'text-warning border-warning/40 bg-warning/10',
  reject: 'text-loss border-loss/40 bg-loss/10',
}

export function RiskVoteList({ state }: { state: CommitteeUiState }) {
  if (state.risk_votes.length === 0) {
    return (
      <div className="rounded-2xl border border-border-subtle bg-surface/40 p-4 text-center text-sm text-text-muted">
        Risk voters weigh in after IPS checks resolve.
      </div>
    )
  }
  return (
    <ul className="space-y-2">
      {state.risk_votes.map((vote) => (
        <li
          key={vote.agent_slug}
          className={cn(
            'rounded-xl border px-3 py-2',
            VOTE_TONE[vote.vote] ?? 'text-text border-border-subtle bg-surface',
          )}
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold uppercase tracking-[0.16em]">
              {vote.agent_slug.replace('-v1', '').replace('risk-', '')}
            </span>
            <span className="font-mono">
              {vote.vote} · {vote.score.toFixed(2)}
            </span>
          </div>
          <p className="mt-1 text-sm text-text">{vote.narrative_md}</p>
        </li>
      ))}
    </ul>
  )
}
