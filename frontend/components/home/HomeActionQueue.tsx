'use client'

import { ArrowRight, Brain, House, Target } from 'lucide-react'
import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'

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
              <Link
                key={action.id}
                href={action.href}
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
                <div className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-text">
                  {action.actionLabel}
                  <ArrowRight className="h-4 w-4" />
                </div>
              </Link>
            )
          })}
        </div>
      ) : null}
    </SectionCard>
  )
}
