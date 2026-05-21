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

export function fetchMacroBacktest(
  args: MacroBacktestQueryArgs = {},
): Promise<MacroBacktestResponse> {
  return apiRequest<MacroBacktestResponse>(
    `/api/macro/backtest${buildMacroBacktestQuery(args)}`,
  )
}
