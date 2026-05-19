/**
 * React Query hooks for Preferences API
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchPreferences,
  fetchScannerFanoutSettings,
  type PreferencesUpdate,
  type ScannerFanoutSettings,
  updatePreferences,
  updateScannerFanoutSettings,
} from '../api/preferences'

/**
 * Hook to fetch user's risk tolerance and trade preferences
 */
export function usePreferences() {
  return useQuery({
    queryKey: ['preferences'],
    queryFn: fetchPreferences,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

/**
 * Hook to update user preferences
 */
export function useUpdatePreferences() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: PreferencesUpdate) => updatePreferences(data),
    onSuccess: () => {
      // Invalidate preferences query to refetch
      queryClient.invalidateQueries({ queryKey: ['preferences'] })
      queryClient.invalidateQueries({
        queryKey: ['home'],
        refetchType: 'active',
      })
    },
  })
}

const SCANNER_FANOUT_QUERY_KEY = ['preferences', 'scanner-fanout'] as const

export function useScannerFanoutSettings() {
  return useQuery({
    queryKey: SCANNER_FANOUT_QUERY_KEY,
    queryFn: fetchScannerFanoutSettings,
    staleTime: 1000 * 60 * 10,
  })
}

export function useUpdateScannerFanoutSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ScannerFanoutSettings) =>
      updateScannerFanoutSettings(data),
    onMutate: async (next) => {
      await queryClient.cancelQueries({ queryKey: SCANNER_FANOUT_QUERY_KEY })
      const previous = queryClient.getQueryData<ScannerFanoutSettings>(
        SCANNER_FANOUT_QUERY_KEY,
      )
      queryClient.setQueryData(SCANNER_FANOUT_QUERY_KEY, next)
      return { previous }
    },
    onError: (_err, _next, context) => {
      if (context?.previous) {
        queryClient.setQueryData(SCANNER_FANOUT_QUERY_KEY, context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: SCANNER_FANOUT_QUERY_KEY })
    },
  })
}
