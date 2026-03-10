import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  fetchSymbolIntelligence,
  fetchSymbolWorkflow,
  recordSymbolWorkflowOutcome,
  transitionSymbolWorkflow,
} from '@/lib/api/symbols'

export function useSymbolIntelligence(symbol: string) {
  return useQuery({
    queryKey: ['symbol-intelligence', symbol],
    queryFn: () => fetchSymbolIntelligence(symbol),
    enabled: symbol.trim().length > 0,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60 * 5,
  })
}

export function useSymbolWorkflow(symbol: string) {
  return useQuery({
    queryKey: ['symbol-workflow', symbol],
    queryFn: () => fetchSymbolWorkflow(symbol),
    enabled: symbol.trim().length > 0,
    staleTime: 1000 * 30,
  })
}

export function useTransitionSymbolWorkflow(defaultSymbol?: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { symbol?: string; stage: string; note?: string }) =>
      transitionSymbolWorkflow(payload.symbol ?? defaultSymbol ?? '', {
        stage: payload.stage,
        note: payload.note,
      }),
    onSuccess: (_result, variables) => {
      const symbol = variables.symbol ?? defaultSymbol ?? ''
      queryClient.invalidateQueries({ queryKey: ['symbol-workflow', symbol] })
      queryClient.invalidateQueries({ queryKey: ['thesis', symbol] })
      queryClient.invalidateQueries({ queryKey: ['symbol-intelligence', symbol] })
      queryClient.invalidateQueries({ queryKey: ['home'] })
      toast.success('Workflow updated.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to update workflow')
    },
  })
}

export function useRecordSymbolWorkflowOutcome(defaultSymbol?: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: {
      symbol?: string
      action: string
      note?: string
      jennyVerdict?: string | null
      managementAction?: string | null
    }) =>
      recordSymbolWorkflowOutcome(payload.symbol ?? defaultSymbol ?? '', {
        action: payload.action,
        note: payload.note,
        jennyVerdict: payload.jennyVerdict,
        managementAction: payload.managementAction,
      }),
    onSuccess: (_result, variables) => {
      const symbol = variables.symbol ?? defaultSymbol ?? ''
      queryClient.invalidateQueries({ queryKey: ['symbol-workflow', symbol] })
      queryClient.invalidateQueries({ queryKey: ['symbol-intelligence', symbol] })
      queryClient.invalidateQueries({ queryKey: ['portfolio', 'jenny'] })
      queryClient.invalidateQueries({ queryKey: ['home'] })
      toast.success('Outcome captured.')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to capture outcome')
    },
  })
}
