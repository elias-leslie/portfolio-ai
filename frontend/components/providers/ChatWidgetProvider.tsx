'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

const STORAGE_KEY = 'portfolio-ai:jenny-chat:widget-enabled'

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
  const [enabled, setEnabledState] = useState(true)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    try {
      setEnabledState(window.localStorage.getItem(STORAGE_KEY) !== 'false')
    } catch {
      // ignore — keep default enabled
    }
    setReady(true)
  }, [])

  const setEnabled = useCallback((next: boolean) => {
    setEnabledState(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, String(next))
    } catch {
      // ignore — preference just won't persist
    }
  }, [])

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
