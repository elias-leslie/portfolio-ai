'use client'

import { MessageCircle, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { JennyChatConversation } from '@/components/chat/JennyChatConversation'
import { useChatWidget } from '@/components/providers/ChatWidgetProvider'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

const MOBILE_DIALOG_QUERY = '(max-width: 639px)'

export function JennyChatWidget() {
  const { enabled, ready } = useChatWidget()
  const [expanded, setExpanded] = useState(false)
  const [mobileDialog, setMobileDialog] = useState(false)

  useEffect(() => {
    const media = window.matchMedia(MOBILE_DIALOG_QUERY)
    const handleChange = () => {
      setMobileDialog(media.matches)
    }

    handleChange()
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  if (!ready || !enabled) {
    return null
  }

  return (
    <Dialog open={expanded} onOpenChange={setExpanded} modal={mobileDialog}>
      <DialogTrigger asChild>
        <button
          type="button"
          aria-label="Open Jenny chat"
          className="fixed bottom-4 right-4 z-[60] flex size-12 items-center justify-center rounded-full border border-primary/40 bg-primary text-primary-foreground shadow-lg shadow-bg/40 transition-transform duration-200 hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus data-[state=open]:invisible data-[state=open]:pointer-events-none sm:bottom-6 sm:right-6"
        >
          <MessageCircle className="size-6" aria-hidden />
        </button>
      </DialogTrigger>

      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[65] sm:hidden"
        className="bottom-0 left-0 top-auto z-[70] flex max-h-[calc(100dvh-1rem)] w-full max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-b-none border-border/50 bg-surface-overlay p-0 shadow-2xl shadow-bg/40 sm:bottom-6 sm:left-auto sm:right-6 sm:w-[min(calc(100vw-3rem),26rem)] sm:max-w-[26rem] sm:rounded-xl"
      >
        <div className="flex items-center justify-between gap-3 border-b border-border/40 px-4 py-3">
          <div className="min-w-0">
            <DialogTitle className="text-sm font-semibold not-italic text-text">
              Chat with Jenny
            </DialogTitle>
            <DialogDescription className="mt-0.5 text-xs text-text-muted">
              Household advisor with live portfolio access.
            </DialogDescription>
          </div>
          <DialogClose asChild>
            <button
              type="button"
              aria-label="Close Jenny chat"
              className="rounded-md p-1 text-text-muted transition-colors hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              <X className="size-4" aria-hidden />
            </button>
          </DialogClose>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:max-h-[min(70vh,32rem)]">
          <JennyChatConversation />
        </div>
      </DialogContent>
    </Dialog>
  )
}
