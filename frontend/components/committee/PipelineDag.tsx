'use client'

import type { CommitteeStage } from '@/lib/committee/events'
import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const STAGES: { id: CommitteeStage; label: string }[] = [
  { id: 'analysts', label: 'Analysts' },
  { id: 'researchers', label: 'Debate' },
  { id: 'trader', label: 'Trader' },
  { id: 'ips', label: 'IPS' },
  { id: 'risk', label: 'Risk' },
  { id: 'pm', label: 'PM' },
]

export function PipelineDag({ state }: { state: CommitteeUiState }) {
  const stageOrder = STAGES.map((s) => s.id)
  const currentIdx = state.stage ? stageOrder.indexOf(state.stage) : -1
  return (
    <ol className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.2em]">
      {STAGES.map((stage, idx) => {
        const visited =
          idx <= currentIdx ||
          state.status === 'complete' ||
          state.status === 'approved'
        const active = idx === currentIdx && state.status === 'running'
        return (
          <li key={stage.id} className="flex items-center gap-1.5">
            <span
              className={cn(
                'rounded-full px-2.5 py-1 border transition-colors',
                visited
                  ? 'border-primary/40 bg-primary/15 text-text'
                  : 'border-border-subtle bg-surface text-text-muted',
                active && 'animate-pulse border-primary text-text',
              )}
            >
              {stage.label}
            </span>
            {idx < STAGES.length - 1 ? (
              <span className="h-px w-4 bg-border-subtle" aria-hidden />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
