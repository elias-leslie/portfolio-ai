'use client'

import { ArrowRight, Brain, CheckCircle2, House, Target } from 'lucide-react'
import Link from 'next/link'
import { useHomeActionQueueState } from '@/components/providers/HomeActionQueueProvider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatDecisionMeta, formatDecisionSeverity } from '@/lib/decision'
import { cn } from '@/lib/utils'
import { quickActionLabel, quickActionTitle } from './quickActionHelpers'

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

export function HomeActionQueueContent({
  limit,
  layout = 'stack',
  onNavigate,
}: {
  limit?: number
  layout?: 'stack' | 'grid'
  onNavigate?: () => void
}) {
  const {
    visibleActions,
    isLoading,
    isFetching,
    isExecuting,
    error,
    refetchActions,
    executeAction,
  } = useHomeActionQueueState()
  const displayedActions = limit
    ? visibleActions.slice(0, limit)
    : visibleActions
  const remainingCount = visibleActions.length - displayedActions.length

  if (isLoading) {
    return (
      <div className="grid gap-2" role="status" aria-live="polite">
        <span className="sr-only">Loading next actions.</span>
        {[...Array(layout === 'grid' ? 2 : 3)].map((_, index) => (
          <div
            key={`home-action-skeleton-${index}`}
            className="skeleton h-20 rounded-lg"
            aria-hidden="true"
          />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="rounded-lg border border-border/40 bg-surface-muted/20 p-3"
        role="alert"
      >
        <p className="text-sm font-medium text-text">
          Next actions unavailable
        </p>
        <p className="mt-1 text-xs leading-5 text-text-muted">
          The rest of Today is still available. Retry this queue when ready.
        </p>
        <Button
          className="mt-3"
          size="sm"
          variant="outline"
          onClick={refetchActions}
          disabled={isFetching}
        >
          Retry next actions
        </Button>
      </div>
    )
  }

  if (visibleActions.length === 0) {
    return (
      <div
        className="flex items-start gap-3 rounded-lg border border-dashed border-border/40 bg-surface-muted/10 p-3"
        role="status"
      >
        <CheckCircle2
          className="mt-0.5 size-4 shrink-0 text-gain"
          aria-hidden="true"
        />
        <div>
          <p className="text-sm font-medium text-text">All clear</p>
          <p className="mt-0.5 text-xs leading-5 text-text-muted">
            No urgent cross-workspace actions are open right now.
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
      <div
        className={cn(
          'grid gap-2',
          layout === 'grid' && 'md:grid-cols-2 xl:grid-cols-3',
        )}
      >
        {displayedActions.map((action) => {
          const Icon =
            categoryIcons[action.category as keyof typeof categoryIcons] ??
            ArrowRight
          const quickLabel = quickActionLabel(action)
          const quickTitle = quickActionTitle(action)
          const decisionMeta = formatDecisionMeta(action.decision, {
            includeTimestamp: false,
          })
          const badgeLabel = action.decision?.severity
            ? formatDecisionSeverity(action.decision.severity)
            : action.badge

          return (
            <article
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
                      aria-hidden="true"
                    />
                    <Icon
                      className="mt-0.5 size-4 shrink-0 text-text-muted"
                      aria-hidden="true"
                    />
                    <h3 className="min-w-0 text-sm font-semibold leading-5 text-text">
                      {action.title}
                    </h3>
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
                  onClick={onNavigate}
                >
                  <Link href={action.href}>
                    {action.actionLabel}
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </Link>
                </Button>
                {action.execution && quickLabel ? (
                  <Button
                    size="sm"
                    onClick={() => executeAction(action)}
                    title={quickTitle}
                    disabled={isExecuting}
                  >
                    {quickLabel}
                  </Button>
                ) : null}
              </div>
            </article>
          )
        })}
      </div>
      {remainingCount > 0 ? (
        <p className="mt-3 text-xs text-text-muted">
          {remainingCount} more {remainingCount === 1 ? 'action' : 'actions'} in
          the Actions menu.
        </p>
      ) : null}
    </>
  )
}
