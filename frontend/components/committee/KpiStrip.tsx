'use client'

import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

function formatNumber(n: number): string {
  return n.toLocaleString('en-US')
}

function formatElapsed(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.round((ms % 60_000) / 1000)
  return `${minutes}m ${seconds}s`
}

export function KpiStrip({ state }: { state: CommitteeUiState }) {
  const items = [
    { label: 'Tokens', value: formatNumber(state.kpi.tokens_total) },
    { label: 'Elapsed', value: formatElapsed(state.kpi.elapsed_ms) },
    {
      label: 'Bull',
      value:
        state.debate_rounds.length > 0
          ? (
              state.debate_rounds[state.debate_rounds.length - 1].bull_score ??
              0
            ).toFixed(2)
          : '—',
    },
    {
      label: 'Bear',
      value:
        state.debate_rounds.length > 0
          ? (
              state.debate_rounds[state.debate_rounds.length - 1].bear_score ??
              0
            ).toFixed(2)
          : '—',
    },
    { label: 'Status', value: state.status },
  ]
  return (
    <div className="flex flex-wrap items-stretch gap-0 divide-x divide-border-subtle rounded-2xl border border-border-subtle bg-surface/60">
      {items.map((item) => (
        <div key={item.label} className={cn('flex-1 px-4 py-3')}>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted/60">
            {item.label}
          </p>
          <p className="mt-1 font-mono text-sm tracking-tight text-text">
            {item.value}
          </p>
        </div>
      ))}
    </div>
  )
}
