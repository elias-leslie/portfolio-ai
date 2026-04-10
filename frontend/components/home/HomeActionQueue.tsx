'use client'

import { ArrowRight, Brain, CheckCircle2, House, Target } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HomeActionItem } from '@/lib/api/home'
import { formatDecisionMeta, formatDecisionSeverity } from '@/lib/decision'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'
import { useAcknowledgeJennyNotification } from '@/lib/hooks/usePortfolio'
import { useTransitionSymbolWorkflow } from '@/lib/hooks/useSymbolIntelligence'
import { cn, formatRelativeTime } from '@/lib/utils'

const categoryIcons = {
  household: House,
  investing: Target,
  learning: Brain,
  overview: ArrowRight,
}

const priorityTone = {
  critical: 'border-loss/25 border-l-loss/60 border-l-[3px] bg-loss/5',
  high: 'border-warning/25 border-l-warning/60 border-l-[3px] bg-warning/5',
  warning: 'border-warning/25 border-l-warning/60 border-l-[3px] bg-warning/5',
  medium: 'border-primary/15 border-l-primary/40 border-l-[3px] bg-primary/5',
  low: 'border-border/40 border-l-border/50 border-l-[3px] bg-surface-muted/15',
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

function SummaryMetric({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface-muted/15 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text">
        {value}
      </p>
      <p className="mt-1 text-xs text-text-muted">{detail}</p>
    </div>
  )
}

export function HomeActionQueue() {
  const { data, isLoading, error, refetch, isFetching } = useHomeActionQueue()
  const acknowledgeNotification = useAcknowledgeJennyNotification()
  const transitionWorkflow = useTransitionSymbolWorkflow()
  const actions = data?.actions ?? []
  const [clearingActionIds, setClearingActionIds] = useState<Set<string>>(
    () => new Set(),
  )
  const [clearedActionIds, setClearedActionIds] = useState<Set<string>>(
    () => new Set(),
  )
  const visibleActions = actions.filter((action) => !clearedActionIds.has(action.id))
  const activeActions = visibleActions.filter(
    (action) => !clearingActionIds.has(action.id),
  )
  const urgentCount = activeActions.filter((action) =>
    ['critical', 'high'].includes(action.priority),
  ).length
  const quickActionCount = activeActions.filter((action) =>
    Boolean(action.execution),
  ).length

  useEffect(() => {
    const actionIds = new Set(actions.map((action) => action.id))
    setClearingActionIds((current) => {
      const next = new Set([...current].filter((id) => actionIds.has(id)))
      return next.size === current.size ? current : next
    })
    setClearedActionIds((current) => {
      const next = new Set([...current].filter((id) => actionIds.has(id)))
      return next.size === current.size ? current : next
    })
  }, [actions])

  const markExecutionSucceeded = (actionId: string) => {
    setClearingActionIds((current) => new Set(current).add(actionId))
  }

  const handleActionTransitionEnd = (actionId: string) => {
    if (!clearingActionIds.has(actionId)) {
      return
    }

    setClearingActionIds((current) => {
      const next = new Set(current)
      next.delete(actionId)
      return next
    })
    setClearedActionIds((current) => new Set(current).add(actionId))
  }

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
        onSuccess: () => markExecutionSucceeded(action.id),
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
          onSuccess: () => markExecutionSucceeded(action.id),
        },
      )
    }
  }

  return (
    <div className="space-y-4">
      {!isLoading && !error ? (
        <div>
          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryMetric
              label="Prioritized"
              value={String(activeActions.length)}
              detail={`ranked action${activeActions.length === 1 ? '' : 's'}`}
            />
            <SummaryMetric
              label="Urgent"
              value={String(urgentCount)}
              detail="critical or high priority"
            />
            <SummaryMetric
              label="Quick Ready"
              value={String(quickActionCount)}
              detail="can be completed inline"
            />
          </div>
          <p className="mt-2 text-xs text-text-muted">
            {data?.generatedAt
              ? `Updated ${formatRelativeTime(data.generatedAt)}`
              : 'Update time unavailable'}
          </p>
        </div>
      ) : null}

      <SectionCard variant="surface" title="Action Queue">
        {isLoading ? (
          <div
            className="grid gap-3 lg:grid-cols-2"
            role="status"
            aria-live="polite"
          >
            {[...Array(4)].map((_, index) => (
              <div
                key={`home-action-skeleton-${index}`}
                className="skeleton rounded-2xl h-28"
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

        {!isLoading && !error && visibleActions.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-gradient-to-br from-surface-muted/10 to-surface/30 px-6 py-12 text-center">
            <div className="relative mx-auto mb-5">
              <div className="absolute inset-0 mx-auto h-12 w-12 rounded-full bg-gain/10 blur-xl" />
              <div className="relative mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-gain/20 bg-gain/10">
                <CheckCircle2 className="h-6 w-6 text-gain" />
              </div>
            </div>
            <p className="font-display italic text-xl text-text">All clear</p>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-text-muted">
              No urgent cross-workspace actions are open right now.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Button asChild size="sm" variant="outline">
                <Link href="/portfolio">Review Investing</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link href="/money?utility=evidence">Add Evidence</Link>
              </Button>
            </div>
          </div>
        ) : null}

        {!isLoading && !error && visibleActions.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2 animate-stagger">
            {visibleActions.map((action) => {
              const Icon =
                categoryIcons[action.category as keyof typeof categoryIcons] ??
                ArrowRight
              const tone =
                priorityTone[action.priority as keyof typeof priorityTone] ??
                priorityTone.low
              const quickLabel = quickActionLabel(action)
              const quickTitle = quickActionTitle(action)
              const decisionMeta = formatDecisionMeta(action.decision, {
                includeTimestamp: false,
              })
              const decisionTimestamp = action.decision?.sourceTimestamp
                ? formatRelativeTime(action.decision.sourceTimestamp)
                : null
              const badgeLabel = action.decision?.severity
                ? formatDecisionSeverity(action.decision.severity)
                : action.badge
              const isClearing = clearingActionIds.has(action.id)

              return (
                <div
                  key={action.id}
                  className={cn(
                    'group rounded-2xl border p-4 card-interactive transition-all duration-300 hover:border-primary/30',
                    tone,
                    isClearing &&
                      'pointer-events-none -translate-y-1 scale-[0.98] opacity-0',
                  )}
                  onTransitionEnd={(event) => {
                    if (event.target === event.currentTarget) {
                      handleActionTransitionEnd(action.id)
                    }
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-2">
                      <div className="flex items-center gap-2.5">
                        <div
                          className={cn(
                            'h-2 w-2 shrink-0 rounded-full',
                            priorityDot[
                              action.priority as keyof typeof priorityDot
                            ] ?? priorityDot.low,
                          )}
                        />
                        <Icon className="h-4 w-4 shrink-0 text-text-muted" />
                        <span className="truncate text-sm font-semibold text-text">
                          {action.title}
                        </span>
                      </div>
                      {decisionMeta ? (
                        <p className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
                          {decisionMeta}
                          {decisionTimestamp ? ` · ${decisionTimestamp}` : ''}
                        </p>
                      ) : null}
                      <p className="text-sm leading-relaxed text-text-muted">
                        {action.detail}
                      </p>
                    </div>
                    {badgeLabel ? (
                      <Badge variant="outline" className="shrink-0">
                        {badgeLabel}
                      </Badge>
                    ) : null}
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
      </SectionCard>
    </div>
  )
}
