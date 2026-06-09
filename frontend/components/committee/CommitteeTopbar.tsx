'use client'

import { Button } from '@/components/ui/button'
import type { CommitteeUiState } from '@/lib/committee/reducer'
import { formatElapsed } from '@/lib/formatters'
import { cn } from '@/lib/utils'

function shortRunId(runId: string | null): string {
  if (!runId) return '—'
  return runId.slice(0, 8)
}

function formatStartedTime(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

const STAGE_ORDER = [
  'analysts',
  'researchers',
  'trader',
  'ips',
  'risk',
  'pm',
] as const
const TOTAL_STAGES = STAGE_ORDER.length

function stageIndex(stage: string | null): number {
  if (!stage) return 0
  const idx = STAGE_ORDER.indexOf(stage as (typeof STAGE_ORDER)[number])
  return idx < 0 ? 0 : idx + 1
}

interface CommitteeTopbarProps {
  state: CommitteeUiState
  runId: string | null
  startedAt: string | null
  onPause: () => void
  onResume: () => void
  onAbort: () => void
  onApprove: () => void
  approving: boolean
}

export function CommitteeTopbar({
  state,
  runId,
  startedAt,
  onPause,
  onResume,
  onAbort,
  onApprove,
  approving,
}: CommitteeTopbarProps) {
  const decision = state.decision
  const proposal = state.proposal
  const referencePrice = decision ? null : (proposal?.entry_price ?? null)
  const actionLabel = decision
    ? `${decision.action.toUpperCase()}${
        decision.qty_pct ? ` ${(decision.qty_pct * 100).toFixed(1)}%` : ''
      }`
    : null

  return (
    <div className="grid grid-cols-1 items-center gap-3 border-b border-border pb-3 md:grid-cols-[auto_1fr_auto]">
      <div className="flex items-baseline gap-3">
        <h1 className="font-display text-xl italic text-text">Committee</h1>
        <div className="flex items-baseline gap-2 rounded-lg border border-border bg-surface px-2.5 py-1 font-mono">
          <span className="text-sm font-bold tracking-[0.05em] text-text">
            {state.symbol ?? '—'}
          </span>
          {referencePrice !== null ? (
            <span className="text-xs text-text-muted">
              ref ${referencePrice.toFixed(2)}
            </span>
          ) : null}
        </div>
      </div>

      <div className="text-center font-mono text-[11px] text-text-muted">
        run/<b className="text-text">{shortRunId(runId)}</b> · graph/
        <b className="text-text">{state.graph_version ?? 'committee'}</b> ·
        stage{' '}
        <b className="text-text">
          {stageIndex(state.stage)}/{TOTAL_STAGES}
        </b>{' '}
        · started <b className="text-text">{formatStartedTime(startedAt)}</b> ·
        elapsed{' '}
        <b className="text-text">{formatElapsed(state.kpi.elapsed_ms)}</b>
      </div>

      <div className="flex flex-wrap items-center justify-end gap-1.5">
        {state.status === 'running' || state.status === 'pending' ? (
          <>
            <Button variant="outline" size="sm" onClick={onPause}>
              Pause
            </Button>
            <Button variant="outline" size="sm" onClick={onResume}>
              Resume
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onAbort}
              className={cn('text-loss-strong border-loss/40')}
            >
              Abort
            </Button>
          </>
        ) : null}
        {state.status === 'complete' && decision ? (
          <Button
            size="sm"
            onClick={onApprove}
            disabled={approving || decision.action === 'hold'}
          >
            {approving
              ? 'Executing…'
              : decision.action === 'hold'
                ? 'Hold (no trade)'
                : `Approve · ${actionLabel}`}
          </Button>
        ) : null}
        {state.status === 'approved' ? (
          <span className="rounded-full border border-gain/50 bg-gain/15 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-gain-strong">
            Executed
          </span>
        ) : null}
        {state.status === 'aborted' ? (
          <span className="rounded-full border border-loss/50 bg-loss/15 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-loss-strong">
            Aborted
          </span>
        ) : null}
      </div>
    </div>
  )
}
