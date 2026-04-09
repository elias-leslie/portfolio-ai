'use client'

import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type { HouseholdInboxItem, HouseholdQuestion } from '@/lib/api/household'
import { JennyQuestionInbox } from './JennyQuestionInbox'

const priorityTone = {
  critical: 'border-loss/25 border-l-loss/60 bg-loss/5',
  high: 'border-warning/25 border-l-warning/60 bg-warning/5',
  medium: 'border-primary/20 border-l-primary/40 bg-primary/5',
  low: 'border-border/40 border-l-border/50 bg-surface-muted/10',
}

export function MoneyInboxPanel({
  inbox,
  questions,
}: {
  inbox: HouseholdInboxItem[]
  questions: HouseholdQuestion[]
}) {
  const openQuestions = questions.filter((question) => !question.answeredAt)

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Inbox"
        description="One ranked list of what is stale, missing, ambiguous, or blocking the money system."
      >
        {inbox.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            Jenny does not currently see a blocking freshness or data-gap issue.
          </div>
        ) : (
          <div className="grid gap-3">
            {inbox.map((item) => (
              <div
                key={item.id}
                className={`rounded-2xl border border-l-[3px] p-4 ${
                  priorityTone[item.priority as keyof typeof priorityTone] ??
                  priorityTone.low
                }`}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-text-muted">
                      <span>{item.priority}</span>
                      <span>{item.category}</span>
                    </div>
                    <p className="text-sm font-semibold text-text">
                      {item.title}
                    </p>
                    <p className="text-sm leading-relaxed text-text-muted">
                      {item.detail}
                    </p>
                  </div>
                  {item.actionHref ? (
                    <Button
                      asChild
                      size="sm"
                      variant="outline"
                      className="lg:shrink-0"
                    >
                      <Link href={item.actionHref}>{item.actionLabel}</Link>
                    </Button>
                  ) : (
                    <span className="text-xs text-text-muted">
                      {item.actionLabel}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {openQuestions.length > 0 ? (
        <JennyQuestionInbox
          questions={openQuestions}
          title="Questions"
          description="Answer only the focused clarifications Jenny still needs."
        />
      ) : null}
    </div>
  )
}
