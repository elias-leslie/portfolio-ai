'use client'

import { Button } from '@/components/ui/button'
import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const ACTION_TONE: Record<string, string> = {
  buy: 'text-gain-strong',
  add: 'text-gain',
  sell: 'text-loss-strong',
  trim: 'text-loss',
  hold: 'text-text-muted',
}

export function VerdictBar({
  state,
  onApprove,
  onAbort,
  onPause,
  onResume,
  onRetro,
  approving,
}: {
  state: CommitteeUiState
  onApprove: () => void
  onAbort: () => void
  onPause: () => void
  onResume: () => void
  onRetro: () => void
  approving: boolean
}) {
  const decision = state.decision
  return (
    <div className="rounded-2xl border border-border-subtle bg-surface-overlay/60 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted/60">
            Verdict
          </p>
          {decision ? (
            <div className="mt-1 flex flex-wrap items-baseline gap-3">
              <span
                className={cn(
                  'font-display text-2xl tracking-tight',
                  ACTION_TONE[decision.action] ?? 'text-text',
                )}
              >
                {decision.action.toUpperCase()}
              </span>
              <span className="font-mono text-sm text-text">
                {(decision.qty_pct * 100).toFixed(1)}% portfolio
              </span>
              <span className="font-mono text-xs text-text-muted">
                conf {decision.confidence.toFixed(2)} · {decision.horizon}
              </span>
            </div>
          ) : (
            <p className="mt-1 text-sm text-text-muted">
              PM has not issued a decision yet.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {state.status === 'running' ? (
            <>
              <Button variant="outline" size="sm" onClick={onPause}>
                Pause
              </Button>
              <Button variant="outline" size="sm" onClick={onResume}>
                Resume
              </Button>
              <Button variant="outline" size="sm" onClick={onAbort}>
                Abort
              </Button>
            </>
          ) : null}
          {state.status === 'complete' ? (
            <>
              <Button
                onClick={onApprove}
                disabled={approving || !decision || decision.action === 'hold'}
              >
                {approving ? 'Executing…' : 'Approve & Execute'}
              </Button>
              <Button variant="outline" size="sm" onClick={onAbort}>
                Discard
              </Button>
            </>
          ) : null}
          {state.status === 'approved' ? (
            <Button variant="outline" size="sm" onClick={onRetro}>
              Start Retro
            </Button>
          ) : null}
          {state.feedback.length > 0 ? null : null}
        </div>
      </div>
      {decision?.rationale_md ? (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-text">
          {decision.rationale_md}
        </p>
      ) : null}
      {decision?.rebuttal_md ? (
        <div className="mt-3 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-text">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-warning-strong">
            Rebuttal
          </p>
          <p className="mt-1 whitespace-pre-wrap">{decision.rebuttal_md}</p>
        </div>
      ) : null}
    </div>
  )
}
