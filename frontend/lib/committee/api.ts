import { get, post } from '@/lib/api/client'
import type { CommitteeEvent, PmDecisionEvent } from './events'

export interface CommitteeRunRow {
  id: string
  symbol: string
  household_id: string | null
  status: 'pending' | 'running' | 'complete' | 'approved' | 'aborted' | 'failed'
  decision_action: string | null
  decision_qty: number | null
  decision_pct_portfolio: number | null
  decision_price: number | null
  decision_horizon: string | null
  confidence: number | null
  bull_score: number | null
  bear_score: number | null
  parent_run_id: string | null
  graph_version: string
  started_at: string | null
  completed_at: string | null
  approved_at: string | null
  aborted_at: string | null
  error: string | null
  tokens_total: number
  cost_usd: number
}

export interface CommitteeRunSnapshot {
  run: CommitteeRunRow
  events: CommitteeEvent[]
}

export interface StartRunResponse {
  run_id: string
  symbol: string
  status: string
  graph_version: string
}

export interface ApproveResponse {
  paper_trade_id: string
  run_id: string
  symbol: string
  action: string
  qty: number
  price: number
}

export async function startCommitteeRun(input: {
  symbol: string
  parentRunId?: string
}): Promise<StartRunResponse> {
  return post<StartRunResponse>('/api/committee/runs', {
    symbol: input.symbol,
    parent_run_id: input.parentRunId ?? null,
  })
}

export async function fetchCommitteeRun(
  runId: string,
): Promise<CommitteeRunSnapshot> {
  return get<CommitteeRunSnapshot>(`/api/committee/runs/${runId}`)
}

export async function approveCommitteeRun(
  runId: string,
): Promise<ApproveResponse> {
  return post<ApproveResponse>(`/api/committee/runs/${runId}/approve`, {})
}

export async function submitCommitteeFeedback(
  runId: string,
  userInput: string,
): Promise<{ input_id: string; round: number }> {
  return post<{ input_id: string; round: number }>(
    `/api/committee/runs/${runId}/feedback`,
    { user_input: userInput },
  )
}

export async function pauseCommitteeRun(
  runId: string,
): Promise<{ paused: boolean }> {
  return post<{ paused: boolean }>(`/api/committee/runs/${runId}/pause`, {})
}

export async function resumeCommitteeRun(
  runId: string,
): Promise<{ resumed: boolean }> {
  return post<{ resumed: boolean }>(`/api/committee/runs/${runId}/resume`, {})
}

export async function abortCommitteeRun(
  runId: string,
): Promise<{ aborted: boolean }> {
  return post<{ aborted: boolean }>(`/api/committee/runs/${runId}/abort`, {})
}

export async function startRetroRun(runId: string): Promise<StartRunResponse> {
  return post<StartRunResponse>(`/api/committee/runs/${runId}/retro`, {})
}

export interface DecisionView extends PmDecisionEvent {
  status: CommitteeRunRow['status']
}
