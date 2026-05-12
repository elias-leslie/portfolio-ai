import { getApiBaseUrl } from '@/lib/api-config'
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

// Committee endpoints stream and return events that must preserve their
// exact snake_case wire shape — the reducer keys off `agent_slug`,
// `content_md`, `qty_pct`, `tokens_total`, etc. The shared api client
// recursively camelCases every response, which would silently break the
// snapshot/replay path while the live SSE path (raw EventSource) stays
// snake_case. We use a thin raw fetch here to keep both paths identical.

async function rawJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = path.startsWith('http') ? '' : getApiBaseUrl()
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${base}${path}`, {
    cache: 'no-store',
    ...init,
    headers,
  })
  if (!response.ok) {
    let message = `HTTP ${response.status}: ${response.statusText}`
    try {
      const data = (await response.json()) as { detail?: string }
      if (data?.detail) message = data.detail
    } catch {
      // keep default message
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function startCommitteeRun(input: {
  symbol: string
  parentRunId?: string
}): Promise<StartRunResponse> {
  return rawJson<StartRunResponse>('/api/committee/runs', {
    method: 'POST',
    body: JSON.stringify({
      symbol: input.symbol,
      parent_run_id: input.parentRunId ?? null,
    }),
  })
}

export async function fetchCommitteeRun(
  runId: string,
): Promise<CommitteeRunSnapshot> {
  return rawJson<CommitteeRunSnapshot>(`/api/committee/runs/${runId}`)
}

export async function approveCommitteeRun(
  runId: string,
): Promise<ApproveResponse> {
  return rawJson<ApproveResponse>(`/api/committee/runs/${runId}/approve`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function submitCommitteeFeedback(
  runId: string,
  userInput: string,
): Promise<{ input_id: string; round: number }> {
  return rawJson<{ input_id: string; round: number }>(
    `/api/committee/runs/${runId}/feedback`,
    {
      method: 'POST',
      body: JSON.stringify({ user_input: userInput }),
    },
  )
}

export async function pauseCommitteeRun(
  runId: string,
): Promise<{ paused: boolean }> {
  return rawJson<{ paused: boolean }>(`/api/committee/runs/${runId}/pause`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function resumeCommitteeRun(
  runId: string,
): Promise<{ resumed: boolean }> {
  return rawJson<{ resumed: boolean }>(`/api/committee/runs/${runId}/resume`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function abortCommitteeRun(
  runId: string,
): Promise<{ aborted: boolean }> {
  return rawJson<{ aborted: boolean }>(`/api/committee/runs/${runId}/abort`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function startRetroRun(runId: string): Promise<StartRunResponse> {
  return rawJson<StartRunResponse>(`/api/committee/runs/${runId}/retro`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export interface DecisionView extends PmDecisionEvent {
  status: CommitteeRunRow['status']
}

export interface CommitteeRunListItem {
  id: string
  symbol: string
  status: CommitteeRunRow['status']
  decision_action: string | null
  decision_pct_portfolio: number | null
  confidence: number | null
  parent_run_id: string | null
  started_at: string | null
  completed_at: string | null
}

export async function fetchCommitteeRuns(
  limit = 20,
): Promise<{ runs: CommitteeRunListItem[] }> {
  return rawJson<{ runs: CommitteeRunListItem[] }>(
    `/api/committee/runs?limit=${encodeURIComponent(limit)}`,
  )
}
