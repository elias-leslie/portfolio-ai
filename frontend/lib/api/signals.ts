import { apiRequest } from './client'

// ── /api/signals/blended ─────────────────────────────────────────────────────

export interface BlendedCommittee {
  runId: string
  action: string | null
  confidence: number | null
  pmScore: number
  completedAt: string | null
  source: string | null
  scannerRank: number | null
}

export interface BlendedRow {
  symbol: string
  scannerRank: number
  blendedRank: number
  deltaRank: number
  flagged: boolean
  scannerCompositePct: number
  blendedScore: number
  committee: BlendedCommittee | null
}

export interface ScannerRunMeta {
  runId: string
  runDate: string
  gateZone: string
  gateScore: number | null
  universeSize: number
  scoredCount: number
  skipReason: string | null
}

export interface BlendWeights {
  scanner: number
  committee: number
}

export interface BlendedResponse {
  run: ScannerRunMeta
  weights: BlendWeights
  rows: BlendedRow[]
}

export interface RankDeltasResponse {
  run: ScannerRunMeta
  weights: BlendWeights
  threshold: number
  rows: BlendedRow[]
}

// ── /api/signals/symbol/{ticker} ─────────────────────────────────────────────

export interface MacroContext {
  snapshotDate: string | null
  zone: string | null
  deploymentScore: number | null
  components: {
    vix: number | null
    term: number | null
    breadth: number | null
    credit: number | null
    putcall: number | null
    crowding: number | null
  }
}

export interface SymbolScannerRow {
  runDate: string
  gateZone: string
  rank: number
  compositePct: number | null
  factorCoverage: number | null
  percentiles: Record<string, number | null>
}

export interface SymbolSignalsResponse {
  symbol: string
  macro: MacroContext
  scanner: SymbolScannerRow[]
  committee: BlendedCommittee | null
}

// ── fetchers ─────────────────────────────────────────────────────────────────

export interface BlendedQueryArgs {
  limit?: number
  weightScanner?: number
  weightCommittee?: number
}

function buildBlendedQuery(args: BlendedQueryArgs = {}): string {
  const params = new URLSearchParams()
  if (args.limit !== undefined) params.set('limit', String(args.limit))
  if (args.weightScanner !== undefined)
    params.set('weight_scanner', args.weightScanner.toFixed(4))
  if (args.weightCommittee !== undefined)
    params.set('weight_committee', args.weightCommittee.toFixed(4))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function fetchBlendedSignals(
  args: BlendedQueryArgs = {},
): Promise<BlendedResponse> {
  return apiRequest<BlendedResponse>(
    `/api/signals/blended${buildBlendedQuery(args)}`,
  )
}

export function fetchRankDeltas(
  args: BlendedQueryArgs = {},
): Promise<RankDeltasResponse> {
  return apiRequest<RankDeltasResponse>(
    `/api/signals/rank-deltas${buildBlendedQuery(args)}`,
  )
}

export function fetchSymbolSignals(
  ticker: string,
  days = 30,
): Promise<SymbolSignalsResponse> {
  return apiRequest<SymbolSignalsResponse>(
    `/api/signals/symbol/${encodeURIComponent(ticker)}?days=${days}`,
  )
}
