'use client'

import { AlertCircle, CheckCircle2, ListChecks, Loader2 } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useHomeActionQueueState } from '@/components/providers/HomeActionQueueProvider'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { HomeActionQueueContent } from './HomeActionQueueContent'

export function HomeActionQueueBadge() {
  const [open, setOpen] = useState(false)
  const titleId = useId()
  const containerRef = useRef<HTMLDivElement | null>(null)
  const { data, visibleActions, isLoading, error } = useHomeActionQueueState()
  const count = visibleActions.length

  useEffect(() => {
    if (!open) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const triggerLabel = isLoading
    ? 'Actions'
    : error
      ? 'Actions unavailable'
      : `Actions ${count}`
  const queueStatus = isLoading
    ? 'loading'
    : error
      ? 'unavailable'
      : `${count} open`

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Action Queue, ${queueStatus}`}
        onClick={() => setOpen((current) => !current)}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
          error
            ? 'border-loss/35 bg-loss/10 text-text hover:border-loss/55 hover:bg-loss/15'
            : count > 0
              ? 'border-warning/35 bg-warning/10 text-text hover:border-warning/55 hover:bg-warning/15'
              : 'border-border/40 bg-surface/60 text-text-muted hover:border-border/60 hover:bg-surface/80 hover:text-text',
        )}
      >
        {isLoading ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : error ? (
          <AlertCircle className="size-4 text-loss" aria-hidden />
        ) : count > 0 ? (
          <span className="flex size-4 items-center justify-center rounded-full bg-warning text-[10px] font-bold text-bg">
            {count}
          </span>
        ) : (
          <CheckCircle2 className="size-4 text-gain" aria-hidden />
        )}
        <ListChecks className="size-4" aria-hidden />
        <span className="hidden sm:inline">{triggerLabel}</span>
      </button>

      {open ? (
        <div
          role="dialog"
          aria-labelledby={titleId}
          className="fixed right-3 top-16 z-[60] mt-2 w-[min(calc(100vw-1.5rem),42rem)] overflow-hidden rounded-xl border border-border/50 bg-surface-overlay shadow-2xl shadow-bg/40 sm:right-6 lg:right-8"
        >
          <div className="border-b border-border/40 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p id={titleId} className="text-sm font-semibold text-text">
                  Action Queue
                </p>
                <p className="mt-0.5 text-xs text-text-muted">
                  {data?.generatedAt ? (
                    <>
                      {data.summary} Updated{' '}
                      <RelativeTime value={data.generatedAt} />.
                    </>
                  ) : (
                    'Next actions across money and investing.'
                  )}
                </p>
              </div>
              <Badge
                variant={error ? 'outline' : count > 0 ? 'warning' : 'success'}
              >
                {isLoading ? '...' : error ? 'Unavailable' : count}
              </Badge>
            </div>
          </div>

          <div className="max-h-[calc(100vh-10rem)] overflow-y-auto overflow-x-hidden p-3">
            <HomeActionQueueContent onNavigate={() => setOpen(false)} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
