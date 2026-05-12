/**
 * Reducer that folds committee SSE events into a single derived state
 * object the UI binds to. The reducer is pure; the SSE hook owns the
 * EventSource lifecycle.
 */

import type {
  CommitteeEvent,
  CommitteeStage,
  EvidenceItem,
  IpsCheckEvent,
  PmDecisionEvent,
  RiskVoteEvent,
  TraderProposalEvent,
} from './events'

export interface AgentState {
  slug: string
  role: string
  status: 'idle' | 'running' | 'done' | 'error'
  content_md: string
  score: number | null
  evidence: EvidenceItem[]
  tokens: number
  latency_ms: number | null
}

export interface DebateRoundState {
  round: number
  bull?: AgentState
  bear?: AgentState
  bull_score: number | null
  bear_score: number | null
  completed: boolean
}

export interface FeedbackEntry {
  round: number
  user_input: string
  input_id?: string
  resolved?: boolean
  decision_shifted?: boolean
  rebuttal_md?: string
}

export interface CommitteeUiState {
  events: CommitteeEvent[]
  status:
    | 'idle'
    | 'pending'
    | 'running'
    | 'complete'
    | 'approved'
    | 'aborted'
    | 'failed'
  stage: CommitteeStage | null
  agents: Record<string, AgentState>
  debate_rounds: DebateRoundState[]
  ips_checks: IpsCheckEvent[]
  proposal: TraderProposalEvent | null
  decision: PmDecisionEvent | null
  risk_votes: Array<RiskVoteEvent & { agent_slug: string; score: number }>
  kpi: { tokens_total: number; cost_usd: number; elapsed_ms: number | null }
  symbol: string | null
  graph_version: string | null
  started_at: string | null
  feedback: FeedbackEntry[]
  error: string | null
}

export const INITIAL_COMMITTEE_STATE: CommitteeUiState = {
  events: [],
  status: 'idle',
  stage: null,
  agents: {},
  debate_rounds: [],
  ips_checks: [],
  proposal: null,
  decision: null,
  risk_votes: [],
  kpi: { tokens_total: 0, cost_usd: 0, elapsed_ms: null },
  symbol: null,
  graph_version: null,
  started_at: null,
  feedback: [],
  error: null,
}

