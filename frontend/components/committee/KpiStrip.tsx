'use client'

import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

function formatTokens(total: number): string {
  if (total < 1000) return total.toString()
  if (total < 100_000) return `${(total / 1000).toFixed(1)}k`
  return `${Math.round(total / 1000)}k`
}

function formatCost(cost: number): string {
  if (cost === 0) return '$0.00'
  if (cost < 0.01) return '<$0.01'
  return `$${cost.toFixed(2)}`
}

function formatElapsed(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms)) return '—'
  const seconds = Math.floor(ms / 1000)
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function decisionToneClass(action: string | null | undefined): string {
  switch (action) {
    case 'buy':
    case 'add':
      return 'text-gain-strong'
    case 'sell':
    case 'trim':
      return 'text-loss-strong'
    case 'hold':
      return 'text-warning-strong'
    default:
      return 'text-text-muted'
  }
}

export function KpiStrip({ state }: { state: CommitteeUiState }) {
  const decision = state.decision
  const proposal = state.proposal
  const lastRound = state.debate_rounds[state.debate_rounds.length - 1]

  const decisionLabel = decision
    ? `${decision.action.toUpperCase()}${
        decision.qty_pct ? ` ${(decision.qty_pct * 100).toFixed(1)}%` : ''
      }`
    : proposal
      ? `${proposal.action.toUpperCase()} (prov)`
      : '—'
  const confidence = decision ? decision.confidence.toFixed(2) : '—'
  const bullScore = lastRound?.bull_score ?? null
  const bearScore = lastRound?.bear_score ?? null
  const position = proposal ? `${(proposal.qty_pct * 100).toFixed(1)}% wt` : '—'

  const cells = [
    {
      label: 'Decision',
      value: decisionLabel,
      valueClass: decisionToneClass(decision?.action),
    },
    {
      label: 'Confidence',
      value: confidence,
      valueClass: 'text-text',
    },
    {
      label: 'Bull / Bear',
      value: null,
      bullBear: { bull: bullScore, bear: bearScore },
    },
    {
      label: 'Position',
      value: position,
      valueClass: 'text-warning-strong',
    },
    {
      label: 'Tokens · Cost',
      value: `${formatTokens(state.kpi.tokens_total)} · ${formatCost(state.kpi.cost_usd)}`,
      valueClass: 'text-text',
    },
    {
      label: 'Elapsed',
      value: formatElapsed(state.kpi.elapsed_ms),
      valueClass: 'text-chart-blue',
    },
  ] as const

  return (
    <div className="grid grid-cols-2 overflow-hidden rounded-2xl border border-border bg-surface sm:grid-cols-3 lg:grid-cols-6">
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="border-b border-r border-border-subtle px-3 py-2.5 last:border-r-0 sm:last:border-r [&:nth-child(3n)]:sm:border-r-0 lg:[&:nth-child(3n)]:border-r lg:[&:nth-child(6n)]:border-r-0"
        >
          <p className="text-[9px] font-semibold uppercase tracking-[0.18em] text-text-muted/70">
            {cell.label}
          </p>
          {cell.value !== null && 'value' in cell ? (
            <p className={cn('mt-0.5 font-mono text-base', cell.valueClass)}>
              {cell.value}
            </p>
          ) : null}
          {'bullBear' in cell && cell.bullBear ? (
            <p className="mt-0.5 font-mono text-base text-text">
              <span className="text-gain-strong">
                {cell.bullBear.bull !== null
                  ? `${cell.bullBear.bull >= 0 ? '+' : ''}${cell.bullBear.bull.toFixed(2)}`
                  : '—'}
              </span>
              <span className="px-1 text-text-muted">/</span>
              <span className="text-loss-strong">
                {cell.bullBear.bear !== null
                  ? `${cell.bullBear.bear >= 0 ? '+' : ''}${cell.bullBear.bear.toFixed(2)}`
                  : '—'}
              </span>
            </p>
          ) : null}
        </div>
      ))}
    </div>
  )
}
