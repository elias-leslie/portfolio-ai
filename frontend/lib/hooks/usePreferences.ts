/**
 * React Query hooks for Preferences API
 */

import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  fetchPreferences,
  type PreferencesUpdate,
  updatePreferences,
} from '../api/preferences'

/** One cache entry and stale time for every reader of `['preferences']`. */
export const preferencesQueryOptions = queryOptions({
  queryKey: ['preferences'],
  queryFn: fetchPreferences,
  staleTime: 1000 * 60 * 5,
})

/**
 * Hook to fetch user's risk tolerance and trade preferences
 */
export function usePreferences() {
  return useQuery(preferencesQueryOptions)
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
      queryClient.invalidateQueries({
        queryKey: preferencesQueryOptions.queryKey,
      })
      queryClient.invalidateQueries({
        queryKey: ['home'],
        refetchType: 'active',
      })
    },
  })
}
