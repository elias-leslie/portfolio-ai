/**
 * SSE event schema for the Investment Committee.
 * Mirrors backend/app/agents/committee/schemas.py + the type strings emitted
 * by graph.run_committee.
 */

export type CommitteeStage =
  | 'analysts'
  | 'researchers'
  | 'trader'
  | 'ips'
  | 'risk'
  | 'pm'
  | 'feedback'
  | 'system'

export type CommitteeEventType =
  | 'run.start'
  | 'stage.enter'
  | 'agent.start'
  | 'agent.output'
  | 'agent.error'
  | 'debate.round.start'
  | 'debate.round.end'
  | 'ips.check'
  | 'trader.proposal'
  | 'risk.vote'
  | 'pm.decision'
  | 'run.feedback.received'
  | 'run.feedback.resolved'
  | 'run.complete'
  | 'run.aborted'
  | 'run.failed'
  | 'kpi.tick'

export type Side = 'bull' | 'bear' | 'neutral'

export interface EvidenceItem {
  claim: string
  source: string | null
  side: Side
  weight: number
}

export interface IpsCheckEvent {
  name: 'concentration' | 'tax_bill' | 'sector_exposure' | 'wash_sale'
  passed: boolean
  severity: 'block' | 'warn' | 'info'
  detail: string
  value: number | null
  threshold: number | null
}

export interface TraderProposalEvent {
  action: 'buy' | 'sell' | 'trim' | 'add' | 'hold'
  qty_pct: number
  entry_price: number
  stop_price: number | null
  horizon: string
  rationale_md: string
  signers: string[]
}

export interface PmDecisionEvent {
  action: 'buy' | 'sell' | 'trim' | 'add' | 'hold'
  qty_pct: number
  qty: number
  confidence: number
  horizon: string
  signers: string[]
  rationale_md: string
  rebuttal_md: string | null
}

export interface RiskVoteEvent {
  vote: 'approve' | 'downgrade' | 'reject'
  narrative_md: string
  objections: Array<{ claim: string; severity: 'low' | 'medium' | 'high' }>
}

export interface CommitteeEvent {
  seq: number
  ts: string
  run_id: string
  type: CommitteeEventType
  stage: CommitteeStage | null
  agent_slug: string | null
  role: string | null
  content: Record<string, unknown>
  score: number | null
  tokens: number | null
  latency_ms: number | null
}