export function reduceCommitteeEvent(
  state: CommitteeUiState,
  event: CommitteeEvent,
): CommitteeUiState {
  // Deduplicate by seq.
  if (state.events.some((e) => e.seq === event.seq)) {
    return state
  }
  const next: CommitteeUiState = {
    ...state,
    events: [...state.events, event],
  }
  switch (event.type) {
    case 'run.start': {
      next.status = 'running'
      next.symbol = String(event.content.symbol ?? '') || state.symbol
      next.graph_version =
        String(event.content.graph_version ?? '') || state.graph_version
      next.started_at = event.ts || state.started_at
      return next
    }
    case 'run.resume': {
      next.status = 'running'
      next.symbol = String(event.content.symbol ?? '') || state.symbol
      next.graph_version =
        String(event.content.graph_version ?? '') || state.graph_version
      return next
    }
    case 'stage.enter': {
      next.stage = (event.stage ?? null) as CommitteeStage | null
      return next
    }
    case 'agent.output': {
      if (!event.agent_slug) return next
      const role = event.role ?? 'unknown'
      const content = event.content as Record<string, unknown>
      const evidence = Array.isArray(content.evidence)
        ? (content.evidence as EvidenceItem[])
        : []
      const content_md = String(
        content.content_md ??
          content.argument_md ??
          content.narrative_md ??
          content.thesis_md ??
          '',
      )
      next.agents = {
        ...state.agents,
        [event.agent_slug]: {
          slug: event.agent_slug,
          role,
          status: 'done',
          content_md,
          score: event.score,
          evidence,
          tokens: event.tokens ?? 0,
          latency_ms: event.latency_ms,
        },
      }
      // Fold researcher outputs into debate_rounds based on current stage.
      if (
        state.stage === 'researchers' &&
        (role === 'bull' || role === 'bear')
      ) {
        const round = next.debate_rounds[next.debate_rounds.length - 1]
        if (round) {
          const updatedRound: DebateRoundState = {
            ...round,
            [role]: next.agents[event.agent_slug],
            [`${role}_score`]: event.score,
          } as DebateRoundState
          next.debate_rounds = [
            ...next.debate_rounds.slice(0, -1),
            updatedRound,
          ]
        }
      }
      return next
    }
    case 'agent.error': {
      if (!event.agent_slug) return next
      const existing = state.agents[event.agent_slug]
      next.agents = {
        ...state.agents,
        [event.agent_slug]: {
          slug: event.agent_slug,
          role: existing?.role ?? 'unknown',
          status: 'error',
          content_md: existing?.content_md ?? '',
          score: existing?.score ?? null,
          evidence: existing?.evidence ?? [],
          tokens: existing?.tokens ?? 0,
          latency_ms: existing?.latency_ms ?? null,
        },
      }
      return next
    }
    case 'debate.round.start': {
      const round = Number((event.content as { round?: number }).round ?? 0)
      next.debate_rounds = [
        ...state.debate_rounds,
        { round, bull_score: null, bear_score: null, completed: false },
      ]
      return next
    }
    case 'debate.round.end': {
      const round = Number((event.content as { round?: number }).round ?? 0)
      next.debate_rounds = state.debate_rounds.map((r) =>
        r.round === round
          ? {
              ...r,
              bull_score: Number(
                (event.content as { bull_score?: number }).bull_score ?? null,
              ),
              bear_score: Number(
                (event.content as { bear_score?: number }).bear_score ?? null,
              ),
              completed: true,
            }
          : r,
      )
      return next
    }
    case 'ips.check': {
      const check = event.content as unknown as IpsCheckEvent
      next.ips_checks = [...state.ips_checks, check]
      return next
    }
    case 'trader.proposal': {
      next.proposal = event.content as unknown as TraderProposalEvent
      return next
    }
    case 'risk.vote': {
      const vote = event.content as Record<string, unknown>
      next.risk_votes = [
        ...state.risk_votes,
        {
          agent_slug: event.agent_slug ?? 'unknown',
          score: event.score ?? 0,
          vote: String(vote.vote ?? 'downgrade') as RiskVoteEvent['vote'],
          narrative_md: String(vote.narrative_md ?? ''),
          objections: Array.isArray(vote.objections)
            ? (vote.objections as RiskVoteEvent['objections'])
            : [],
        },
      ]
      return next
    }
    case 'pm.decision': {
      next.decision = event.content as unknown as PmDecisionEvent
      return next
    }
    case 'run.feedback.received': {
      const content = event.content as Record<string, unknown>
      const round = Number(content.round ?? 0)
      next.feedback = [
        ...state.feedback,
        {
          round,
          user_input: String(content.user_input ?? ''),
          input_id: String(content.input_id ?? ''),
        },
      ]
      return next
    }
    case 'run.feedback.resolved': {
      const content = event.content as Record<string, unknown>
      const round = Number(content.round ?? 0)
      next.feedback = state.feedback.map((f) =>
        f.round === round
          ? {
              ...f,
              resolved: true,
              decision_shifted: Boolean(content.decision_shifted),
              rebuttal_md: String(content.rebuttal_md ?? ''),
            }
          : f,
      )
      return next
    }
    case 'run.complete': {
      next.status = 'complete'
      const content = event.content as Record<string, unknown>
      next.kpi = {
        tokens_total: Number(content.tokens_total ?? state.kpi.tokens_total),
        cost_usd: Number(content.cost_usd ?? state.kpi.cost_usd),
        elapsed_ms: Number(content.elapsed_ms ?? null),
      }
      return next
    }
    case 'run.aborted': {
      next.status = 'aborted'
      return next
    }
    case 'run.failed': {
      next.status = 'failed'
      next.error = String((event.content as { error?: string }).error ?? '')
      return next
    }
    case 'kpi.tick': {
      const content = event.content as Record<string, unknown>
      next.kpi = {
        tokens_total: Number(content.tokens_total ?? state.kpi.tokens_total),
        cost_usd: Number(content.cost_usd ?? state.kpi.cost_usd),
        elapsed_ms: Number(content.elapsed_ms ?? null),
      }
      return next
    }
    default:
      return next
  }
}

export function reduceCommitteeEvents(
  state: CommitteeUiState,
  events: CommitteeEvent[],
): CommitteeUiState {
  return events.reduce(reduceCommitteeEvent, state)
}
