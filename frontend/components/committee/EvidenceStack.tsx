'use client'

import type { EvidenceItem } from '@/lib/committee/events'
import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

function shortLabel(claim: string): string {
  const trimmed = claim.trim()
  if (trimmed.length <= 18) return trimmed
  const firstClause = trimmed.split(/[,.;:]/)[0].trim()
  return firstClause.length <= 24 ? firstClause : `${firstClause.slice(0, 22)}…`
}

function collectEvidence(state: CommitteeUiState): EvidenceItem[] {
  const out: EvidenceItem[] = []
  for (const agent of Object.values(state.agents)) {
    for (const item of agent.evidence) {
      out.push(item)
    }
  }
  // Sort: bull first, then neutral, then bear (mockup order)
  return out.sort((a, b) => {
    const order = { bull: 0, neutral: 1, bear: 2 }
    return (order[a.side] ?? 1) - (order[b.side] ?? 1)
  })
}

export function EvidenceStack({ state }: { state: CommitteeUiState }) {
  const evidence = collectEvidence(state)
  return (
    <div className="flex h-full flex-col items-center gap-1.5 border-x border-border-subtle bg-bg/40 px-1.5 py-3">
      <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-text-muted/60">
        Evidence
      </p>
      {evidence.length === 0 ? (
        <p className="mt-2 text-center text-[9px] text-text-muted/60">
          awaiting…
        </p>
      ) : (
        evidence.slice(0, 14).map((item, idx) => (
          <div
            key={`${item.claim}-${idx}`}
            className={cn(
              'flex h-11 w-11 flex-col items-center justify-center rounded-md border bg-surface p-1 text-center',
              item.side === 'bull' && 'border-gain/50',
              item.side === 'bear' && 'border-loss/50',
              item.side === 'neutral' && 'border-warning/40',
            )}
            title={item.claim}
          >
            <p
              className={cn(
                'truncate text-[8px] font-semibold uppercase tracking-[0.04em]',
                item.side === 'bull' && 'text-gain-strong',
                item.side === 'bear' && 'text-loss-strong',
                item.side === 'neutral' && 'text-warning-strong',
              )}
            >
              {shortLabel(item.claim)}
            </p>
            <p className="font-mono text-[9px] text-text">
              {item.weight.toFixed(1)}
            </p>
          </div>
        ))
      )}
    </div>
  )
}
