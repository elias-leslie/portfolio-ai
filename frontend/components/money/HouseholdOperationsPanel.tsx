'use client'

import { useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { useAnswerHouseholdQuestion } from '@/lib/hooks/useHousehold'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return '—'
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function HouseholdOperationsPanel({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const answerQuestion = useAnswerHouseholdQuestion()
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <SectionCard
        variant="surface"
        title="Operational Queue"
        description="Handle the next household actions instead of just reading summaries."
      >
        <div className="space-y-4">
          {dashboard.questions.length > 0 ? (
            dashboard.questions.slice(0, 3).map((question) => (
              <div
                key={question.id}
                className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4"
              >
                <p className="text-sm font-semibold text-text">{question.question}</p>
                {question.recommendation ? (
                  <p className="mt-2 text-sm text-text-muted">{question.recommendation}</p>
                ) : null}
                <div className="mt-4 flex flex-col gap-3 md:flex-row">
                  <Input
                    value={drafts[question.id] ?? ''}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [question.id]: event.target.value,
                      }))
                    }
                    placeholder="Answer briefly so Jenny can use it now"
                  />
                  <Button
                    disabled={
                      answerQuestion.isPending || !(drafts[question.id] ?? '').trim()
                    }
                    onClick={() =>
                      answerQuestion.mutate({
                        questionId: question.id,
                        answerText: (drafts[question.id] ?? '').trim(),
                      })
                    }
                  >
                    Save Answer
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
              Jenny does not need any follow-up answers right now.
            </div>
          )}

          <div className="grid gap-3">
            {dashboard.actionItems.map((item) => (
              <div
                key={`${item.title}-${item.detail}`}
                className="rounded-2xl border border-border/50 bg-surface/50 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">{item.title}</p>
                    <p className="mt-1 text-sm text-text-muted">{item.detail}</p>
                  </div>
                  <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-primary">
                    {item.priority}
                  </span>
                </div>
                <p className="mt-3 text-sm text-text">{item.actionLabel}</p>
              </div>
            ))}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Budget Tracker"
        description={dashboard.budgetSnapshot.summary}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Income Target
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrency(dashboard.budgetSnapshot.monthlyIncomeTarget)}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Monthly Plan
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrency(dashboard.budgetSnapshot.monthlyPlanTotal)}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Essential Spend
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrency(dashboard.budgetSnapshot.actualEssentialMonthlySpend)}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              Target {formatCurrency(dashboard.budgetSnapshot.essentialTarget)}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Discretionary Spend
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrency(dashboard.budgetSnapshot.actualDiscretionaryMonthlySpend)}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              Headroom {formatCurrency(dashboard.budgetSnapshot.discretionaryHeadroom)}
            </p>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}
