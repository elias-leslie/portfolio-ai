'use client'

import { useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type { HouseholdQuestion } from '@/lib/api/household'
import { useAnswerHouseholdQuestion } from '@/lib/hooks/useHousehold'
import {
  getQuestionSourceDocument,
  questionSourceLabel,
} from './household-profile-utils'

function normalizeQuestionFormat(
  questionFormat: string | null | undefined,
): string {
  switch ((questionFormat ?? 'short_text').toLowerCase()) {
    case 'text':
      return 'short_text'
    case 'number':
      return 'integer'
    case 'yes_no':
      return 'boolean'
    case 'multiple_choice':
      return 'single_select'
    default:
      return (questionFormat ?? 'short_text').toLowerCase()
  }
}

export function JennyQuestionInbox({
  questions,
  title = 'Jenny Questions',
  description = 'Answer only the gaps Jenny cannot infer confidently from your documents and account activity.',
  selectedQuestionId = null,
}: {
  questions: HouseholdQuestion[]
  title?: string
  description?: string
  selectedQuestionId?: string | null
}) {
  const answerQuestion = useAnswerHouseholdQuestion()
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [multiSelectDrafts, setMultiSelectDrafts] = useState<
    Record<string, string[]>
  >({})

  const openQuestions = questions.filter(
    (question) =>
      question.status === 'open' &&
      (question.direction == null || question.direction === 'jenny_to_user'),
  )
  const orderedQuestions = openQuestions.slice().sort((left, right) => {
    if (selectedQuestionId && left.id === selectedQuestionId) return -1
    if (selectedQuestionId && right.id === selectedQuestionId) return 1
    return 0
  })

  const submitAnswer = (questionId: string, answerText: string) => {
    const trimmed = answerText.trim()
    if (!trimmed) {
      return
    }
    answerQuestion.mutate(
      { questionId, answerText: trimmed },
      {
        onSuccess: () => {
          setDrafts((current) => {
            const next = { ...current }
            delete next[questionId]
            return next
          })
          setMultiSelectDrafts((current) => {
            const next = { ...current }
            delete next[questionId]
            return next
          })
        },
      },
    )
  }

  return (
    <SectionCard
      variant="surface"
      title={title}
      description={description}
      actions={
        <Badge variant={openQuestions.length > 0 ? 'warning' : 'success'}>
          {openQuestions.length > 0
            ? `${openQuestions.length} open`
            : 'No open questions'}
        </Badge>
      }
    >
      <div className="space-y-4">
        {openQuestions.length === 0 ? (
          <div className="rounded-2xl border border-border/40 bg-surface/70 px-4 py-3 text-sm text-text-muted">
            Jenny has enough confirmed information for now. She will reopen the
            queue only when confidence drops.
          </div>
        ) : (
          orderedQuestions.map((question) => {
            const sourceDocument = getQuestionSourceDocument(question)
            const questionFormat = normalizeQuestionFormat(
              question.questionFormat,
            )
            const options = question.options ?? []

            return (
              <div
                key={question.id}
                className={`rounded-2xl border bg-surface/80 p-4 ${
                  selectedQuestionId === question.id
                    ? 'border-primary/50 ring-1 ring-primary/30'
                    : 'border-border/40'
                }`}
              >
                <div className="mb-3 rounded-xl border border-border/40 bg-surface-muted/30 px-3 py-2 text-xs text-text-muted">
                  <p className="font-medium text-text">
                    Source: {questionSourceLabel(question)}
                  </p>
                  {sourceDocument?.filename ? (
                    <p className="mt-1">File: {sourceDocument.filename}</p>
                  ) : null}
                  {sourceDocument?.reviewSummary ? (
                    <p className="mt-1">{sourceDocument.reviewSummary}</p>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-text">
                    {question.question}
                  </p>
                  <Badge
                    variant={
                      question.priority === 'high' ? 'warning' : 'secondary'
                    }
                  >
                    {question.priority}
                  </Badge>
                </div>

                {question.rationale ? (
                  <p className="mt-2 text-sm text-text-muted">
                    {question.rationale}
                  </p>
                ) : null}

                {question.recommendation ? (
                  <div className="mt-3 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-text">
                    <span className="font-semibold">Jenny recommends:</span>{' '}
                    {question.recommendation}
                  </div>
                ) : null}

                {questionFormat === 'boolean' ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      onClick={() => submitAnswer(question.id, 'yes')}
                      disabled={answerQuestion.isPending}
                    >
                      Yes
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => submitAnswer(question.id, 'no')}
                      disabled={answerQuestion.isPending}
                    >
                      No
                    </Button>
                  </div>
                ) : null}

                {questionFormat === 'single_select' ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {options.map((option) => (
                      <Button
                        key={option}
                        variant="outline"
                        onClick={() => submitAnswer(question.id, option)}
                        disabled={answerQuestion.isPending}
                      >
                        {option}
                      </Button>
                    ))}
                  </div>
                ) : null}

                {questionFormat === 'multi_select' ? (
                  <div className="mt-3 space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {options.map((option) => {
                        const selected =
                          multiSelectDrafts[question.id]?.includes(option) ??
                          false
                        return (
                          <Button
                            key={option}
                            variant={selected ? 'default' : 'outline'}
                            onClick={() =>
                              setMultiSelectDrafts((current) => {
                                const existing = current[question.id] ?? []
                                return {
                                  ...current,
                                  [question.id]: selected
                                    ? existing.filter(
                                        (value) => value !== option,
                                      )
                                    : [...existing, option],
                                }
                              })
                            }
                            disabled={answerQuestion.isPending}
                          >
                            {option}
                          </Button>
                        )
                      })}
                    </div>
                    <Button
                      onClick={() =>
                        submitAnswer(
                          question.id,
                          (multiSelectDrafts[question.id] ?? []).join(', '),
                        )
                      }
                      disabled={
                        answerQuestion.isPending ||
                        (multiSelectDrafts[question.id] ?? []).length === 0
                      }
                    >
                      Confirm choices
                    </Button>
                  </div>
                ) : null}

                {[
                  'short_text',
                  'integer',
                  'currency',
                  'date',
                  'long_text',
                ].includes(questionFormat) ? (
                  <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                    {questionFormat === 'long_text' ? (
                      <Textarea
                        value={drafts[question.id] ?? ''}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [question.id]: event.target.value,
                          }))
                        }
                        placeholder="Answer with enough detail for Jenny to continue accurately"
                      />
                    ) : (
                      <Input
                        type={
                          questionFormat === 'date'
                            ? 'date'
                            : questionFormat === 'integer' ||
                                questionFormat === 'currency'
                              ? 'number'
                              : 'text'
                        }
                        step={
                          questionFormat === 'currency' ? '0.01' : undefined
                        }
                        value={drafts[question.id] ?? ''}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [question.id]: event.target.value,
                          }))
                        }
                        placeholder={
                          questionFormat === 'currency'
                            ? 'e.g. 9000'
                            : questionFormat === 'integer'
                              ? 'e.g. 60'
                              : 'Answer briefly so Jenny can confirm the plan'
                        }
                      />
                    )}
                    <Button
                      onClick={() =>
                        submitAnswer(question.id, drafts[question.id] ?? '')
                      }
                      disabled={
                        answerQuestion.isPending ||
                        !(drafts[question.id] ?? '').trim()
                      }
                    >
                      Confirm
                    </Button>
                  </div>
                ) : null}
              </div>
            )
          })
        )}
      </div>
    </SectionCard>
  )
}
