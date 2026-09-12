'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useRef } from 'react'
import { Button } from '@/components/ui/button'

export type HouseholdIdentity = {
  member_id: string | null
  display_name: string
  access: 'adult' | 'capture_only' | 'local_operator'
}

const localIdentity: HouseholdIdentity = {
  member_id: null,
  display_name: 'Local workspace',
  access: 'local_operator',
}
const IdentityContext = createContext<HouseholdIdentity>(localIdentity)

export function useHouseholdIdentity() {
  return useContext(IdentityContext)
}
export function identityStorageKey(identity: HouseholdIdentity, key: string) {
  return `portfolio-ai:member:${identity.member_id ?? 'local'}:${key}`
}

export function HouseholdIdentityProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const queryClient = useQueryClient()
  const activeMember = useRef<string | null>(null)
  const identity = useQuery({
    queryKey: ['household-identity'],
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    queryFn: async (): Promise<HouseholdIdentity> => {
      const response = await fetch('/api/identity', { cache: 'no-store' })
      if (!response.ok)
        throw new Error(
          'Your sign-in could not be verified. Retry or sign in again.',
        )
      const value: unknown = await response.json()
      if (
        typeof value !== 'object' ||
        value === null ||
        !('access' in value) ||
        !('member_id' in value) ||
        !('display_name' in value) ||
        typeof value.display_name !== 'string' ||
        (value.member_id !== null && typeof value.member_id !== 'string') ||
        (value.access !== 'adult' &&
          value.access !== 'capture_only' &&
          value.access !== 'local_operator')
      )
        throw new Error('Invalid household identity.')
      const member = value.member_id ?? 'local'
      if (activeMember.current !== member) {
        let previous: string | null = null
        try {
          previous = localStorage.getItem('portfolio-ai:last-signed-member')
        } catch {
          /* Storage may be disabled. */
        }
        if (
          value.access === 'capture_only' ||
          (value.access === 'adult' && previous && previous !== member)
        ) {
          const registration =
            'serviceWorker' in navigator
              ? await navigator.serviceWorker.getRegistration()
              : undefined
          const subscription = await registration?.pushManager.getSubscription()
          if (subscription && !(await subscription.unsubscribe()))
            throw new Error(
              'This browser’s previous alerts could not be disconnected. Retry the sign-in check.',
            )
          const notifications = await registration?.getNotifications()
          for (const notification of notifications ?? []) notification.close()
        }
        try {
          localStorage.setItem('portfolio-ai:last-signed-member', member)
        } catch {
          /* Identity remains server verified. */
        }
        await queryClient.cancelQueries({
          predicate: (query) => query.queryKey[0] !== 'household-identity',
        })
        queryClient.removeQueries({
          predicate: (query) => query.queryKey[0] !== 'household-identity',
        })
        activeMember.current = member
      }
      return {
        member_id: value.member_id,
        display_name: value.display_name,
        access: value.access,
      }
    },
  })
  if (identity.isPending)
    return (
      <p className="p-6 text-text-muted" role="status">
        Checking household access…
      </p>
    )
  if (identity.isError)
    return (
      <div className="space-y-4 p-6">
        <p role="alert">{identity.error.message}</p>
        <Button onClick={() => void identity.refetch()}>
          Retry sign-in check
        </Button>
        <a className="ml-4 underline" href="/cdn-cgi/access/logout">
          Sign in again
        </a>
      </div>
    )
  return (
    <IdentityContext.Provider
      key={identity.data.member_id ?? 'local'}
      value={identity.data}
    >
      {children}
    </IdentityContext.Provider>
  )
}
