/**
 * React Query hooks for Preferences API
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchPreferences,
  type PreferencesUpdate,
  updatePreferences,
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
