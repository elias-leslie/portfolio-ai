'use client'

import type { CommitteeStage } from '@/lib/committee/events'
import type { AgentState, CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

type LaneId = 'analysts' | 'researchers' | 'trader' | 'risk' | 'pm'

interface NodeSpec {
  slug: string
  label: string
  shortSlug: string
}

interface LaneSpec {
  id: LaneId
  title: string
  nodes: NodeSpec[]
  stage: CommitteeStage
}

const LANES: LaneSpec[] = [
  {
    id: 'analysts',
    title: 'Analysts',
    stage: 'analysts',
    nodes: [
      {
        slug: 'fundamentals-v1',
        label: 'Fundamentals',
        shortSlug: 'ah/fundamentals.v1',
      },
      {
        slug: 'news-grounded-v1',
        label: 'News & Macro',
        shortSlug: 'ah/news-grounded.v1',
      },
      {
        slug: 'sentiment-grounded-v1',
        label: 'Sentiment',
        shortSlug: 'ah/sentiment-grounded.v1',
      },
      {
        slug: 'technical-v1',
        label: 'Technical',
        shortSlug: 'ah/technical.v1',
      },
    ],
  },
  {
    id: 'researchers',
    title: 'Researchers',
    stage: 'researchers',
    nodes: [
      {
        slug: 'bull-researcher-v1',
        label: 'Bull',
        shortSlug: 'ah/bull-researcher.v1',
      },
      {
        slug: 'bear-researcher-v1',
        label: 'Bear',
        shortSlug: 'ah/bear-researcher.v1',
      },
    ],
  },
  {
    id: 'trader',
    title: 'Trader',
    stage: 'trader',
    nodes: [
      { slug: 'trader-v1', label: 'Trade Composer', shortSlug: 'ah/trader.v1' },
    ],
  },
  {
    id: 'risk',
    title: 'Risk Vote',
    stage: 'risk',
    nodes: [
      {
        slug: 'risk-aggressive-v1',
        label: 'Aggressive',
        shortSlug: 'ah/risk-aggressive.v1',
      },
      {
        slug: 'risk-neutral-v1',
        label: 'Neutral',
        shortSlug: 'ah/risk-neutral.v1',
      },
      {
        slug: 'risk-conservative-v1',
        label: 'Conservative',
        shortSlug: 'ah/risk-conservative.v1',
      },
    ],
  },
  {
    id: 'pm',
    title: 'Decision',
    stage: 'pm',
    nodes: [
      {
        slug: 'portfolio-mgr-v1',
        label: 'Portfolio Mgr',
        shortSlug: 'ah/portfolio-mgr.v1',
      },
    ],
  },
]

const STAGE_ORDER: CommitteeStage[] = [
  'analysts',
  'researchers',
  'trader',
  'ips',
  'risk',
  'pm',
]

function laneState(
  lane: LaneSpec,
  state: CommitteeUiState,
): 'done' | 'live' | 'idle' {
  if (state.status === 'complete' || state.status === 'approved') {
    return 'done'
  }
  if (!state.stage) return 'idle'
  const currentIdx = STAGE_ORDER.indexOf(state.stage)
  const laneIdx = STAGE_ORDER.indexOf(lane.stage)
  if (laneIdx < currentIdx) return 'done'
  if (laneIdx === currentIdx) return 'live'
  return 'idle'
}

function nodeStatus(
  agent: AgentState | undefined,
  laneStateValue: 'done' | 'live' | 'idle',
): 'done' | 'live' | 'idle' | 'error' {
  if (agent?.status === 'error') return 'error'
  if (agent?.status === 'done') return 'done'
  if (laneStateValue === 'done') return 'done'
  if (laneStateValue === 'live') return 'live'
  return 'idle'
}

function formatScore(score: number | null | undefined): {
  text: string
  tone: 'gain' | 'loss' | 'warn' | 'muted'
} {
  if (score === null || score === undefined) {
    return { text: '—', tone: 'muted' }
  }
  const tone = score > 0.15 ? 'gain' : score < -0.15 ? 'loss' : 'warn'
  const sign = score > 0 ? '+' : score < 0 ? '−' : ''
  return { text: `${sign}${Math.abs(score).toFixed(2)}`, tone }
}

export function PipelineDag({ state }: { state: CommitteeUiState }) {
  return (
    <div className="grid grid-cols-1 gap-3 rounded-2xl border border-border bg-gradient-to-b from-surface to-bg p-3 sm:grid-cols-2 lg:grid-cols-5">
      {LANES.map((lane, laneIdx) => {
        const lstate = laneState(lane, state)
        return (
          <div key={lane.id} className="flex flex-col gap-1.5">
            <h4 className="mb-1 text-center font-semibold text-[9px] uppercase tracking-[0.2em] text-text-muted/60">
              {lane.title}
            </h4>
            {lane.nodes.map((node, nodeIdx) => {
              const agent = state.agents[node.slug]
              const status = nodeStatus(agent, lstate)
              const score = formatScore(agent?.score ?? null)
              const iconIndex = laneIdx * 4 + nodeIdx + 1
              return (
                <div
                  key={node.slug}
                  className={cn(
                    'grid grid-cols-[1.25rem_1fr_auto] items-center gap-2 rounded-lg border bg-surface px-2.5 py-1.5',
                    status === 'done' && 'border-gain/40 bg-gain/10',
                    status === 'live' &&
                      'border-primary bg-primary/15 shadow-[0_0_0_1px_var(--color-primary)] animate-pulse',
                    status === 'error' && 'border-loss/40 bg-loss/10',
                    status === 'idle' && 'border-border-subtle opacity-60',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-4 w-4 items-center justify-center rounded-full border border-border-subtle bg-bg font-mono text-[9px] text-text-muted',
                      status === 'done' &&
                        'border-gain/50 bg-gain/15 text-gain-strong',
                      status === 'live' &&
                        'border-primary bg-primary/25 text-primary',
                      status === 'error' &&
                        'border-loss/50 bg-loss/15 text-loss-strong',
                    )}
                  >
                    {status === 'done'
                      ? '✓'
                      : status === 'live'
                        ? '●'
                        : status === 'error'
                          ? '✕'
                          : iconIndex}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-[11px] font-semibold text-text">
                      {node.label}
                    </p>
                    <p className="truncate font-mono text-[9px] text-text-muted/70">
                      {node.shortSlug}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'font-mono text-[10px]',
                      score.tone === 'gain' && 'text-gain-strong',
                      score.tone === 'loss' && 'text-loss-strong',
                      score.tone === 'warn' && 'text-warning-strong',
                      score.tone === 'muted' && 'text-text-muted',
                    )}
                  >
                    {score.text}
                  </span>
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
