'use client'

import Link from 'next/link'
import { useState } from 'react'
import type {
  HouseholdFinanceDashboard,
  HouseholdPlanningUpdate,
  JennyNeed,
} from '@/lib/api/household'
import {
  useAnswerHouseholdQuestion,
  useCategorizeHouseholdTransaction,
  useConfirmFact,
  useUpdateHouseholdPlanning,
  useUpdateHouseholdProfile,
} from '@/lib/hooks/useHousehold'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { formatCurrency } from '@/lib/formatters'

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
const QUICK_SAVE_NOTE = 'Added from What Jenny Needs quick save.'

function getPlanningSectionNeed(need: JennyNeed): string | null {
  return need.id.startsWith('need_planning_')
    ? need.id.slice('need_planning_'.length)
    : null
}

function stripPlanningItemMeta<T extends { createdAt: string; updatedAt: string }>(
  item: T,
): Omit<T, 'createdAt' | 'updatedAt'> {
  const { createdAt: _createdAt, updatedAt: _updatedAt, ...rest } = item
  return rest
}

function buildQuickPlanningPayload(
  section: string,
  value: number,
  planning: HouseholdFinanceDashboard['planning'] | null | undefined,
): HouseholdPlanningUpdate | null {
  switch (section) {
    case 'debt':
      return {
        debtObligations: [
          ...(planning?.debtObligations ?? []).map(stripPlanningItemMeta),
          {
            label: 'Household debt',
            debtType: 'other',
            monthlyPayment: value,
            notes: QUICK_SAVE_NOTE,
          },
        ],
      }
    case 'housing':
      return {
        housingCosts: [
          ...(planning?.housingCosts ?? []).map(stripPlanningItemMeta),
          {
            label: 'Primary housing',
            housingType: 'primary_residence',
            occupancyRole: 'primary',
            monthlyPayment: value,
            notes: QUICK_SAVE_NOTE,
          },
        ],
      }
    case 'insurance':
      return {
        insurancePolicies: [
          ...(planning?.insurancePolicies ?? []).map(stripPlanningItemMeta),
          {
            label: 'Primary insurance',
            coverageType: 'unknown',
            premiumMonthly: value,
            notes: QUICK_SAVE_NOTE,
          },
        ],
      }
    case 'retirement_income':
      return {
        retirementIncomeSources: [
          ...(planning?.retirementIncomeSources ?? []).map(stripPlanningItemMeta),
          {
            label: 'Retirement income',
            sourceType: 'other',
            monthlyAmount: value,
            notes: QUICK_SAVE_NOTE,
          },
        ],
      }
    case 'planned_expenses':
      return {
        plannedExpenses: [
          ...(planning?.plannedExpenses ?? []).map(stripPlanningItemMeta),
          {
            label: 'Major expense',
            expenseKind: 'major_expense',
            category: 'planned',
            targetAmount: value,
            priority: 'medium',
            notes: QUICK_SAVE_NOTE,
          },
        ],
      }
    case 'goal_buckets':
      return {
        plannedExpenses: [
          ...(planning?.plannedExpenses ?? []).map(stripPlanningItemMeta),
          {
            label: 'Goal bucket',
            expenseKind: 'goal_bucket',
            category: 'goal_bucket',
            monthlySavingTarget: value,
            priority: 'medium',
            notes: QUICK_SAVE_NOTE,
          },
        ],
      }
    default:
      return null
  }
}

function getSetNeedPlaceholder(need: JennyNeed, planningSection: string | null): string {
  if (need.fieldName === 'target_retirement_age') {
    return 'e.g. 65'
  }

  switch (planningSection) {
    case 'household':
      return 'e.g. 4'
    case 'income':
      return 'e.g. 8500'
    case 'taxes':
      return 'e.g. 24'
    default:
      return 'e.g. 5000'
  }
}

export interface JennyNeedCardProps {
  need: JennyNeed
  dashboard: HouseholdFinanceDashboard
}

export function JennyNeedCard({
  need,
  dashboard,
}: JennyNeedCardProps) {
  const confirmFact = useConfirmFact()
  const updateProfile = useUpdateHouseholdProfile()
  const updatePlanning = useUpdateHouseholdPlanning()
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
  const planningSection = getPlanningSectionNeed(need)

  // Provide type: link to intake
  if (need.needType === 'provide') {
    return (
      <div className={cn('rounded-2xl border p-4', priorityColor)}>
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
        <div className={cn('rounded-2xl border p-4', priorityColor)}>
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
      <div className={cn('rounded-2xl border p-4', priorityColor)}>
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
    const placeholder = getSetNeedPlaceholder(need, planningSection)
    const canSaveInline = Boolean(need.fieldName || planningSection)

    const saveSetNeed = () => {
      const value = Number(draft)
      if (Number.isNaN(value)) {
        return
      }

      if (need.fieldName) {
        const payload: Record<string, number> = {}
        const camelKey = need.fieldName.replace(/_([a-z])/g, (_, c: string) =>
          c.toUpperCase(),
        )
        payload[camelKey] = value
        updateProfile.mutate(payload, { onSuccess: () => setDraft('') })
        return
      }

      if (planningSection === 'household') {
        updateProfile.mutate(
          { adultCount: Math.max(1, Math.round(value)) },
          { onSuccess: () => setDraft('') },
        )
        return
      }

      if (planningSection === 'income') {
        updateProfile.mutate(
          { monthlyNetIncomeTarget: value },
          { onSuccess: () => setDraft('') },
        )
        return
      }

      if (planningSection === 'taxes') {
        updateProfile.mutate(
          { effectiveTaxRate: value },
          { onSuccess: () => setDraft('') },
        )
        return
      }

      const payload = planningSection
        ? buildQuickPlanningPayload(planningSection, value, dashboard.planning)
        : null
      if (!payload) {
        return
      }

      updatePlanning.mutate(payload, { onSuccess: () => setDraft('') })
    }

    return (
      <div className={cn('rounded-2xl border p-4', priorityColor)}>
        <p className="text-sm font-semibold text-text">{need.title}</p>
        <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
        {canSaveInline ? (
          <div className="mt-3 flex flex-col gap-3 md:flex-row">
            <Input
              type="number"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={placeholder}
            />
            <Button
              disabled={
                updateProfile.isPending ||
                updatePlanning.isPending ||
                !draft.trim()
              }
              onClick={saveSetNeed}
            >
              Save
            </Button>
            {need.actionHref ? (
              <Button asChild variant="outline">
                <Link href={need.actionHref}>Open Planning</Link>
              </Button>
            ) : null}
          </div>
        ) : need.actionHref ? (
          <div className="mt-3">
            <Button asChild size="sm" variant="outline">
              <Link href={need.actionHref}>Open Planning</Link>
            </Button>
          </div>
        ) : null}
      </div>
    )
  }

  // Review type: inline categorization
  if (need.needType === 'review') {
    return (
      <div className={cn('rounded-2xl border p-4', priorityColor)}>
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
                    {formatCurrency(candidate.amount, { decimals: 0, nullDisplay: 'Not set' })}
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
                    aria-label="Transaction category"
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
                    aria-label="Transaction essentiality"
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
    <div className={cn('rounded-2xl border p-4', priorityColor)}>
      <p className="text-sm font-semibold text-text">{need.title}</p>
      <p className="mt-1 text-sm text-text-muted">{need.detail}</p>
    </div>
  )
}
