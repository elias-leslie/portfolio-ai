/**
 * React Query hooks for Portfolio API
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  type AddPositionRequest,
  acknowledgeJennyNotification,
  addPosition,
  type CreateAccountRequest,
  chatWithJenny,
  createAccount,
  deleteAccount,
  deletePosition,
  fetchAccounts,
  fetchAnalytics,
  fetchJennyDashboard,
  fetchPortfolio,
  runJennyRoutine,
  updatePosition,
} from '../api/portfolio'

/**
 * Hook to fetch portfolio positions with current values
 * Refreshes on a short cadence so live-quoted holdings keep moving during the day.
 */
export function usePortfolio(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
    enabled: options?.enabled !== false, // Default to true
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch portfolio analytics
 * Refreshes on the same short cadence as holdings so concentration and gain stay aligned.
 */
export function usePortfolioAnalytics() {
  return useQuery({
    queryKey: ['portfolio', 'analytics'],
    queryFn: fetchAnalytics,
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
    refetchOnWindowFocus: true,
  })
}

export function useJennyDashboard() {
  return useQuery({
    queryKey: ['portfolio', 'jenny'],
    queryFn: fetchJennyDashboard,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60 * 5,
  })
}

export function useJennyChat() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: chatWithJenny,
    onSuccess: (response) => {
      queryClient.invalidateQueries({
        queryKey: ['household'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['accounts'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['portfolio', 'analytics'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['portfolio', 'jenny'],
        refetchType: 'active',
      })
      if (response.resolvedQuestions.length > 0) {
        toast.success(
          `Jenny reconciled ${response.resolvedQuestions.length} question${response.resolvedQuestions.length === 1 ? '' : 's'}.`,
        )
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to chat with Jenny',
      )
    },
  })
}

/**
 * Hook to fetch all accounts
 */
export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: fetchAccounts,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Hook to create a new account
 */
export function useCreateAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateAccountRequest) => createAccount(data),
    onSuccess: () => {
      // Invalidate and refetch accounts and portfolio queries
      queryClient.invalidateQueries({
        queryKey: ['accounts'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['household'],
        refetchType: 'active',
      })
    },
  })
}

/**
 * Hook to delete an account
 */
export function useDeleteAccount() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (accountId: string) => deleteAccount(accountId),
    onSuccess: () => {
      // Invalidate and refetch all portfolio-related queries
      queryClient.invalidateQueries({
        queryKey: ['accounts'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['household'],
        refetchType: 'active',
      })
    },
  })
}

/**
 * Hook to add or update a position
 */
export function useAddPosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: AddPositionRequest) => {
      const promise = addPosition(data)
      const positionTypeLabel = data.positionType === 'paper' ? 'paper' : 'live'
      toast.promise(promise, {
        loading: `Adding ${data.symbol.toUpperCase()} position...`,
        success: (position) =>
          `${position.symbol} ${positionTypeLabel} position added (${data.shares} shares @ $${data.costBasis.toFixed(2)})`,
        error: (error) => {
          const errorMsg =
            error instanceof Error ? error.message : 'Failed to add position'
          return `Failed to add ${data.symbol.toUpperCase()}: ${errorMsg}`
        },
      })
      return promise
    },
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['household'],
        refetchType: 'active',
      })
    },
  })
}

/**
 * Hook to update a position
 */
export function useUpdatePosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      positionId,
      data,
    }: {
      positionId: string
      data: AddPositionRequest
    }) => {
      const promise = updatePosition(positionId, data)
      toast.promise(promise, {
        loading: `Updating ${data.symbol.toUpperCase()} position...`,
        success: (position) =>
          `${position.symbol} position updated (${data.shares} shares @ $${data.costBasis.toFixed(2)})`,
        error: (error) => {
          const errorMsg =
            error instanceof Error ? error.message : 'Failed to update position'
          return `Failed to update ${data.symbol.toUpperCase()}: ${errorMsg}`
        },
      })
      return promise
    },
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['household'],
        refetchType: 'active',
      })
    },
  })
}

/**
 * Hook to delete a position
 */
export function useDeletePosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (positionId: string) => {
      // Get position details for toast message before deleting
      const portfolioData = queryClient.getQueryData<{
        positions: Array<{ id: string; symbol: string; shares: number }>
      }>(['portfolio'])
      const position = portfolioData?.positions.find((p) => p.id === positionId)
      const symbol = position?.symbol || 'position'

      const promise = deletePosition(positionId)
      toast.promise(promise, {
        loading: `Deleting ${symbol} position...`,
        success: `${symbol} position deleted`,
        error: (error) => {
          const errorMsg =
            error instanceof Error ? error.message : 'Failed to delete position'
          return `Failed to delete ${symbol}: ${errorMsg}`
        },
      })
      return promise
    },
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['household'],
        refetchType: 'active',
      })
    },
  })
}

export function useRunJennyRoutine() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: runJennyRoutine,
    onSuccess: (result) => {
      queryClient.setQueryData(['portfolio', 'jenny'], result.dashboard)
      queryClient.invalidateQueries({
        queryKey: ['portfolio'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['home'],
        refetchType: 'active',
      })
      toast.success('Jenny finished a new review.')
    },
    onError: (error) => {
      const errorMsg =
        error instanceof Error ? error.message : 'Jenny review failed'
      toast.error(errorMsg)
    },
  })
}

export function useAcknowledgeJennyNotification() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: acknowledgeJennyNotification,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['portfolio', 'jenny'],
        refetchType: 'active',
      })
      queryClient.invalidateQueries({
        queryKey: ['home'],
        refetchType: 'active',
      })
    },
  })
}
