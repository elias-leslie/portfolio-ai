import { useQuery } from '@tanstack/react-query'
import {
  fetchMacroBacktest,
  fetchMacroConditions,
  fetchMacroConditionsHistory,
  fetchMacroCurrent,
  fetchMacroHistory,
  type MacroBacktestQueryArgs,
  type MacroBacktestResponse,
  type MacroConditionsHistoryResponse,
  type MacroConditionsResponse,
  type MacroHistoryResponse,
  type MacroSnapshot,
} from '@/lib/api/macro'

const ONE_MINUTE = 1000 * 60

export function useMacroCurrent() {
  return useQuery<MacroSnapshot>({
    queryKey: ['macro', 'current'],
    queryFn: fetchMacroCurrent,
    staleTime: 5 * ONE_MINUTE,
    refetchInterval: ONE_MINUTE,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    retry: 1,
  })
}

export function useMacroConditions() {
  return useQuery<MacroConditionsResponse>({
    queryKey: ['macro', 'conditions'],
    queryFn: fetchMacroConditions,
    staleTime: 5 * ONE_MINUTE,
    refetchInterval: ONE_MINUTE,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    retry: 1,
  })
}

export function useMacroHistory(days = 90) {
  return useQuery<MacroHistoryResponse>({
    queryKey: ['macro', 'history', days],
    queryFn: () => fetchMacroHistory(days),
    staleTime: 10 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useMacroConditionsHistory(days = 90) {
  return useQuery<MacroConditionsHistoryResponse>({
    queryKey: ['macro', 'conditions', 'history', days],
    queryFn: () => fetchMacroConditionsHistory(days),
    staleTime: 5 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}

export function useMacroBacktest(args: MacroBacktestQueryArgs = {}) {
  return useQuery<MacroBacktestResponse>({
    queryKey: ['macro', 'backtest', args],
    queryFn: () => fetchMacroBacktest(args),
    staleTime: 10 * ONE_MINUTE,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}
