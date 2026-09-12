'use client'

import { useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { JennyChatWidget } from '@/components/chat/JennyChatWidget'
import { Navigation } from '@/components/Navigation'
import { useHouseholdIdentity } from '@/components/providers/HouseholdIdentityProvider'
import { Button } from '@/components/ui/button'

export function HouseholdShell({ children }: { children: React.ReactNode }) {
  const identity = useHouseholdIdentity()
  const path = usePathname()
  const router = useRouter()
  const queryClient = useQueryClient()
  const [signingOut, setSigningOut] = useState(false)
  const [error, setError] = useState('')
  const child = identity.access === 'capture_only'
  useEffect(() => {
    if (child && path !== '/capture') router.replace('/capture')
  }, [child, path, router])
  async function signOut() {
    setSigningOut(true)
    setError('')
    try {
      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.getRegistration()
        const subscription = await registration?.pushManager.getSubscription()
        if (subscription) {
          if (!child)
            await fetch('/api/household/push/unsubscribe', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ endpoint: subscription.endpoint }),
            })
          if (!(await subscription.unsubscribe()))
            throw new Error(
              'Could not turn off this browser’s alerts. Please retry before signing out.',
            )
        }
      }
      queryClient.clear()
      const prefix = `portfolio-ai:member:${identity.member_id}:jenny-chat:`
      for (const key of Object.keys(localStorage))
        if (key.startsWith(prefix)) localStorage.removeItem(key)
      sessionStorage.removeItem('portfolio-ai:active-member')
      window.location.assign('/cdn-cgi/access/logout')
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Sign-out failed. Please retry.',
      )
      setSigningOut(false)
    }
  }
  return (
    <>
      {child ? (
        <header className="flex items-center justify-between border-b border-border p-4">
          <Link href="/capture" className="font-semibold">
            Family capture
          </Link>
          <span>{identity.display_name}</span>
        </header>
      ) : (
        <Navigation />
      )}
      <div className="flex items-center justify-end gap-3 border-b border-border/30 px-4 py-1 text-xs text-text-muted">
        {!child && (
          <Link className="underline" href="/capture">
            Capture receipt or shelf tag
          </Link>
        )}
        <span>{identity.display_name}</span>
        {identity.access !== 'local_operator' && (
          <Button
            variant="ghost"
            size="sm"
            disabled={signingOut}
            onClick={() => void signOut()}
          >
            {signingOut ? 'Signing out…' : 'Sign out'}
          </Button>
        )}
      </div>
      {error && (
        <p role="alert" className="p-3 text-loss">
          {error}
        </p>
      )}
      <main id="main-content" className="flex-1 overflow-auto" tabIndex={-1}>
        {child && path !== '/capture' ? (
          <p className="p-6">Opening capture…</p>
        ) : (
          children
        )}
      </main>
      {!child && <JennyChatWidget />}
    </>
  )
}
