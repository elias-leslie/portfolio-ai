'use client'

import { MessageCircle, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { JennyChatConversation } from '@/components/chat/JennyChatConversation'
import { useChatWidget } from '@/components/providers/ChatWidgetProvider'

export function JennyChatWidget() {
  const { enabled, ready } = useChatWidget()
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (!expanded) {
      return
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExpanded(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [expanded])

  if (!ready || !enabled) {
    return null
  }

  if (!expanded) {
    return (
      <button
        type="button"
        aria-label="Open Jenny chat"
        onClick={() => setExpanded(true)}
        className="fixed bottom-4 right-4 z-[60] flex size-12 items-center justify-center rounded-full border border-primary/40 bg-primary text-primary-foreground shadow-lg shadow-bg/40 transition-transform duration-200 hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:bottom-6 sm:right-6"
      >
        <MessageCircle className="size-6" aria-hidden />
      </button>
    )
  }

  return (
    <div
      role="dialog"
      aria-label="Jenny chat"
      className="fixed bottom-4 right-4 z-[60] flex w-[min(calc(100vw-2rem),26rem)] flex-col overflow-hidden rounded-xl border border-border/50 bg-surface-overlay shadow-2xl shadow-bg/40 sm:bottom-6 sm:right-6"
    >
      <div className="flex items-center justify-between gap-3 border-b border-border/40 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">Chat with Jenny</p>
          <p className="mt-0.5 text-xs text-text-muted">
            Household advisor with live portfolio access.
          </p>
        </div>
        <button
          type="button"
          aria-label="Close Jenny chat"
          onClick={() => setExpanded(false)}
          className="rounded-md p-1 text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <div className="max-h-[min(70vh,32rem)] overflow-y-auto p-4">
        <JennyChatConversation />
      </div>
    </div>
  )
}
