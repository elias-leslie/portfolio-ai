'use client'

import type {
  AgentState,
  CommitteeUiState,
  DebateRoundState,
} from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'
import { EvidenceStack } from './EvidenceStack'

function liveRound(state: CommitteeUiState): DebateRoundState | undefined {
  return state.debate_rounds[state.debate_rounds.length - 1]
}

function ColumnHeader({
  side,
  agentSlug,
  score,
}: {
  side: 'bull' | 'bear'
  agentSlug: string
  score: number | null | undefined
}) {
  const label = side === 'bull' ? 'Bull' : 'Bear'
  const tone = side === 'bull' ? 'text-gain-strong' : 'text-loss-strong'
  const avatarTone =
    side === 'bull'
      ? 'border-gain/50 bg-gain/15 text-gain-strong'
      : 'border-loss/50 bg-loss/15 text-loss-strong'
  return (
    <div
      className={cn(
        'flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] text-text-muted',
        side === 'bear' && 'flex-row-reverse text-right',
      )}
    >
      <span
        className={cn(
          'flex h-6 w-6 items-center justify-center rounded-full border font-display text-xs italic',
          avatarTone,
        )}
      >
        {side === 'bull' ? 'B' : 'b'}
      </span>
      <div className={cn(side === 'bear' && 'text-right')}>
        <span className="block">{label}</span>
        <span
          className={cn('block font-mono text-[10px] tracking-[0.04em]', tone)}
        >
          {agentSlug}
          {score !== null && score !== undefined
            ? ` · ${score >= 0 ? '+' : ''}${score.toFixed(2)}`
            : ''}
        </span>
      </div>
    </div>
  )
}

function Bubble({
  side,
  agent,
  roundLabel,
  isLatest,
}: {
  side: 'bull' | 'bear'
  agent: AgentState | undefined
  roundLabel: string
  isLatest: boolean
}) {
  const tone = side === 'bull' ? 'border-gain/30' : 'border-loss/30'
  const content = agent?.content_md ?? ''
  const lines = content.split('\n').filter((l) => l.trim())
  const headline = lines[0] ?? ''
  const body = lines.slice(1).join('\n')
  const isStreaming = isLatest && agent?.status !== 'done'

  return (
    <div
      className={cn(
        'rounded-xl border bg-surface px-3 py-2.5 text-[12px] leading-relaxed text-text',
        tone,
        isStreaming && 'border-dashed opacity-90',
      )}
    >
      <h5 className="mb-1 font-display text-sm italic text-text">
        {isStreaming ? `${roundLabel} · streaming` : roundLabel}
      </h5>
      {headline ? <p className="font-medium text-text">{headline}</p> : null}
      {body ? (
        <p className="mt-1 whitespace-pre-wrap text-text-muted">{body}</p>
      ) : !headline ? (
        <p className="text-text-muted/60">Awaiting argument…</p>
      ) : null}
      {agent?.tokens ? (
        <p className="mt-2 inline-flex rounded-full border border-border-subtle bg-bg/40 px-2 py-0.5 font-mono text-[9px] text-text-muted">
          tokens {agent.tokens}
        </p>
      ) : null}
    </div>
  )
}

function Column({
  side,
  state,
}: {
  side: 'bull' | 'bear'
  state: CommitteeUiState
}) {
  const sideAgents = Object.values(state.agents).filter((a) => a.role === side)
  const tone = side === 'bull' ? 'bg-gain/[0.04]' : 'bg-loss/[0.04]'
  if (state.debate_rounds.length === 0) {
    return (
      <div
        className={cn(
          'flex min-h-[20rem] flex-col gap-2 p-3.5 text-center text-text-muted',
          tone,
        )}
      >
        <p className="mt-auto mb-auto text-[12px]">
          Debate starts after analysts finish.
        </p>
      </div>
    )
  }
  return (
    <div className={cn('flex flex-col gap-2 p-3.5', tone)}>
      {state.debate_rounds.map((round, idx) => {
        const agent = round[side]
        const isLatest =
          idx === state.debate_rounds.length - 1 && !round.completed
        return (
          <Bubble
            key={`${side}-${round.round}`}
            side={side}
            agent={agent}
            roundLabel={`Round ${round.round + 1}`}
            isLatest={isLatest}
          />
        )
      })}
      {state.debate_rounds.length === 0 && sideAgents.length > 0 ? (
        <Bubble
          side={side}
          agent={sideAgents[0]}
          roundLabel="Opening"
          isLatest={false}
        />
      ) : null}
    </div>
  )
}

export function DebatePane({ state }: { state: CommitteeUiState }) {
  const round = liveRound(state)
  const totalRounds = 3
  const currentRound = round ? round.round + 1 : 0
  const bullAgent = round?.bull
  const bearAgent = round?.bear

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-gradient-to-b from-surface to-bg">
      <div className="grid grid-cols-1 items-center gap-3 border-b border-border bg-bg/60 px-4 py-2.5 md:grid-cols-[1fr_auto_1fr]">
        <ColumnHeader
          side="bull"
          agentSlug={bullAgent?.slug ?? 'bull-researcher.v1'}
          score={bullAgent?.score ?? null}
        />
        <p className="text-center font-mono text-[11px] text-text-muted">
          round{' '}
          <span className="block font-display text-base italic text-text">
            {currentRound} of {totalRounds}
          </span>
        </p>
        <ColumnHeader
          side="bear"
          agentSlug={bearAgent?.slug ?? 'bear-researcher.v1'}
          score={bearAgent?.score ?? null}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_4rem_1fr]">
        <Column side="bull" state={state} />
        <EvidenceStack state={state} />
        <Column side="bear" state={state} />
      </div>
    </div>
  )
}
