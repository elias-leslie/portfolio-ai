'use client'

import { ArrowRight, Brain, House, Target } from 'lucide-react'
import Link from 'next/link'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HomeActionItem } from '@/lib/api/home'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'
import { useAcknowledgeJennyNotification } from '@/lib/hooks/usePortfolio'
import { useTransitionSymbolWorkflow } from '@/lib/hooks/useSymbolIntelligence'
import { formatRelativeTime } from '@/lib/utils'

const categoryIcons = {
  household: House,
  investing: Target,
  learning: Brain,
  overview: ArrowRight,
}

const priorityTone = {
  critical: 'border-loss/30 bg-loss/10',
  high: 'border-warning/30 bg-warning/10',
  warning: 'border-warning/30 bg-warning/10',
  medium: 'border-primary/20 bg-primary/5',
  low: 'border-border/50 bg-surface-muted/20',
}

function quickActionLabel(action: HomeActionItem) {
  if (!action.execution) {
    return null
  }

  switch (action.execution.kind) {
    case 'acknowledge_notification':
      return 'Acknowledge'
    case 'workflow_transition':
      return 'Advance workflow'
    default:
      return 'Quick action'
  }
}

export function HomeActionQueue() {
  const { data, isLoading, error, refetch, isFetching } = useHomeActionQueue()
  const acknowledgeNotification = useAcknowledgeJennyNotification()
  const transitionWorkflow = useTransitionSymbolWorkflow()
  const actions = data?.actions ?? []
  const urgentCount = actions.filter((action) =>
    ['critical', 'high'].includes(action.priority),
  ).length
  const quickActionCount = actions.filter((action) => Boolean(action.execution)).length

  const handleExecution = (action: HomeActionItem) => {
    const execution = action.execution
    if (!execution) {
      return
    }

    if (execution.kind === 'acknowledge_notification' && execution.notificationId) {
      acknowledgeNotification.mutate(execution.notificationId)
      return
    }

    if (
      execution.kind === 'workflow_transition' &&
      execution.symbol &&
      execution.stage
    ) {
      transitionWorkflow.mutate({
        symbol: execution.symbol,
        stage: execution.stage,
      })
    }
  }

  return (
    <SectionCard
      variant="surface"
      title="Action Queue"
      description={
        data?.summary ??
        'The most important next steps across today, the portfolio, and the money system.'
      }
    >
      {!isLoading && !error ? (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-border/40 bg-surface-muted/20 px-4 py-3 text-sm text-text-muted">
          <span>
            {actions.length} prioritized action{actions.length === 1 ? '' : 's'}
            {urgentCount > 0 ? ` · ${urgentCount} urgent` : ''}
            {quickActionCount > 0 ? ` · ${quickActionCount} quick action-ready` : ''}
          </span>
          <span>Updated {formatRelativeTime(data?.generatedAt)}</span>
        </div>
      ) : null}

      {isLoading ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {[...Array(4)].map((_, index) => (
            <div
              key={`home-action-skeleton-${index}`}
              className="h-28 animate-pulse rounded-2xl bg-surface-muted/40"
            />
          ))}
        </div>
      ) : null}

      {!isLoading && error ? (
        <LoadErrorState
          title="Failed to load the action queue."
          detail="Retry to refresh today’s next actions across the portfolio and money system."
          onRetry={() => {
            void refetch()
          }}
          isRetrying={isFetching}
        />
      ) : null}

      {!isLoading && !error && actions.length === 0 ? (
        <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-5">
          <p className="text-sm font-medium text-text">No urgent cross-workspace actions.</p>
          <p className="mt-2 text-sm text-text-muted">
            The queue is clear for now. Use this time to tighten the watchlist, review the
            portfolio, or upload new household documents so Jenny has fresher evidence.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href="/watchlist">Review Watchlist</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/money?tab=intake">Open Intake</Link>
            </Button>
          </div>
        </div>
      ) : null}

      {!isLoading && !error && actions.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {actions.map((action) => {
            const Icon =
              categoryIcons[action.category as keyof typeof categoryIcons] ?? ArrowRight
            const tone =
              priorityTone[action.priority as keyof typeof priorityTone] ??
              priorityTone.low
            const quickLabel = quickActionLabel(action)

            return (
              <div
                key={action.id}
                className={`rounded-2xl border p-4 transition hover:border-primary/40 hover:bg-surface-muted/30 ${tone}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm font-semibold text-text">
                      <Icon className="h-4 w-4 text-primary" />
                      <span>{action.title}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">{action.category}</Badge>
                      <Badge variant="outline">{action.source}</Badge>
                      <Badge variant="outline">{action.priority}</Badge>
                    </div>
                    <p className="text-sm text-text-muted">{action.detail}</p>
                  </div>
                  {action.badge ? <Badge variant="outline">{action.badge}</Badge> : null}
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <Button asChild size="sm" variant="outline">
                    <Link href={action.href}>
                      {action.actionLabel}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                  {action.execution && quickLabel ? (
                    <Button
                      size="sm"
                      onClick={() => handleExecution(action)}
                      disabled={
                        acknowledgeNotification.isPending || transitionWorkflow.isPending
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
    </SectionCard>
  )
}
