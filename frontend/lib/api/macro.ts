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
  computedAt: string | null
}

export function fetchMacroCurrent(): Promise<MacroSnapshot> {
  return apiRequest<MacroSnapshot>('/api/macro/current')
}
