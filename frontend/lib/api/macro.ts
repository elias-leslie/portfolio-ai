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
  degraded: boolean
  staleComponents: string[]
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

export type OvernightDirection =
  | 'risk_on'
  | 'risk_off'
  | 'neutral'
  | 'unavailable'
  | string
export type OvernightSignalDirection = OvernightDirection | 'closed'

export interface OvernightLeanSignal {
  key: string
  label: string
  symbol: string
  changePct: number | null
  direction: OvernightSignalDirection
  magnitude: 'flat' | 'mild' | 'strong' | 'unavailable' | string
  live: boolean
  note: string | null
}

export interface OvernightLean {
  applies: boolean
  session: 'overnight' | 'weekend' | 'halt' | 'rth' | string
  sessionLabel: string
  direction: OvernightDirection
  confidence: number
  liveCount: number
  headline: string
  stressScore: number | null
  droveCaution: boolean
  note: string | null
  asOf: string | null
  signals: OvernightLeanSignal[]
}

export interface MacroConditionTrigger {
  key: string
  label: string
  current: number | null
  currentDisplay: string
  trigger: number
  triggerDisplay: string
  baseline: number
  watch: number
  direction: 'above' | 'below' | string
  unit: string
  progress: number | null
  fired: boolean
  tone: 'gain' | 'warning' | 'loss' | 'neutral' | string
  note: string
}

export interface MacroConditionsResponse {
  snapshotDate: string | null
  computedAt: string | null
  state: 'Calm' | 'Caution' | 'Elevated' | string
  stressScore: number | null
  macroStressScore: number | null
  tapePressureScore: number | null
  overallCautionScore: number | null
  overallRead: 'normal' | 'selective' | 'defensive' | 'unavailable' | string
  primaryDriver: 'macro' | 'tape' | 'both' | 'none' | 'data_limited' | string
  driverDetail: string
  deploymentScore: number | null
  macroZone: string | null
  coverage: number | null
  tapeAvailable: boolean
  tapeState: 'live' | 'held' | 'unavailable' | string | null
  tapeAsOf: string | null
  marketSession: string | null
  tapeStatus: string | null
  nextCatalyst: {
    eventType: string
    eventDate: string
    eventTime: string | null
    title: string
    impactScore: number
  } | null
  overnightLean: OvernightLean | null
  summary: string
  actionText: string
  driving: {
    headline: string
    tone: 'risk_off' | 'caution' | 'constructive' | 'neutral' | string
  } | null
  whatMatters: string[]
  whatToDo: string[]
  watchItems: string[]
  triggers: MacroConditionTrigger[]
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

export interface MacroConditionsHistoryPoint {
  recordedAt: string
  snapshotDate: string
  deploymentScore: number | null
  macroStress: number | null
  tapePressure: number | null
  overallCaution: number | null
  overallRead: string | null
  primaryDriver: string | null
  state: string | null
  tapeAvailable: boolean
  tapeState: 'live' | 'held' | 'unavailable' | string | null
  marketSession: string | null
}

export interface MacroConditionsHistoryResponse {
  points: MacroConditionsHistoryPoint[]
  severeThreshold: number
  selectiveThreshold: number
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

export function fetchMacroConditionsHistory(
  days = 90,
): Promise<MacroConditionsHistoryResponse> {
  return apiRequest<MacroConditionsHistoryResponse>(
    `/api/macro/conditions/history?days=${days}`,
  )
}

export function fetchMacroBacktest(
  args: MacroBacktestQueryArgs = {},
): Promise<MacroBacktestResponse> {
  return apiRequest<MacroBacktestResponse>(
    `/api/macro/backtest${buildMacroBacktestQuery(args)}`,
  )
}
