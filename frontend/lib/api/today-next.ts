import { apiRequest } from './client'

export interface MacroGate {
  status: string
  score: number
  label: string
  fearGreedScore: number
  fearGreedLabel: string
  vix?: number | null
  asOf?: string | null
  signals: Array<{
    label: string
    value: string
    score?: number | null
  }>
}

export interface ScannerCandidate {
  symbol: string
  signalType?: string | null
  signalStrength?: number | null
  score?: number | null
  headline?: string | null
  style?: string | null
  riskLevel?: string | null
  entryPrice?: number | null
  stopLoss?: number | null
  profitTarget?: number | null
}

export interface CommitteeCandidate {
  symbol: string
  thesisAction?: string | null
  thesisStatus?: string | null
  expectedReturnPct?: number | null
  crossValidationScore?: number | null
  committeeRunId?: string | null
  committeeStatus?: string | null
  committeeAction?: string | null
  committeeConfidence?: number | null
  updatedAt?: string | null
}

export interface TodayNextResponse {
  macroGate: MacroGate
  scanner: ScannerCandidate[]
  committee: CommitteeCandidate[]
}

export function fetchTodayNext(): Promise<TodayNextResponse> {
  return apiRequest<TodayNextResponse>('/api/today-next')
}
