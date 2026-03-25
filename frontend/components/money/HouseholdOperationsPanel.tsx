'use client'

import { useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import { useAskJenny } from '@/lib/hooks/useHousehold'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { formatCurrency } from '@/lib/formatters'
import { JennyChatPanel } from './JennyChatPanel'
import { JennyNeedCard } from './JennyNeedCard'
import { JennyQuestionInbox } from './JennyQuestionInbox'

function AskJennyCard() {
  const askJenny = useAskJenny()
  const [askDraft, setAskDraft] = useState('')

  return (
    <SectionCard
      variant="surface"
      title="Create household follow-up"
      description="Use this when you want Jenny to open or track a household planning follow-up, not for portfolio chat."
      padding="sm"
    >
      <div className="flex flex-col gap-3 md:flex-row">
        <Input
          value={askDraft}
          onChange={(e) => setAskDraft(e.target.value)}
          placeholder="Create a household follow-up for Jenny..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && askDraft.trim() && !askJenny.isPending) {
              askJenny.mutate(askDraft.trim(), { onSuccess: () => setAskDraft('') })
            }
          }}
        />
        <Button
          disabled={askJenny.isPending || !askDraft.trim()}
          onClick={() =>
            askJenny.mutate(askDraft.trim(), { onSuccess: () => setAskDraft('') })
          }
        >
          Ask
        </Button>
      </div>
    </SectionCard>
  )
}

export function HouseholdOperationsPanel({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const paceTone =
    dashboard.budgetSnapshot.paceStatus === 'running_hot'
      ? 'border-warning/30 bg-warning/10'
      : dashboard.budgetSnapshot.paceStatus === 'under_plan'
        ? 'border-gain/30 bg-gain/10'
        : 'border-border/40 bg-surface-muted/20'

  const unsatisfiedNeeds = dashboard.jennyNeeds.filter(
    (n) => n.status === 'unsatisfied',
  )
  const openQuestions = dashboard.questions.filter((question) => !question.answeredAt)

  return (
    <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
      <div className="order-2 space-y-6 xl:order-1">
        <SectionCard
          variant="surface"
          title="What Jenny Needs"
          description={
            unsatisfiedNeeds.length > 0
              ? `${unsatisfiedNeeds.length} thing${unsatisfiedNeeds.length === 1 ? '' : 's'} to move forward.`
              : 'Nothing needed — Jenny has everything she needs.'
          }
        >
          <div className="space-y-4">
            {unsatisfiedNeeds.length === 0 ? (
              <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
                Nothing needed — Jenny has everything she needs.
              </div>
            ) : (
              unsatisfiedNeeds.map((need) => (
                <JennyNeedCard
                  key={need.id}
                  need={need}
                  dashboard={dashboard}
                />
              ))
            )}
          </div>
        </SectionCard>

        {openQuestions.length > 0 ? (
          <JennyQuestionInbox
            questions={dashboard.questions}
            title="Questions for You"
            description="These are the few clarifications Jenny still needs before she can move the money system forward."
          />
        ) : null}
        <SectionCard
          variant="surface"
          title="Budget Tracker"
          description={dashboard.budgetSnapshot.summary}
        >
          <div className={cn('rounded-2xl border p-4', paceTone)}>
            <p className="text-sm font-semibold text-text">Mid-month pacing</p>
            <p className="mt-2 text-sm text-text-muted">
              {dashboard.budgetSnapshot.paceDetail}
            </p>
            <p className="mt-3 text-xs uppercase tracking-wide text-text-muted">
              {formatCurrency(dashboard.budgetSnapshot.monthToDateSpend, { decimals: 0, nullDisplay: 'Not set' })} spent so
              far
              {dashboard.budgetSnapshot.monthToDatePlan
                ? ` · pace target ${formatCurrency(dashboard.budgetSnapshot.monthToDatePlan, { decimals: 0, nullDisplay: 'Not set' })}`
                : ''}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Income Target
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
                {formatCurrency(dashboard.budgetSnapshot.monthlyIncomeTarget, { decimals: 0, nullDisplay: 'Not set' })}
              </p>
            </div>
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Monthly Plan
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
                {formatCurrency(dashboard.budgetSnapshot.monthlyPlanTotal, { decimals: 0, nullDisplay: 'Not set' })}
              </p>
            </div>
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Essential Spend
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
                {formatCurrency(
                  dashboard.budgetSnapshot.actualEssentialMonthlySpend,
                  { decimals: 0, nullDisplay: 'Not set' },
                )}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                Target{' '}
                {formatCurrency(dashboard.budgetSnapshot.essentialTarget, { decimals: 0, nullDisplay: 'Not set' })}
              </p>
            </div>
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Discretionary Spend
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
                {formatCurrency(
                  dashboard.budgetSnapshot.actualDiscretionaryMonthlySpend,
                  { decimals: 0, nullDisplay: 'Not set' },
                )}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                Headroom{' '}
                {formatCurrency(dashboard.budgetSnapshot.discretionaryHeadroom, { decimals: 0, nullDisplay: 'Not set' })}
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-3">
            <div>
              <p className="text-sm font-semibold text-text">
                Recurring bills and subscriptions
              </p>
              <p className="mt-1 text-sm text-text-muted">
                The steady commitments Jenny can now pace against the monthly plan.
              </p>
            </div>
            {dashboard.recurringCommitments.length === 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
                Jenny is processing your documents to detect recurring
                commitments.
              </div>
            ) : (
              dashboard.recurringCommitments.slice(0, 4).map((commitment) => (
                <div
                  key={`${commitment.merchant}-${commitment.cadence}`}
                  className="rounded-2xl border border-border/40 bg-surface/60 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-text">
                        {commitment.merchant}
                      </p>
                      <p className="mt-1 text-sm text-text-muted">
                        {commitment.category} · {commitment.cadence}
                      </p>
                      <p className="mt-2 text-xs uppercase tracking-wide text-text-muted">
                        {commitment.dueStatus.replaceAll('_', ' ')} ·{' '}
                        {(commitment.dueConfidence * 100).toFixed(0)}% confidence
                      </p>
                    </div>
                    <div className="text-right text-sm">
                      <p className="font-semibold text-text">
                        {formatCurrency(commitment.averageAmount, { decimals: 0, nullDisplay: 'Not set' })}
                      </p>
                      <p className="text-text-muted">
                        {formatCurrency(commitment.annualizedCost, { decimals: 0, nullDisplay: 'Not set' })} / year
                      </p>
                      {commitment.daysUntilDue !== null ? (
                        <p className="text-text-muted">
                          {commitment.daysUntilDue < 0
                            ? `${Math.abs(commitment.daysUntilDue)} days overdue`
                            : `Due in ${commitment.daysUntilDue} days`}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>

      <div className="order-1 space-y-6 xl:order-2 xl:sticky xl:top-40 xl:self-start">
        <SectionCard
          variant="surface"
          title="Jenny Desk"
          description="Keep the live conversation and the blocking work in one place."
          padding="sm"
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Unsatisfied needs
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
                {unsatisfiedNeeds.length}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                Immediate actions Jenny is waiting on.
              </p>
            </div>
            <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Open questions
              </p>
              <p className="mt-2 text-2xl font-semibold tabular-nums text-text">
                {openQuestions.length}
              </p>
              <p className="mt-1 text-sm text-text-muted">
                Clarifications that still need your answer.
              </p>
            </div>
          </div>
        </SectionCard>

        <JennyChatPanel
          title="Chat with Jenny"
          description="Portfolio chat, household answers, and live follow-through without leaving the operate view."
        />

        <AskJennyCard />
      </div>
    </div>
  )
}
