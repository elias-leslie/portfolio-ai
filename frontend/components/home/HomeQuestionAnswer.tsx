'use client'

import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { HomeActionItem } from '@/lib/api/home'
import { useAnswerHouseholdQuestion } from '@/lib/hooks/useHousehold'

export function HomeQuestionAnswer({
  question,
  title,
}: {
  question: NonNullable<HomeActionItem['question']>
  title: string
}) {
  const answer = useAnswerHouseholdQuestion()
  const inputId = useId()
  const [draft, setDraft] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const format = question.format.toLowerCase()
  const boolean = ['boolean', 'yes_no'].includes(format)
  const multiple = format === 'multi_select' && question.options.length > 0
  const choices = boolean
    ? ['Yes', 'No']
    : ['single_select', 'multiple_choice', 'multi_select'].includes(format)
      ? question.options
      : []
  const numeric = [
    'integer',
    'number',
    'decimal',
    'currency',
    'percentage',
  ].includes(format)

  const save = (value: string) => {
    if (value.trim() && !answer.isPending) {
      answer.mutate({ questionId: question.id, answerText: value.trim() })
    }
  }

  return (
    <form
      className="w-full space-y-2"
      aria-label={`Answer: ${title}`}
      onSubmit={(event) => {
        event.preventDefault()
        save(multiple ? selected.join(', ') : draft)
      }}
    >
      {choices.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {choices.map((choice) => (
            <Button
              key={choice}
              type="button"
              size="sm"
              variant={
                multiple && selected.includes(choice) ? 'default' : 'outline'
              }
              aria-pressed={multiple ? selected.includes(choice) : undefined}
              disabled={answer.isPending}
              onClick={() =>
                multiple
                  ? setSelected((current) =>
                      current.includes(choice)
                        ? current.filter((v) => v !== choice)
                        : [...current, choice],
                    )
                  : save(boolean ? choice.toLowerCase() : choice)
              }
            >
              {choice}
            </Button>
          ))}
        </div>
      ) : (
        <>
          <label htmlFor={inputId} className="sr-only">
            Your answer to {title}
          </label>
          <Input
            id={inputId}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            type={numeric ? 'number' : format === 'date' ? 'date' : 'text'}
            step={format === 'integer' ? '1' : 'any'}
            placeholder="Your answer"
            disabled={answer.isPending}
            required
          />
        </>
      )}
      {multiple || choices.length === 0 ? (
        <Button
          type="submit"
          size="sm"
          disabled={
            answer.isPending || !(multiple ? selected.length : draft.trim())
          }
        >
          Save answer
        </Button>
      ) : null}
      {answer.isPending ? (
        <p role="status" className="text-xs text-text-muted">
          Saving answer…
        </p>
      ) : null}
      {answer.isError ? (
        <p role="alert" className="text-xs text-loss">
          Answer wasn’t saved. Please try again.
        </p>
      ) : null}
    </form>
  )
}
