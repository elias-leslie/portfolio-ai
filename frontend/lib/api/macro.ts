import { apiRequest } from './client'

export interface MacroSnapshot {
  snapshotDate: string
  deploymentScore: number
  zone: string
  coverage: number | null
  components: {
    vix: number | null
    term: number | null
    breadth: number | null
    credit: number | null
    putcall: number | null
    crowding: number | null
  }
  raw: {
    vixClose: number | null
    termSpreadBps: number | null
    breadthPct: number | null
    hySpread: number | null
    putCallRatio: number | null
    factorCrowdingCorr: number | null
  }
  weights: Record<string, number>
  componentQuality: Record<
    string,
    {
      status: 'fresh' | 'stale' | 'missing'
      asOf: string | null
      source: string
      cadence: string
      reason?: string | null
    }
  >
  computedAt: string | null
}

export interface MacroConditionEvidence {
  key: string
  label: string
  value: string
  detail: string
  tone: 'gain' | 'warning' | 'loss' | 'neutral' | string
  tooltip: string
  trend: MacroConditionTrend | null
}

export interface MacroConditionTrend {
  key: string
  label: string
  direction: 'improving' | 'worsening' | 'flat' | 'unavailable' | string
  tone: 'gain' | 'warning' | 'loss' | 'neutral' | string
  delta: number | null
  changeLabel: string
  summary: string
  windowDays: number
  latestDate: string | null
  priorDate: string | null
  reversal: boolean
  reversalLabel: string | null
  sparkline: number[]
}

export interface MacroConditionShift {
  key: string
  label: string
  detail: string
  tone: 'gain' | 'warning' | 'loss' | 'neutral' | string
  reversal: boolean
}

export interface MacroConditionsResponse {
  snapshotDate: string | null
  computedAt: string | null
  state: 'Calm' | 'Caution' | 'Elevated' | string
  stressScore: number | null
  deploymentScore: number | null
  macroZone: string | null
  coverage: number | null
  summary: string
  actionText: string
  whatMatters: string[]
  whatToDo: string[]
  watchItems: string[]
  trend: Record<string, MacroConditionTrend>
  marketShifts: MacroConditionShift[]
  flags: string[]
  alert: {
    active: boolean
    priority: 'high' | 'critical' | string | null
    reason: string | null
  }
  bondSignals: {
    asOf: string | null
    tenYearTwoYearBps: number | null
    tenYearThreeMonthBps: number | null
  }
  creditSignal: {
    latestDate: string | null
    latestValue: number | null
    priorDate: string | null
    priorValue: number | null
    changeBps: number | null
  }
  evidence: MacroConditionEvidence[]
}

export interface MacroBacktestRow {
  snapshotDate: string
  deploymentScore: number
  zone: string
  coverage: number
}

export interface MacroBacktestResponse {
  start: string
  end: string
  rows: MacroBacktestRow[]
  sanity: Record<string, string>
}

export interface MacroHistoryResponse {
  snapshots: MacroSnapshot[]
  weights: Record<string, number>
  zones: string[]
}

export interface MacroBacktestQueryArgs {
  start?: string
  end?: string
}

function buildMacroBacktestQuery(args: MacroBacktestQueryArgs = {}): string {
  const params = new URLSearchParams()
  if (args.start) params.set('start', args.start)
  if (args.end) params.set('end', args.end)
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function fetchMacroCurrent(): Promise<MacroSnapshot> {
  return apiRequest<MacroSnapshot>('/api/macro/current')
}

export function fetchMacroConditions(): Promise<MacroConditionsResponse> {
  return apiRequest<MacroConditionsResponse>('/api/macro/conditions')
}

export function fetchMacroHistory(days = 90): Promise<MacroHistoryResponse> {
  return apiRequest<MacroHistoryResponse>(`/api/macro/history?days=${days}`)
}

export function fetchMacroBacktest(
  args: MacroBacktestQueryArgs = {},
): Promise<MacroBacktestResponse> {
  return apiRequest<MacroBacktestResponse>(
    `/api/macro/backtest${buildMacroBacktestQuery(args)}`,
  )
}
