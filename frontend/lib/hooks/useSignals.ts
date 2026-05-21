import { useQuery } from '@tanstack/react-query'
import {
  fetchMacroBacktest,
  fetchMacroCurrent,
  type MacroBacktestQueryArgs,
  type MacroBacktestResponse,
  type MacroSnapshot,
} from '@/lib/api/macro'
import { fetchScannerLatest, type ScannerLatest } from '@/lib/api/scanner'
import {
  type BlendedQueryArgs,
  type BlendedResponse,
  fetchBlendedSignals,
  fetchRankDeltas,
  fetchSymbolSignals,
  type RankDeltasResponse,
  type SymbolSignalsResponse,
} from '@/lib/api/signals'

const ONE_MINUTE = 1000 * 60

export function useMacroCurrent() {
  return useQuery<MacroSnapshot>({
    queryKey: ['signals', 'macro', 'current'],
    queryFn: fetchMacroCurrent,
    staleTime: 5 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useMacroBacktest(args: MacroBacktestQueryArgs = {}) {
  return useQuery<MacroBacktestResponse>({
    queryKey: ['signals', 'macro', 'backtest', args],
    queryFn: () => fetchMacroBacktest(args),
    staleTime: 10 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useScannerLatest(limit = 50) {
  return useQuery<ScannerLatest>({
    queryKey: ['signals', 'scanner', 'latest', limit],
    queryFn: () => fetchScannerLatest(limit),
    staleTime: 5 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useBlendedSignals(args: BlendedQueryArgs = {}) {
  return useQuery<BlendedResponse>({
    queryKey: ['signals', 'blended', args],
    queryFn: () => fetchBlendedSignals(args),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useRankDeltas(args: BlendedQueryArgs = {}) {
  return useQuery<RankDeltasResponse>({
    queryKey: ['signals', 'rank-deltas', args],
    queryFn: () => fetchRankDeltas(args),
    staleTime: 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useSymbolSignals(ticker: string, days = 30) {
  return useQuery<SymbolSignalsResponse>({
    queryKey: ['signals', 'symbol', ticker, days],
    queryFn: () => fetchSymbolSignals(ticker, days),
    enabled: Boolean(ticker),
    staleTime: 5 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}
