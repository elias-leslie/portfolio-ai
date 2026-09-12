'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import type {
  MonthlyReviewPlan,
  MonthlyReviewRecord,
  ReviewDecision,
} from '@/lib/api/household'
import { formatCurrency } from '@/lib/formatters'
import { useConfirmFact } from '@/lib/hooks/useHousehold'

const outcomeLabels = {
  not_reviewed: 'Not reviewed yet',
  kept: 'Kept',
  changed: 'Changed',
  not_done: 'Not done',
}

function serialize(record: MonthlyReviewRecord) {
  return JSON.stringify({
    expected_income: record.expectedIncome,
    planned_asset_draw: record.plannedAssetDraw,
    planned_spending: record.plannedSpending,
    additional_commitments: record.additionalCommitments,
    funding_note: record.fundingNote,
    decisions: record.decisions,
  })
}

export function MonthlyReviewAgreement({ plan }: { plan: MonthlyReviewPlan }) {
  const save = useConfirmFact()
  const [editing, setEditing] = useState(false)
  const [income, setIncome] = useState('')
  const [draw, setDraw] = useState('')
  const [spending, setSpending] = useState('')
  const [commitments, setCommitments] = useState('')
  const [note, setNote] = useState('')
  const [decisions, setDecisions] = useState<ReviewDecision[]>([])
  const money = (value: number | null) =>
    value == null ? 'Not agreed' : formatCurrency(value, { decimals: 0 })

  function edit() {
    setIncome(plan.expectedIncome == null ? '' : String(plan.expectedIncome))
    setDraw(plan.plannedAssetDraw == null ? '' : String(plan.plannedAssetDraw))
    setSpending(
      plan.plannedSpending == null ? '' : String(plan.plannedSpending),
    )
    setCommitments(
      plan.additionalCommitments == null
        ? ''
        : String(plan.additionalCommitments),
    )
    setNote(plan.record.fundingNote)
    setDecisions(
      Array.from(
        { length: 3 },
        (_, index) =>
          plan.record.decisions[index] ?? {
            action: '',
            outcome: 'not_reviewed',
            note: '',
          },
      ),
    )
    setEditing(true)
  }

  async function submit() {
    try {
      const number = (value: string) => {
        if (!value.trim()) return null
        const result = Number(value.replaceAll(',', ''))
        if (!Number.isFinite(result) || result < 0)
          throw new Error(
            'Enter non-negative dollar amounts, or leave unknown amounts blank.',
          )
        return result
      }
      await save.mutateAsync({
        factKey: `monthly_review:${plan.month}`,
        factValue: serialize({
          expectedIncome: number(income),
          plannedAssetDraw: number(draw),
          plannedSpending: number(spending),
          additionalCommitments: number(commitments),
          fundingNote: note,
          decisions: decisions.filter((item) => item.action.trim()),
        }),
      })
      setEditing(false)
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Could not save this review.',
      )
    }
  }

  async function updatePrevious(
    index: number,
    outcome: ReviewDecision['outcome'],
  ) {
    if (!plan.previousRecord || !plan.previousMonth) return
    try {
      const record = {
        ...plan.previousRecord,
        decisions: plan.previousRecord.decisions.map((item, position) =>
          position === index ? { ...item, outcome } : item,
        ),
      }
      await save.mutateAsync({
        factKey: `monthly_review:${plan.previousMonth}`,
        factValue: serialize(record),
      })
    } catch {
      toast.error('Could not save the previous review outcome.')
    }
  }

  return (
    <SectionCard
      variant="surface"
      title="Funding and agreed changes"
      actions={
        <Button size="sm" variant="outline" onClick={edit}>
          Review agreement
        </Button>
      }
    >
      <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div>
          <dt className="text-text-muted">Expected take-home income</dt>
          <dd>{money(plan.expectedIncome)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Planned cash / portfolio draw</dt>
          <dd>{money(plan.plannedAssetDraw)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Ordinary spending plan</dt>
          <dd>{money(plan.plannedSpending)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Saving and other commitments</dt>
          <dd>{money(plan.additionalCommitments)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-sm">
        {plan.fundingBalance == null
          ? 'Confirm funding and the complete spending plan before judging whether this month is funded.'
          : plan.fundingBalance >= 0
            ? `${money(plan.fundingBalance)} remains in the agreed funding plan.`
            : `${money(Math.abs(plan.fundingBalance))} still needs a funding decision.`}
      </p>
      <p className="mt-1 text-xs text-text-muted">
        {plan.incomeSource}.{' '}
        {plan.confirmedAt
          ? `Agreement saved ${new Date(plan.confirmedAt).toLocaleDateString()}.`
          : 'Amounts shown are current proposals until saved for this month.'}
      </p>
      {plan.unplannedCategories.length > 0 ? (
        <p className="mt-1 text-xs text-text-muted">
          No agreed cap: {plan.unplannedCategories.join(', ')}.
        </p>
      ) : null}
      <details className="mt-2 text-xs text-text-muted">
        <summary className="cursor-pointer">What these amounts include</summary>
        <p className="mt-1">{plan.detail}</p>
      </details>
      {plan.record.fundingNote ? (
        <p className="mt-2 text-sm">{plan.record.fundingNote}</p>
      ) : null}
      {plan.record.decisions.length ? (
        <ul className="mt-3 space-y-1 text-sm">
          {plan.record.decisions.map((item) => (
            <li key={item.action}>
              {item.action} · {outcomeLabels[item.outcome]}
              {item.note ? ` · ${item.note}` : ''}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-text-muted">
          Use this month’s review to agree on one to three changes, if any.
        </p>
      )}
      {plan.previousRecord?.decisions.length ? (
        <div className="mt-4 border-t border-border/30 pt-3">
          <p className="mb-2 text-sm font-medium">From {plan.previousMonth}</p>
          {plan.previousRecord.decisions.map((item, index) => (
            <label
              key={item.action}
              className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm"
            >
              <span>{item.action}</span>
              <select
                aria-label={`Outcome: ${item.action}`}
                className="rounded border border-border bg-surface p-2"
                value={item.outcome}
                disabled={save.isPending}
                onChange={(event) =>
                  void updatePrevious(
                    index,
                    event.target.value as ReviewDecision['outcome'],
                  )
                }
              >
                {Object.entries(outcomeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      ) : null}
      {editing ? (
        <form
          className="mt-4 space-y-3 border-t border-border/30 pt-4"
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ['Expected take-home income', income, setIncome],
              ['Planned cash / portfolio draw', draw, setDraw],
              ['Ordinary spending plan', spending, setSpending],
              ['Saving and other commitments', commitments, setCommitments],
            ].map(([label, value, setValue]) => (
              <label key={String(label)} className="text-sm">
                {String(label)}
                <Input
                  aria-label={String(label)}
                  inputMode="decimal"
                  value={String(value)}
                  onChange={(event) => {
                    if (typeof setValue === 'function')
                      setValue(event.target.value)
                  }}
                  placeholder="Not agreed"
                />
              </label>
            ))}
          </div>
          <label className="block text-sm">
            Funding note
            <textarea
              aria-label="Funding note"
              className="mt-1 block min-h-16 w-full rounded border border-border bg-surface p-2"
              value={note}
              maxLength={1000}
              onChange={(event) => setNote(event.target.value)}
              placeholder="For example, a planned draw while one person is working."
            />
          </label>
          {decisions.map((item, index) => (
            <div key={index} className="grid gap-2 sm:grid-cols-[2fr_1fr]">
              <Input
                aria-label={`Agreed change ${index + 1}`}
                value={item.action}
                maxLength={240}
                placeholder={`Agreed change ${index + 1} (optional)`}
                onChange={(event) =>
                  setDecisions((current) =>
                    current.map((decision, position) =>
                      position === index
                        ? { ...decision, action: event.target.value }
                        : decision,
                    ),
                  )
                }
              />
              <select
                aria-label={`Outcome for change ${index + 1}`}
                className="rounded border border-border bg-surface p-2 text-sm"
                value={item.outcome}
                onChange={(event) =>
                  setDecisions((current) =>
                    current.map((decision, position) =>
                      position === index
                        ? {
                            ...decision,
                            outcome: event.target
                              .value as ReviewDecision['outcome'],
                          }
                        : decision,
                    ),
                  )
                }
              >
                {Object.entries(outcomeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <Textarea
                aria-label={`Outcome note for change ${index + 1}`}
                value={item.note}
                maxLength={500}
                placeholder="Outcome or context (optional)"
                onChange={(event) =>
                  setDecisions((current) =>
                    current.map((decision, position) =>
                      position === index
                        ? { ...decision, note: event.target.value }
                        : decision,
                    ),
                  )
                }
                className="sm:col-span-2"
              />
            </div>
          ))}
          <div className="flex gap-2">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save this month’s agreement'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
    </SectionCard>
  )
}
