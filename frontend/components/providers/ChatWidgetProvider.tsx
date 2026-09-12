'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import {
  identityStorageKey,
  useHouseholdIdentity,
} from './HouseholdIdentityProvider'

type ChatWidgetContextValue = {
  enabled: boolean
  /** False until the localStorage preference has hydrated on the client. */
  ready: boolean
  setEnabled: (enabled: boolean) => void
}

const ChatWidgetContext = createContext<ChatWidgetContextValue | null>(null)

export function ChatWidgetProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const identity = useHouseholdIdentity()
  const storageKey = identityStorageKey(identity, 'jenny-chat:widget-enabled')
  const [enabled, setEnabledState] = useState(true)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    try {
      setEnabledState(window.localStorage.getItem(storageKey) !== 'false')
    } catch {
      // ignore — keep default enabled
    }
    setReady(true)
  }, [storageKey])

  const setEnabled = useCallback(
    (next: boolean) => {
      setEnabledState(next)
      try {
        window.localStorage.setItem(storageKey, String(next))
      } catch {
        // ignore — preference just won't persist
      }
    },
    [storageKey],
  )

  return (
    <ChatWidgetContext.Provider value={{ enabled, ready, setEnabled }}>
      {children}
    </ChatWidgetContext.Provider>
  )
}

export function useChatWidget(): ChatWidgetContextValue {
  const context = useContext(ChatWidgetContext)
  if (!context) {
    throw new Error('useChatWidget must be used within ChatWidgetProvider')
  }
  return context
}
