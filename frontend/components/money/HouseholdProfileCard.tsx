'use client'

import { useEffect, useState } from 'react'
import type {
  HouseholdProfile,
  HouseholdQuestion,
  HouseholdResolvedValue,
} from '@/lib/api/household'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAnswerHouseholdQuestion, useUpdateHouseholdProfile } from '@/lib/hooks/useHousehold'
import { formatCurrency, formatEnumLabel } from './formatters'
import {
  formatResolvedValue,
  getQuestionSourceDocument,
  numberInput,
  parseNullableNumber,
  questionSourceLabel,
} from './household-profile-utils'

function badgeVariantForStatus(status: string) {
  switch (status) {
    case 'confirmed':
      return 'success' as const
    case 'inferred':
      return 'warning' as const
    case 'missing':
      return 'outline' as const
    default:
      return 'secondary' as const
  }
}

export function HouseholdProfileCard({
  profile,
  resolvedValues,
  questions,
}: {
  profile: HouseholdProfile
  resolvedValues: HouseholdResolvedValue[]
  questions: HouseholdQuestion[]
}) {
  const updateProfile = useUpdateHouseholdProfile()
  const answerQuestion = useAnswerHouseholdQuestion()
  const [householdName, setHouseholdName] = useState(profile.householdName)
  const [monthlyNetIncomeTarget, setMonthlyNetIncomeTarget] = useState(
    numberInput(profile.monthlyNetIncomeTarget),
  )
  const [monthlyEssentialTarget, setMonthlyEssentialTarget] = useState(
    numberInput(profile.monthlyEssentialTarget),
  )
  const [monthlyDiscretionaryTarget, setMonthlyDiscretionaryTarget] = useState(
    numberInput(profile.monthlyDiscretionaryTarget),
  )
  const [monthlySavingsTarget, setMonthlySavingsTarget] = useState(
    numberInput(profile.monthlySavingsTarget),
  )
  const [targetRetirementAge, setTargetRetirementAge] = useState(
    numberInput(profile.targetRetirementAge),
  )
  const [targetRetirementSpend, setTargetRetirementSpend] = useState(
    numberInput(profile.targetRetirementSpend),
  )
  const [notes, setNotes] = useState(profile.notes ?? '')
  const [answers, setAnswers] = useState<Record<string, string>>({})

  useEffect(() => {
    setHouseholdName(profile.householdName)
    setMonthlyNetIncomeTarget(numberInput(profile.monthlyNetIncomeTarget))
    setMonthlyEssentialTarget(numberInput(profile.monthlyEssentialTarget))
    setMonthlyDiscretionaryTarget(numberInput(profile.monthlyDiscretionaryTarget))
    setMonthlySavingsTarget(numberInput(profile.monthlySavingsTarget))
    setTargetRetirementAge(numberInput(profile.targetRetirementAge))
    setTargetRetirementSpend(numberInput(profile.targetRetirementSpend))
    setNotes(profile.notes ?? '')
  }, [profile])

  const handleSubmit = () => {
    updateProfile.mutate({
      householdName: householdName.trim(),
      monthlyNetIncomeTarget: parseNullableNumber(monthlyNetIncomeTarget),
      monthlyEssentialTarget: parseNullableNumber(monthlyEssentialTarget),
      monthlyDiscretionaryTarget: parseNullableNumber(monthlyDiscretionaryTarget),
      monthlySavingsTarget: parseNullableNumber(monthlySavingsTarget),
      targetRetirementAge: parseNullableNumber(targetRetirementAge),
      targetRetirementSpend: parseNullableNumber(targetRetirementSpend),
      notes: notes.trim() || null,
    })
  }

  return (
    <SectionCard
      variant="surface"
      title="Jenny Household Plan"
      description="Jenny should infer most of this from your documents. Use manual overrides only when you want to steer or confirm the plan directly."
      actions={
        <Button
          onClick={handleSubmit}
          disabled={updateProfile.isPending}
          aria-busy={updateProfile.isPending}
        >
          {updateProfile.isPending ? 'Saving...' : 'Save Overrides'}
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="grid gap-4 xl:grid-cols-3">
          {resolvedValues.length === 0 ? (
            <div className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4 text-sm text-text-muted xl:col-span-3">
              Jenny has not resolved any structured planning values yet. Upload documents or set an override to start building the household plan.
            </div>
          ) : (
            resolvedValues.map((value) => (
              <div key={value.fieldName} className="rounded-2xl border border-border/50 bg-surface-muted/20 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-text">{value.label}</p>
                    <p className="mt-2 text-base font-semibold text-text">
                      {formatResolvedValue(value)}
                    </p>
                  </div>
                  <Badge variant={badgeVariantForStatus(value.status)}>{formatEnumLabel(value.status)}</Badge>
                </div>
                <div className="mt-3 space-y-2 text-sm text-text-muted">
                  <p>
                    Source:{' '}
                    {value.source === 'jenny_inference'
                      ? 'Jenny estimate'
                      : value.source === 'manual'
                        ? 'Confirmed override'
                        : 'Pending'}
                  </p>
                  {value.confidence != null ? (
                    <p>Confidence: {Math.round(value.confidence * 100)}%</p>
                  ) : null}
                  {value.rationale ? <p>{value.rationale}</p> : null}
                  {value.question ? <p>Needs confirmation: {value.question}</p> : null}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-text">Jenny follow-up questions</p>
              <p className="mt-1 text-sm text-text-muted">
                Answer only the gaps Jenny cannot infer confidently from your statements, receipts, and screenshots.
              </p>
            </div>
            <Badge variant={questions.length > 0 ? 'warning' : 'success'}>
              {questions.length > 0 ? `${questions.length} open` : 'No open questions'}
            </Badge>
          </div>
          <div className="mt-4 space-y-4">
            {questions.length === 0 ? (
              <div className="rounded-2xl border border-border/40 bg-surface/70 px-4 py-3 text-sm text-text-muted">
                Jenny has enough confirmed information for now. Keep uploading fresh documents and she will reopen the queue only when confidence drops.
              </div>
            ) : (
              questions.map((question) => {
                const sourceDocument = getQuestionSourceDocument(question)
                return (
                  <div
                    key={question.id}
                    className="rounded-2xl border border-border/40 bg-surface/80 p-4"
                  >
                    <div className="mb-3 rounded-xl border border-border/40 bg-surface-muted/30 px-3 py-2 text-xs text-text-muted">
                      <p className="font-medium text-text">Source: {questionSourceLabel(question)}</p>
                      {sourceDocument?.filename ? (
                        <p className="mt-1">File: {sourceDocument.filename}</p>
                      ) : null}
                      {sourceDocument?.reviewSummary ? (
                        <p className="mt-1">{sourceDocument.reviewSummary}</p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-text">{question.question}</p>
                      <Badge variant={question.priority === 'high' ? 'warning' : 'secondary'}>
                        {question.priority}
                      </Badge>
                    </div>
                    {question.rationale ? (
                      <p className="mt-2 text-sm text-text-muted">{question.rationale}</p>
                    ) : null}
                    {question.recommendation ? (
                      <div className="mt-3 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-text">
                        <span className="font-semibold">Jenny recommends:</span>{' '}
                        {question.recommendation}
                      </div>
                    ) : null}
                    <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                      <Input
                        value={answers[question.id] ?? ''}
                        onChange={(event) =>
                          setAnswers((current) => ({
                            ...current,
                            [question.id]: event.target.value,
                          }))
                        }
                        placeholder="Answer briefly so Jenny can confirm the plan"
                      />
                      <Button
                        onClick={() =>
                          answerQuestion.mutate({
                            questionId: question.id,
                            answerText: (answers[question.id] ?? '').trim(),
                          })
                        }
                        disabled={
                          answerQuestion.isPending || !(answers[question.id] ?? '').trim()
                        }
                      >
                        Confirm
                      </Button>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label htmlFor="household-name">Household name</Label>
              <Input
                id="household-name"
                value={householdName}
                onChange={(event) => setHouseholdName(event.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="monthly-income">Monthly take-home income</Label>
              <Input
                id="monthly-income"
                inputMode="decimal"
                value={monthlyNetIncomeTarget}
                onChange={(event) => setMonthlyNetIncomeTarget(event.target.value)}
                placeholder="12500"
              />
            </div>
            <div>
              <Label htmlFor="monthly-essential">Essential budget</Label>
              <Input
                id="monthly-essential"
                inputMode="decimal"
                value={monthlyEssentialTarget}
                onChange={(event) => setMonthlyEssentialTarget(event.target.value)}
                placeholder="5200"
              />
            </div>
            <div>
              <Label htmlFor="monthly-discretionary">Discretionary budget</Label>
              <Input
                id="monthly-discretionary"
                inputMode="decimal"
                value={monthlyDiscretionaryTarget}
                onChange={(event) => setMonthlyDiscretionaryTarget(event.target.value)}
                placeholder="1800"
              />
            </div>
            <div>
              <Label htmlFor="monthly-savings">Monthly savings target</Label>
              <Input
                id="monthly-savings"
                inputMode="decimal"
                value={monthlySavingsTarget}
                onChange={(event) => setMonthlySavingsTarget(event.target.value)}
                placeholder="2600"
              />
            </div>
            <div>
              <Label htmlFor="retirement-age">Target retirement age</Label>
              <Input
                id="retirement-age"
                inputMode="numeric"
                value={targetRetirementAge}
                onChange={(event) => setTargetRetirementAge(event.target.value)}
                placeholder="60"
              />
            </div>
            <div>
              <Label htmlFor="retirement-spend">Target monthly retirement spend</Label>
              <Input
                id="retirement-spend"
                inputMode="decimal"
                value={targetRetirementSpend}
                onChange={(event) => setTargetRetirementSpend(event.target.value)}
                placeholder="9000"
              />
            </div>
          </div>

          <div className="rounded-2xl border border-border/50 bg-surface-muted/30 p-5">
            <p className="text-sm font-semibold text-text">Manual overrides</p>
            <div className="mt-4 space-y-3 text-sm text-text-muted">
              <p>Income: {formatCurrency(parseNullableNumber(monthlyNetIncomeTarget))}</p>
              <p>Essentials: {formatCurrency(parseNullableNumber(monthlyEssentialTarget))}</p>
              <p>
                Flexible spend: {formatCurrency(parseNullableNumber(monthlyDiscretionaryTarget))}
              </p>
              <p>Savings: {formatCurrency(parseNullableNumber(monthlySavingsTarget))}</p>
              <p>
                Retirement: age {parseNullableNumber(targetRetirementAge) ?? 'Not set'} /{' '}
                {formatCurrency(parseNullableNumber(targetRetirementSpend))}
              </p>
            </div>
            <div className="mt-5">
              <Label htmlFor="household-notes">Notes</Label>
              <Textarea
                id="household-notes"
                className="mt-2 min-h-32"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Travel goals, one-time expenses, pension assumptions, healthcare concerns..."
              />
            </div>
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
