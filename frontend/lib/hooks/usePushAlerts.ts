/**
 * Query/mutation surface for the household push channel (plan §7 3.6).
 *
 * The device's own state — supported, permitted, already subscribed — is read
 * from the browser rather than the server, because the server only knows which
 * endpoints exist, not whether *this* handset is one of them.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  deletePushSubscription,
  fetchPushSubscriptions,
  type PushSubscriptionList,
  registerPushSubscription,
  sendTestPush,
  unsubscribePushEndpoint,
} from '@/lib/api/push'
import {
  currentEndpoint,
  type PushPermission,
  type PushSupport,
  pushPermission,
  pushSupport,
  subscribeThisDevice,
  unsubscribeThisDevice,
} from '@/lib/push/subscription'

const PUSH_SUBSCRIPTIONS_KEY = ['household', 'push', 'subscriptions']

export function usePushSubscriptions() {
  return useQuery<PushSubscriptionList>({
    queryKey: PUSH_SUBSCRIPTIONS_KEY,
    queryFn: fetchPushSubscriptions,
  })
}

export interface DevicePushState {
  support: PushSupport
  permission: PushPermission
  endpoint: string | null
  isLoading: boolean
}

/** What this browser can do and has already done. */
export function useDevicePushState(): DevicePushState {
  const [state, setState] = useState<DevicePushState>({
    support: 'unsupported',
    permission: 'default',
    endpoint: null,
    isLoading: true,
  })

  useEffect(() => {
    let cancelled = false
    const support = pushSupport()
    if (support !== 'supported') {
      setState({
        support,
        permission: pushPermission(),
        endpoint: null,
        isLoading: false,
      })
      return
    }
    currentEndpoint()
      .then((endpoint) => {
        if (cancelled) return
        setState({
          support,
          permission: pushPermission(),
          endpoint,
          isLoading: false,
        })
      })
      .catch(() => {
        if (cancelled) return
        setState({
          support,
          permission: pushPermission(),
          endpoint: null,
          isLoading: false,
        })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}

export function useEnablePushOnThisDevice() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      publicKey,
      householdMemberId,
    }: {
      publicKey: string
      householdMemberId: string | null
    }) => {
      const registration = await subscribeThisDevice(
        publicKey,
        householdMemberId,
      )
      return registerPushSubscription(registration)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PUSH_SUBSCRIPTIONS_KEY })
      toast.success('This phone will get budget alerts.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Could not turn on alerts',
      )
    },
  })
}

export function useDisablePushOnThisDevice() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const endpoint = await unsubscribeThisDevice()
      // The browser's subscription is gone either way; the row only matters if
      // there was an endpoint to name it by.
      if (endpoint) {
        await unsubscribePushEndpoint(endpoint)
      }
      return endpoint
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PUSH_SUBSCRIPTIONS_KEY })
      toast.success('Alerts are off on this phone.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Could not turn off alerts',
      )
    },
  })
}

export function useRemovePushSubscription() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (subscriptionId: string) =>
      deletePushSubscription(subscriptionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PUSH_SUBSCRIPTIONS_KEY })
      toast.success('Device removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Could not remove the device',
      )
    },
  })
}

export function useSendTestPush() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (subscriptionId?: string | null) =>
      sendTestPush(subscriptionId ?? null),
    onSuccess: async (delivery) => {
      await queryClient.invalidateQueries({ queryKey: PUSH_SUBSCRIPTIONS_KEY })
      if (delivery.delivered > 0) {
        toast.success(
          `Sent to ${delivery.delivered} device${delivery.delivered === 1 ? '' : 's'}.`,
        )
        return
      }
      if (delivery.expired > 0) {
        toast.error('That device is no longer reachable and was removed.')
        return
      }
      toast.error('No device took the test push.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Could not send a test push',
      )
    },
  })
}
