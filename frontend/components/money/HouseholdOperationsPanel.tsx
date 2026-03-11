'use client'

import Link from 'next/link'
import { useState } from 'react'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import {
  useAnswerHouseholdQuestion,
  useCategorizeHouseholdTransaction,
} from '@/lib/hooks/useHousehold'
import { Badge } from '@/components/ui/badge'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatCurrency } from './formatters'

const HOUSEHOLD_CATEGORY_OPTIONS = [
  'Bills',
  'Dining',
  'Gas',
  'Groceries',
  'Household',
  'Income',
  'Retail',
  'Subscriptions',
  'Transfers',
] as const

const ESSENTIALITY_OPTIONS = ['essential', 'discretionary', 'mixed'] as const

export function HouseholdOperationsPanel({
  dashboard,
}: {
  dashboard: HouseholdFinanceDashboard
}) {
  const answerQuestion = useAnswerHouseholdQuestion()
  const categorizeTransaction = useCategorizeHouseholdTransaction()
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [categorizationDrafts, setCategorizationDrafts] = useState<
    Record<string, { category: string; essentiality: string }>
  >({})

  const paceTone =
    dashboard.budgetSnapshot.paceStatus === 'running_hot'
      ? 'border-warning/30 bg-warning/10'
      : dashboard.budgetSnapshot.paceStatus === 'under_plan'
        ? 'border-gain/30 bg-gain/10'
        : 'border-border/40 bg-surface-muted/20'

  return (
    <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <SectionCard
        variant="surface"
        title="Operational Queue"
        description="Handle the next household actions instead of just reading summaries."
      >
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">
              {dashboard.questions.length} open question{dashboard.questions.length === 1 ? '' : 's'}
            </Badge>
            <Badge variant="outline">
              {dashboard.actionItems.length} action item{dashboard.actionItems.length === 1 ? '' : 's'}
            </Badge>
            <Badge variant="outline">
              {dashboard.categorizationQueue.length} categorization follow-up
              {dashboard.categorizationQueue.length === 1 ? '' : 's'}
            </Badge>
          </div>

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
          {dashboard.questions.length > 3 ? (
            <p className="text-xs text-text-muted">
              {dashboard.questions.length - 3} more question
              {dashboard.questions.length - 3 === 1 ? '' : 's'} remain after this first batch.
            </p>
          ) : null}

          <div className="grid gap-3">
            {dashboard.actionItems.length === 0 ? (
              <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
                No additional operator actions are waiting right now.
              </div>
            ) : (
              dashboard.actionItems.slice(0, 4).map((item) => (
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
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button asChild size="sm" variant="outline">
                      <Link href={item.href}>{item.actionLabel}</Link>
                    </Button>
                    <span className="text-xs text-text-muted">{item.source}</span>
                  </div>
                </div>
              ))
            )}
          </div>
          {dashboard.actionItems.length > 4 ? (
            <p className="text-xs text-text-muted">
              {dashboard.actionItems.length - 4} more action item
              {dashboard.actionItems.length - 4 === 1 ? '' : 's'} are waiting behind these.
            </p>
          ) : null}

          <div className="space-y-3 rounded-2xl border border-border/40 bg-surface/40 p-4">
            <div>
              <p className="text-sm font-semibold text-text">Categorization review</p>
              <p className="mt-1 text-sm text-text-muted">
                Confirm low-confidence spend rows so the budget and merchant insights stop drifting.
              </p>
            </div>
            {dashboard.categorizationQueue.length === 0 ? (
              <div className="rounded-2xl border border-gain/30 bg-gain/10 p-4 text-sm text-text-muted">
                No categorization follow-ups are waiting right now.
              </div>
            ) : (
              dashboard.categorizationQueue.slice(0, 4).map((candidate) => (
                <div
                  key={candidate.id}
                  className="rounded-2xl border border-border/40 bg-surface/80 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-text">{candidate.merchant}</p>
                      <p className="mt-1 text-sm text-text-muted">{candidate.description}</p>
                    </div>
                    <span className="text-sm font-semibold text-text">
                      {formatCurrency(candidate.amount)}
                    </span>
                  </div>
                  <p className="mt-3 text-xs uppercase tracking-wide text-text-muted">
                    {candidate.currentCategory} / {candidate.currentEssentiality} {'->'}{' '}
                    {candidate.suggestedCategory} / {candidate.suggestedEssentiality}
                  </p>
                  <p className="mt-2 text-sm text-text-muted">{candidate.reason}</p>
                  {candidate.similarTransactionCount > 0 ? (
                    <p className="mt-2 text-xs text-text-muted">
                      {candidate.similarTransactionCount} similar transaction
                      {candidate.similarTransactionCount === 1 ? '' : 's'} can be updated with the same rule.
                    </p>
                  ) : null}
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    <Select
                      value={
                        categorizationDrafts[candidate.id]?.category ??
                        candidate.suggestedCategory
                      }
                      onValueChange={(value) =>
                        setCategorizationDrafts((current) => ({
                          ...current,
                          [candidate.id]: {
                            category: value,
                            essentiality:
                              current[candidate.id]?.essentiality ??
                              candidate.suggestedEssentiality,
                          },
                        }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Category" />
                      </SelectTrigger>
                      <SelectContent>
                        {HOUSEHOLD_CATEGORY_OPTIONS.map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={
                        categorizationDrafts[candidate.id]?.essentiality ??
                        candidate.suggestedEssentiality
                      }
                      onValueChange={(value) =>
                        setCategorizationDrafts((current) => ({
                          ...current,
                          [candidate.id]: {
                            category:
                              current[candidate.id]?.category ??
                              candidate.suggestedCategory,
                            essentiality: value,
                          },
                        }))
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Essentiality" />
                      </SelectTrigger>
                      <SelectContent>
                        {ESSENTIALITY_OPTIONS.map((option) => (
                          <SelectItem key={option} value={option}>
                            {option}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() =>
                        categorizeTransaction.mutate({
                          transactionId: candidate.id,
                          category:
                            categorizationDrafts[candidate.id]?.category ??
                            candidate.suggestedCategory,
                          essentiality:
                            categorizationDrafts[candidate.id]?.essentiality ??
                            candidate.suggestedEssentiality,
                        })
                      }
                      disabled={categorizeTransaction.isPending}
                      aria-busy={categorizeTransaction.isPending}
                    >
                      Save this row
                    </Button>
                    {candidate.similarTransactionCount > 0 ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          categorizeTransaction.mutate({
                            transactionId: candidate.id,
                            category:
                              categorizationDrafts[candidate.id]?.category ??
                              candidate.suggestedCategory,
                            essentiality:
                              categorizationDrafts[candidate.id]?.essentiality ??
                              candidate.suggestedEssentiality,
                            applyToMerchant: true,
                          })
                        }
                        disabled={categorizeTransaction.isPending}
                        aria-busy={categorizeTransaction.isPending}
                      >
                        Apply to similar
                      </Button>
                    ) : null}
                    <span className="text-xs text-text-muted">
                      {(candidate.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                </div>
              ))
            )}
            {dashboard.categorizationQueue.length > 4 ? (
              <p className="text-xs text-text-muted">
                {dashboard.categorizationQueue.length - 4} more low-confidence transaction
                {dashboard.categorizationQueue.length - 4 === 1 ? '' : 's'} remain after these.
              </p>
            ) : null}
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Budget Tracker"
        description={dashboard.budgetSnapshot.summary}
      >
        <div className={`rounded-2xl border p-4 ${paceTone}`}>
          <p className="text-sm font-semibold text-text">Mid-month pacing</p>
          <p className="mt-2 text-sm text-text-muted">{dashboard.budgetSnapshot.paceDetail}</p>
          <p className="mt-3 text-xs uppercase tracking-wide text-text-muted">
            {formatCurrency(dashboard.budgetSnapshot.monthToDateSpend)} spent so far
            {dashboard.budgetSnapshot.monthToDatePlan
              ? ` · pace target ${formatCurrency(dashboard.budgetSnapshot.monthToDatePlan)}`
              : ''}
          </p>
        </div>

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

        <div className="mt-6 space-y-3">
          <div>
            <p className="text-sm font-semibold text-text">Recurring bills and subscriptions</p>
            <p className="mt-1 text-sm text-text-muted">
              The steady commitments Jenny can now pace against the monthly plan.
            </p>
          </div>
          {dashboard.recurringCommitments.length === 0 ? (
            <div className="rounded-2xl border border-border/40 bg-surface/60 p-4 text-sm text-text-muted">
              Jenny needs more statement coverage before recurring commitments can be trusted.
            </div>
          ) : (
            dashboard.recurringCommitments.slice(0, 4).map((commitment) => (
              <div
                key={`${commitment.merchant}-${commitment.cadence}`}
                className="rounded-2xl border border-border/40 bg-surface/60 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">{commitment.merchant}</p>
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
                      {formatCurrency(commitment.averageAmount)}
                    </p>
                    <p className="text-text-muted">
                      {formatCurrency(commitment.annualizedCost)} / year
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
  )
}
