'use client'

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { HomeActionItem, HomeActionQueue } from '@/lib/api/home'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'
import { useAcknowledgeJennyNotification } from '@/lib/hooks/usePortfolio'
import { useTransitionSymbolWorkflow } from '@/lib/hooks/useSymbolIntelligence'

interface HomeActionQueueContextValue {
  data: HomeActionQueue | undefined
  visibleActions: HomeActionItem[]
  isLoading: boolean
  isFetching: boolean
  isExecuting: boolean
  error: Error | null
  refetchActions: () => void
  executeAction: (action: HomeActionItem) => void
}

const HomeActionQueueContext =
  createContext<HomeActionQueueContextValue | null>(null)

export function HomeActionQueueProvider({
  children,
  enabled = true,
}: {
  children: ReactNode
  enabled?: boolean
}) {
  const { data, isLoading, isFetching, error, refetch } = useHomeActionQueue({
    enabled,
  })
  const acknowledgeNotification = useAcknowledgeJennyNotification()
  const transitionWorkflow = useTransitionSymbolWorkflow()
  const actions = useMemo(() => data?.actions ?? [], [data?.actions])
  const [clearedActionIds, setClearedActionIds] = useState<Set<string>>(
    () => new Set(),
  )

  useEffect(() => {
    const actionIds = new Set(actions.map((action) => action.id))
    setClearedActionIds((current) => {
      const next = new Set([...current].filter((id) => actionIds.has(id)))
      return next.size === current.size ? current : next
    })
  }, [actions])

  const executeAction = useCallback(
    (action: HomeActionItem) => {
      const execution = action.execution
      if (!execution) {
        return
      }

      const clearAction = () => {
        setClearedActionIds((current) => new Set(current).add(action.id))
      }

      if (
        execution.kind === 'acknowledge_notification' &&
        execution.notificationId
      ) {
        acknowledgeNotification.mutate(execution.notificationId, {
          onSuccess: clearAction,
        })
        return
      }

      if (
        execution.kind === 'workflow_transition' &&
        execution.symbol &&
        execution.stage
      ) {
        transitionWorkflow.mutate(
          {
            symbol: execution.symbol,
            stage: execution.stage,
          },
          { onSuccess: clearAction },
        )
      }
    },
    [acknowledgeNotification, transitionWorkflow],
  )

  const value = useMemo<HomeActionQueueContextValue>(
    () => ({
      data,
      visibleActions: actions.filter(
        (action) => !clearedActionIds.has(action.id),
      ),
      isLoading,
      isFetching,
      isExecuting:
        acknowledgeNotification.isPending || transitionWorkflow.isPending,
      error: error ?? null,
      refetchActions: () => {
        void refetch()
      },
      executeAction,
    }),
    [
      acknowledgeNotification.isPending,
      actions,
      clearedActionIds,
      data,
      error,
      executeAction,
      isFetching,
      isLoading,
      refetch,
      transitionWorkflow.isPending,
    ],
  )

  return (
    <HomeActionQueueContext.Provider value={value}>
      {children}
    </HomeActionQueueContext.Provider>
  )
}

export function useHomeActionQueueState(): HomeActionQueueContextValue {
  const context = useContext(HomeActionQueueContext)
  if (!context) {
    throw new Error(
      'useHomeActionQueueState must be used within HomeActionQueueProvider',
    )
  }
  return context
}
