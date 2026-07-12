'use client'

import { ListChecks } from 'lucide-react'
import { useHomeActionQueueState } from '@/components/providers/HomeActionQueueProvider'
import { Badge } from '@/components/ui/badge'
import { HomeActionQueueContent } from './HomeActionQueueContent'

export function HomeNextActions() {
  const { data, visibleActions, isLoading, error } = useHomeActionQueueState()
  const count = visibleActions.length

  return (
    <section
      aria-labelledby="today-next-actions-title"
      className="rounded-2xl border border-border/40 bg-surface/50 p-4 surface-highlight backdrop-blur-sm sm:p-5"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ListChecks className="size-4 text-primary" aria-hidden="true" />
            <h2
              id="today-next-actions-title"
              className="font-display text-lg italic tracking-tight text-text"
            >
              Next actions
            </h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-text-muted">
            {data?.summary ??
              'The most important open decisions across money and investing.'}
          </p>
        </div>
        <Badge variant={error ? 'outline' : count > 0 ? 'warning' : 'success'}>
          {isLoading ? 'Loading' : error ? 'Unavailable' : `${count} open`}
        </Badge>
      </div>
      <HomeActionQueueContent limit={3} layout="grid" />
    </section>
  )
}
