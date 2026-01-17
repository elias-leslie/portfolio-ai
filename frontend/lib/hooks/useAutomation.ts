/**
 * React hooks for automation pipeline triggers
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import {
  getPipelineStatus,
  triggerAutoPaperTrade,
  triggerFullPipeline,
  triggerSignalGeneration,
  triggerStrategyResearch,
} from '@/lib/api/automation'

// Query keys
export const automationKeys = {
  all: ['automation'] as const,
  status: () => [...automationKeys.all, 'status'] as const,
}

/**
 * Hook to get pipeline status
 */
export function usePipelineStatus() {
  return useQuery({
    queryKey: automationKeys.status(),
    queryFn: getPipelineStatus,
    refetchInterval: 30000, // Refresh every 30 seconds
  })
}

/**
 * Hook to trigger strategy research
 */
export function useTriggerStrategyResearch() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      symbol,
      force,
    }: {
      symbol?: string
      force?: boolean
    } = {}) => triggerStrategyResearch(symbol, force),
    onMutate: () => {
      toast.loading('Starting strategy research...')
    },
    onSuccess: (data) => {
      toast.dismiss()
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: automationKeys.status() })
    },
    onError: (error) => {
      toast.dismiss()
      toast.error(
        `Failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}

/**
 * Hook to trigger signal generation
 */
export function useTriggerSignalGeneration() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => triggerSignalGeneration(),
    onMutate: () => {
      toast.loading('Generating signals...')
    },
    onSuccess: (data) => {
      toast.dismiss()
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: automationKeys.status() })
    },
    onError: (error) => {
      toast.dismiss()
      toast.error(
        `Failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}

/**
 * Hook to trigger auto paper trading
 */
export function useTriggerAutoPaperTrade() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (minStrength: number = 5) => triggerAutoPaperTrade(minStrength),
    onMutate: () => {
      toast.loading('Executing paper trades...')
    },
    onSuccess: (data) => {
      toast.dismiss()
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: automationKeys.status() })
    },
    onError: (error) => {
      toast.dismiss()
      toast.error(
        `Failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}

/**
 * Hook to trigger full pipeline
 */
export function useTriggerFullPipeline() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (skipResearch: boolean = false) =>
      triggerFullPipeline(skipResearch),
    onMutate: () => {
      toast.loading('Starting full pipeline...')
    },
    onSuccess: (data) => {
      toast.dismiss()
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: automationKeys.status() })
    },
    onError: (error) => {
      toast.dismiss()
      toast.error(
        `Failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}
