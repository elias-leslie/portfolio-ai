import { apiRequest } from './client'

export interface ScannerRun {
  runId: string
  runDate: string
  gateZone: string
  gateScore: number | null
  universeSize: number
  scoredCount: number
  skipReason: string | null
  startedAt: string | null
  completedAt: string | null
}

export interface ScannerScore {
  symbol: string
  rank: number
  compositePct: number | null
  factorCoverage: number | null
  factors: Record<string, number | null>
  percentiles: Record<string, number | null>
}

export interface ScannerLatest {
  run: ScannerRun
  scores: ScannerScore[]
  factorOrder: string[]
}

export function fetchScannerLatest(limit = 50): Promise<ScannerLatest> {
  return apiRequest<ScannerLatest>(`/api/scanner/latest?limit=${limit}`)
}
