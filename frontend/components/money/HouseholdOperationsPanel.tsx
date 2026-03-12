'use client'

import Link from 'next/link'
import { useState } from 'react'
import type {
  HouseholdFinanceDashboard,
  JennyNeed,
} from '@/lib/api/household'
import {
  useAnswerHouseholdQuestion,
  useAskJenny,
  useCategorizeHouseholdTransaction,
  useConfirmFact,
  useUpdateHouseholdProfile,
} from '@/lib/hooks/useHousehold'
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
import { JennyChatPanel } from './JennyChatPanel'
import { JennyQuestionInbox } from './JennyQuestionInbox'

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

function JennyNeedCard({
  need,
  dashboard,
}: {
  need: JennyNeed
  dashboard: HouseholdFinanceDashboard
}) {
  const confirmFact = useConfirmFact()
  const updateProfile = useUpdateHouseholdProfile()
  const categorizeTransaction = useCategorizeHouseholdTransaction()
  const answerQuestion = useAnswerHouseholdQuestion()
  const [draft, setDraft] = useState('')
  const [categorizationDrafts, setCategorizationDrafts] = useState<
    Record<string, { category: string; essentiality: string }>
  >({})

  const priorityColor =
    need.priority === 'critical'
      ? 'border-loss/30 bg-loss/10'
      : need.priority === 'high'
        ? 'border-warning/30 bg-warning/10'
        : 'border-border/50 bg-surface-muted/20'

  // Provide type: link to intake
  if (need.needType === 'provide') {
    return (
      <div className={`rounded-2xl border p-4 ${priorityColor}`}>
        <p className="text-sm font-semibold text-text">{need.title}</p>
        <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
        {need.actionHref ? (
          <div className="mt-3">
            <Button asChild size="sm" variant="outline">
              <Link href={need.actionHref}>Go to Intake</Link>
            </Button>
          </div>
        ) : null}
      </div>
    )
  }

  // Confirm type: fact confirmation or routed question
  if (need.needType === 'confirm') {
    if (need.relatedQuestionId) {
      const question = dashboard.questions.find(
        (q) => q.id === need.relatedQuestionId,
      )
      const format = need.questionFormat ?? question?.questionFormat ?? 'short_text'
      const options = need.options ?? question?.options ?? []

      return (
        <div className={`rounded-2xl border p-4 ${priorityColor}`}>
          <p className="text-sm font-semibold text-text">{need.title}</p>
          <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
          {question?.recommendation ? (
            <p className="mt-2 text-xs text-text-muted">
              {question.recommendation}
            </p>
          ) : null}

          {format === 'boolean' || format === 'yes_no' ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                onClick={() =>
                  answerQuestion.mutate({
                    questionId: need.relatedQuestionId!,
                    answerText: 'yes',
                  })
                }
                disabled={answerQuestion.isPending}
              >
                Yes
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  answerQuestion.mutate({
                    questionId: need.relatedQuestionId!,
                    answerText: 'no',
                  })
                }
                disabled={answerQuestion.isPending}
              >
                No
              </Button>
            </div>
          ) : format === 'single_select' || format === 'multiple_choice' ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {options.map((option) => (
                <Button
                  key={option}
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    answerQuestion.mutate({
                      questionId: need.relatedQuestionId!,
                      answerText: option,
                    })
                  }
                  disabled={answerQuestion.isPending}
                >
                  {option}
                </Button>
              ))}
            </div>
          ) : (
            <div className="mt-3 flex flex-col gap-3 md:flex-row">
              <Input
                type={format === 'integer' || format === 'currency' || format === 'number' ? 'number' : 'text'}
                step={format === 'currency' ? '0.01' : undefined}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={
                  format === 'integer' ? 'e.g. 65' : format === 'currency' ? 'e.g. 5000' : 'Your answer'
                }
              />
              <Button
                size="sm"
                disabled={answerQuestion.isPending || !draft.trim()}
                onClick={() =>
                  answerQuestion.mutate(
                    {
                      questionId: need.relatedQuestionId!,
                      answerText: draft.trim(),
                    },
                    { onSuccess: () => setDraft('') },
                  )
                }
              >
                Confirm
              </Button>
            </div>
          )}
        </div>
      )
    }

    // Fact confirmation (yes/no)
    return (
      <div className={`rounded-2xl border p-4 ${priorityColor}`}>
        <p className="text-sm font-semibold text-text">{need.title}</p>
        <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
        <div className="mt-3 flex flex-col gap-3 md:flex-row">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Your answer"
          />
          <Button
            disabled={confirmFact.isPending || !draft.trim()}
            onClick={() =>
              confirmFact.mutate(
                {
                  factKey: need.fieldName ?? need.id,
                  factValue: draft.trim(),
                },
                { onSuccess: () => setDraft('') },
              )
            }
          >
            Confirm
          </Button>
        </div>
      </div>
    )
  }

  // Set type: profile field input
  if (need.needType === 'set') {
    return (
      <div className={`rounded-2xl border p-4 ${priorityColor}`}>
        <p className="text-sm font-semibold text-text">{need.title}</p>
        <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
        <div className="mt-3 flex flex-col gap-3 md:flex-row">
          <Input
            type="number"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={
              need.fieldName === 'target_retirement_age'
                ? 'e.g. 65'
                : 'e.g. 5000'
            }
          />
          <Button
            disabled={updateProfile.isPending || !draft.trim()}
            onClick={() => {
              if (!need.fieldName) return
              const value = Number(draft)
              if (Number.isNaN(value)) return
              const payload: Record<string, number> = {}
              // Convert snake_case field to camelCase for the API
              const camelKey = need.fieldName.replace(/_([a-z])/g, (_, c: string) =>
                c.toUpperCase(),
              )
              payload[camelKey] = value
              updateProfile.mutate(payload, { onSuccess: () => setDraft('') })
            }}
          >
            Save
          </Button>
        </div>
      </div>
    )
  }

  // Review type: inline categorization
  if (need.needType === 'review') {
    return (
      <div className={`rounded-2xl border p-4 ${priorityColor}`}>
        <p className="text-sm font-semibold text-text">{need.title}</p>
        <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
        {dashboard.categorizationQueue.length > 0 ? (
          <div className="mt-3 space-y-3">
            {dashboard.categorizationQueue.slice(0, 4).map((candidate) => (
              <div
                key={candidate.id}
                className="rounded-2xl border border-border/40 bg-surface/80 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {candidate.merchant}
                    </p>
                    <p className="mt-1 text-sm text-text-muted">
                      {candidate.description}
                    </p>
                  </div>
                  <span className="text-sm font-semibold text-text">
                    {formatCurrency(candidate.amount)}
                  </span>
                </div>
                <p className="mt-3 text-xs uppercase tracking-wide text-text-muted">
                  {candidate.currentCategory} / {candidate.currentEssentiality}{' '}
                  {'->'} {candidate.suggestedCategory} /{' '}
                  {candidate.suggestedEssentiality}
                </p>
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
                  >
                    Looks right
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
                    >
                      Apply to similar
                    </Button>
                  ) : null}
                  <span className="text-xs text-text-muted">
                    {(candidate.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  // Fallback
  return (
    <div className={`rounded-2xl border p-4 ${priorityColor}`}>
      <p className="text-sm font-semibold text-text">{need.title}</p>
      <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
    </div>
  )
}

function AskJennyCard() {
  const askJenny = useAskJenny()
  const [askDraft, setAskDraft] = useState('')

  return (
    <SectionCard
      variant="surface"
      title="Ask Jenny"
      description="Ask Jenny anything about your household finances, budget, or planning."
    >
      <div className="flex flex-col gap-3 md:flex-row">
        <Input
          value={askDraft}
          onChange={(e) => setAskDraft(e.target.value)}
          placeholder="Ask Jenny anything about your finances..."
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

  return (
    <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <div className="space-y-6">
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

        {dashboard.questions.length > 0 ? (
          <JennyQuestionInbox
            questions={dashboard.questions}
            title="Questions for You"
            description="These are the few clarifications Jenny still needs before she can move the money system forward."
          />
        ) : null}

        <JennyChatPanel />

        <AskJennyCard />
      </div>

      <SectionCard
        variant="surface"
        title="Budget Tracker"
        description={dashboard.budgetSnapshot.summary}
      >
        <div className={`rounded-2xl border p-4 ${paceTone}`}>
          <p className="text-sm font-semibold text-text">Mid-month pacing</p>
          <p className="mt-2 text-sm text-text-muted">
            {dashboard.budgetSnapshot.paceDetail}
          </p>
          <p className="mt-3 text-xs uppercase tracking-wide text-text-muted">
            {formatCurrency(dashboard.budgetSnapshot.monthToDateSpend)} spent so
            far
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
              {formatCurrency(
                dashboard.budgetSnapshot.actualEssentialMonthlySpend,
              )}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              Target{' '}
              {formatCurrency(dashboard.budgetSnapshot.essentialTarget)}
            </p>
          </div>
          <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Discretionary Spend
            </p>
            <p className="mt-2 text-2xl font-semibold text-text">
              {formatCurrency(
                dashboard.budgetSnapshot.actualDiscretionaryMonthlySpend,
              )}
            </p>
            <p className="mt-1 text-sm text-text-muted">
              Headroom{' '}
              {formatCurrency(dashboard.budgetSnapshot.discretionaryHeadroom)}
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
