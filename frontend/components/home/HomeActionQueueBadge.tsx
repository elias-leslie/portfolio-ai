'use client'

import {
  ArrowRight,
  Brain,
  CheckCircle2,
  House,
  ListChecks,
  Loader2,
  Target,
} from 'lucide-react'
import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { RelativeTime } from '@/components/shared/RelativeTime'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HomeActionItem } from '@/lib/api/home'
import { formatDecisionMeta, formatDecisionSeverity } from '@/lib/decision'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'
import { useAcknowledgeJennyNotification } from '@/lib/hooks/usePortfolio'
import { useTransitionSymbolWorkflow } from '@/lib/hooks/useSymbolIntelligence'
import { cn } from '@/lib/utils'

const categoryIcons = {
  household: House,
  investing: Target,
  learning: Brain,
  overview: ArrowRight,
}

const priorityDot = {
  critical: 'bg-loss',
  high: 'bg-warning',
  warning: 'bg-warning',
  medium: 'bg-primary',
  low: 'bg-text-muted',
}

function quickActionLabel(action: HomeActionItem) {
  if (!action.execution) {
    return null
  }

  switch (action.execution.kind) {
    case 'acknowledge_notification':
      return 'Dismiss alert'
    case 'workflow_transition':
      return 'Advance workflow'
    default:
      return 'Quick action'
  }
}

function quickActionTitle(action: HomeActionItem) {
  if (action.execution?.kind === 'acknowledge_notification') {
    return 'Dismisses this Today alert only. It does not place a trade or approve the recommendation.'
  }

  return undefined
}

export function HomeActionQueueBadge() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const { data, isLoading, error, refetch, isFetching } = useHomeActionQueue()
  const acknowledgeNotification = useAcknowledgeJennyNotification()
  const transitionWorkflow = useTransitionSymbolWorkflow()
  const actions = data?.actions ?? []
  const [clearedActionIds, setClearedActionIds] = useState<Set<string>>(
    () => new Set(),
  )
  const visibleActions = actions.filter(
    (action) => !clearedActionIds.has(action.id),
  )
  const count = visibleActions.length

  useEffect(() => {
    const actionIds = new Set(actions.map((action) => action.id))
    setClearedActionIds((current) => {
      const next = new Set([...current].filter((id) => actionIds.has(id)))
      return next.size === current.size ? current : next
    })
  }, [actions])

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

  const handleExecution = (action: HomeActionItem) => {
    const execution = action.execution
    if (!execution) {
      return
    }

    if (
      execution.kind === 'acknowledge_notification' &&
      execution.notificationId
    ) {
      acknowledgeNotification.mutate(execution.notificationId, {
        onSuccess: () => {
          setClearedActionIds((current) => new Set(current).add(action.id))
        },
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
        {
          onSuccess: () => {
            setClearedActionIds((current) => new Set(current).add(action.id))
          },
        },
      )
    }
  }

  const triggerLabel = isLoading ? 'Actions' : `Actions ${count}`

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Action Queue, ${isLoading ? 'loading' : `${count} open`}`}
        onClick={() => setOpen((current) => !current)}
        className={cn(
          'inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
          count > 0
            ? 'border-warning/35 bg-warning/10 text-text hover:border-warning/55 hover:bg-warning/15'
            : 'border-border/40 bg-surface/60 text-text-muted hover:border-border/60 hover:bg-surface/80 hover:text-text',
        )}
      >
        {isLoading ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
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
          className="fixed right-3 top-16 z-[60] mt-2 w-[min(calc(100vw-1.5rem),42rem)] overflow-hidden rounded-xl border border-border/50 bg-surface-overlay shadow-2xl shadow-bg/40 sm:right-6 lg:right-8"
        >
          <div className="border-b border-border/40 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-text">Action Queue</p>
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
              <Badge variant={count > 0 ? 'warning' : 'success'}>
                {isLoading ? '...' : count}
              </Badge>
            </div>
          </div>

          <div className="max-h-[calc(100vh-10rem)] overflow-y-auto overflow-x-hidden p-3">
            {isLoading ? (
              <div className="grid gap-2" role="status" aria-live="polite">
                {[...Array(3)].map((_, index) => (
                  <div
                    key={`home-action-menu-skeleton-${index}`}
                    className="skeleton h-20 rounded-lg"
                  />
                ))}
              </div>
            ) : null}

            {!isLoading && error ? (
              <div className="rounded-lg border border-border/40 bg-surface-muted/20 p-3">
                <p className="text-sm font-medium text-text">
                  Action Queue unavailable
                </p>
                <Button
                  className="mt-3"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    void refetch()
                  }}
                  disabled={isFetching}
                >
                  Refresh
                </Button>
              </div>
            ) : null}

            {!isLoading && !error && visibleActions.length === 0 ? (
              <div className="flex items-start gap-3 rounded-lg border border-dashed border-border/40 bg-surface-muted/10 p-3">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-gain" />
                <div>
                  <p className="text-sm font-medium text-text">All clear</p>
                  <p className="mt-0.5 text-xs leading-5 text-text-muted">
                    No urgent cross-workspace actions are open right now.
                  </p>
                </div>
              </div>
            ) : null}

            {!isLoading && !error && visibleActions.length > 0 ? (
              <div className="grid gap-2">
                {visibleActions.map((action) => {
                  const Icon =
                    categoryIcons[
                      action.category as keyof typeof categoryIcons
                    ] ?? ArrowRight
                  const quickLabel = quickActionLabel(action)
                  const quickTitle = quickActionTitle(action)
                  const decisionMeta = formatDecisionMeta(action.decision, {
                    includeTimestamp: false,
                  })
                  const badgeLabel = action.decision?.severity
                    ? formatDecisionSeverity(action.decision.severity)
                    : action.badge

                  return (
                    <div
                      key={action.id}
                      className="overflow-hidden rounded-lg border border-border/40 bg-surface/70 p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0 flex-1 basis-64">
                          <div className="flex min-w-0 items-start gap-2">
                            <span
                              className={cn(
                                'mt-1.5 size-2 shrink-0 rounded-full',
                                priorityDot[
                                  action.priority as keyof typeof priorityDot
                                ] ?? priorityDot.low,
                              )}
                            />
                            <Icon className="mt-0.5 size-4 shrink-0 text-text-muted" />
                            <p className="min-w-0 text-sm font-semibold leading-5 text-text">
                              {action.title}
                            </p>
                          </div>
                          {decisionMeta ? (
                            <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-muted">
                              {decisionMeta}
                            </p>
                          ) : null}
                        </div>
                        {badgeLabel ? (
                          <Badge
                            variant="outline"
                            className="max-w-full shrink-0 whitespace-normal text-left leading-4"
                          >
                            {badgeLabel}
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-2 break-words text-xs leading-5 text-text-muted">
                        {action.detail}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          asChild
                          size="sm"
                          variant="outline"
                          onClick={() => setOpen(false)}
                        >
                          <Link href={action.href}>
                            {action.actionLabel}
                            <ArrowRight className="size-4" />
                          </Link>
                        </Button>
                        {action.execution && quickLabel ? (
                          <Button
                            size="sm"
                            onClick={() => handleExecution(action)}
                            title={quickTitle}
                            disabled={
                              acknowledgeNotification.isPending ||
                              transitionWorkflow.isPending
                            }
                          >
                            {quickLabel}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
