'use client'

import { ArrowRight, Brain, House, Target } from 'lucide-react'
import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { HomeActionItem } from '@/lib/api/home'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'
import { useAcknowledgeJennyNotification } from '@/lib/hooks/usePortfolio'
import { useTransitionSymbolWorkflow } from '@/lib/hooks/useSymbolIntelligence'

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

export function HomeActionQueue() {
  const { data, isLoading, error } = useHomeActionQueue()
  const acknowledgeNotification = useAcknowledgeJennyNotification()
  const transitionWorkflow = useTransitionSymbolWorkflow()

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
        <div className="rounded-2xl border border-loss/30 bg-loss/10 p-4 text-sm text-loss">
          Failed to load the action queue.
        </div>
      ) : null}

      {!isLoading && !error ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {data?.actions.map((action) => {
            const Icon =
              categoryIcons[action.category as keyof typeof categoryIcons] ?? ArrowRight
            const tone =
              priorityTone[action.priority as keyof typeof priorityTone] ??
              priorityTone.low

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
                  {action.execution ? (
                    <Button
                      size="sm"
                      onClick={() => handleExecution(action)}
                      disabled={
                        acknowledgeNotification.isPending || transitionWorkflow.isPending
                      }
                    >
                      Quick action
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
