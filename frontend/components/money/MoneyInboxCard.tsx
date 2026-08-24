'use client'

import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import type { HouseholdInboxItem } from '@/lib/api/household'

export interface MoneyInboxCardProps {
  inbox: HouseholdInboxItem[] | undefined
  isLoading: boolean
}

const PRIORITY_VARIANT: Record<
  string,
  'error' | 'warning' | 'secondary' | 'outline'
> = {
  high: 'error',
  medium: 'warning',
  low: 'secondary',
}

/**
 * Everything waiting on a person, on the screen where the month is reviewed.
 *
 * The inbox reached the UI through exactly one door before this: two items,
 * filtered to those affecting Free to spend, inside a Decision Board card. The
 * other items — a stale balance, an unlinked card, a question only the
 * household can answer — had no surface at all. Each of these is the reason
 * some number on this screen is not yet trustworthy, so this is where they
 * belong.
 */
export function MoneyInboxCard({ inbox, isLoading }: MoneyInboxCardProps) {
  if (!inbox || inbox.length === 0) {
    return (
      <SectionCard
        variant="surface"
        title="Waiting on you"
        description={
          isLoading
            ? 'Reading the review queue…'
            : 'Nothing in the review queue is waiting on a person.'
        }
      >
        {null}
      </SectionCard>
    )
  }

  return (
    <SectionCard
      variant="surface"
      title="Waiting on you"
      description={`${inbox.length} item${inbox.length === 1 ? '' : 's'} that no amount of processing can settle — each one is why some number here is not yet final.`}
    >
      <div className="space-y-2">
        {inbox.map((item) => {
          const body = (
            <>
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-text">{item.title}</p>
                <Badge variant={PRIORITY_VARIANT[item.priority] ?? 'outline'}>
                  {item.actionLabel}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-text-muted">{item.detail}</p>
            </>
          )
          return item.actionHref ? (
            <Link
              key={item.id}
              href={item.actionHref}
              className="block rounded-2xl border border-border/40 bg-surface-muted/15 px-4 py-3 transition-colors hover:border-primary/40"
            >
              {body}
            </Link>
          ) : (
            <div
              key={item.id}
              className="rounded-2xl border border-border/40 bg-surface-muted/15 px-4 py-3"
            >
              {body}
            </div>
          )
        })}
      </div>
    </SectionCard>
  )
}
