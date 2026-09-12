'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  BillPaymentPreference,
  BillSuggestion,
} from '@/lib/api/cards/strategy'
import { formatCurrency } from '@/lib/formatters'
import { useStrategyActions } from '@/lib/hooks/useCardStrategy'

function BillRow({
  bill,
  planId,
  enabled,
}: {
  bill: BillSuggestion
  planId: string | null
  enabled: boolean
}) {
  const [open, setOpen] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [benefits, setBenefits] = useState(false)
  const [fee, setFee] = useState('')
  const [discount, setDiscount] = useState('')
  const { bill: move, billPreference } = useStrategyActions()
  const labels = {
    suggested: 'Suggested',
    confirmed: 'Changed · awaiting first charge',
    observed: 'First charge verified',
    skipped: 'Keep in place',
    already_on_card: 'Already on this card',
    kept_in_place: 'Keep in place',
  }
  return (
    <li className="space-y-3 rounded-xl border border-border/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{bill.merchant}</p>
          <p className="text-sm text-text-muted">
            {formatCurrency(bill.amount)} · {bill.cadence} · next expected{' '}
            {bill.firstChargeDueOn ?? bill.nextExpected ?? 'unknown'}
          </p>
        </div>
        <span className="text-xs text-text-muted">{labels[bill.status]}</span>
      </div>
      <p className="text-xs text-text-muted">
        Currently: {bill.currentAccount ?? 'Payment account unknown'}.{' '}
        {bill.alreadyCardSpend
          ? 'Already included in the spending estimate.'
          : 'Excluded from the bonus-spending estimate.'}
      </p>
      <label className="block text-sm">
        Payment preference
        <select
          className="mt-1 block w-full rounded-md border border-border bg-surface p-2 text-sm"
          value={bill.paymentPreference}
          disabled={billPreference.isPending || move.isPending}
          onChange={(event) => {
            setOpen(false)
            billPreference.mutate({
              key: bill.key,
              preference: event.target.value as BillPaymentPreference,
            })
          }}
        >
          <option value="automatic">
            {bill.paidFromCma ? 'Automatic · keep on CMA' : 'Automatic'}
          </option>
          <option value="keep_current">Keep current payment</option>
          <option value="consider_card">Consider a credit card</option>
        </select>
      </label>
      {bill.paymentReason ? (
        <p className="text-xs text-text-muted">{bill.paymentReason}</p>
      ) : null}
      {bill.observedOn ? (
        <p className="text-sm text-gain">
          Posted charge observed {bill.observedOn}.{' '}
          <a
            className="underline"
            href={
              '/money?tab=ledger&search=' + encodeURIComponent(bill.merchant)
            }
          >
            View ledger
          </a>
        </p>
      ) : null}
      <details className="text-xs text-text-muted">
        <summary className="cursor-pointer">Why this is recurring</summary>
        <p className="mt-2">{bill.evidence}</p>
      </details>
      {enabled &&
      planId &&
      !['observed', 'already_on_card', 'kept_in_place'].includes(
        bill.status,
      ) ? (
        <div className="flex flex-wrap gap-2">
          {bill.status === 'suggested' && !bill.keepCurrentPayment ? (
            <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>
              Review payment change
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            disabled={move.isPending}
            onClick={() =>
              move.mutate({
                id: planId,
                key: bill.key,
                payload: {
                  status: bill.status === 'suggested' ? 'skipped' : 'reset',
                },
              })
            }
          >
            {bill.status === 'suggested'
              ? 'Keep in place'
              : bill.status === 'skipped'
                ? 'Reconsider for this plan'
                : 'Undo confirmation'}
          </Button>
        </div>
      ) : null}
      {open && enabled && planId && !bill.keepCurrentPayment ? (
        <form
          className="space-y-3 border-t border-border/40 pt-3"
          onSubmit={(event) => {
            event.preventDefault()
            move.mutate(
              {
                id: planId,
                key: bill.key,
                payload: {
                  status: 'confirmed',
                  cardAccepted: accepted,
                  benefitsChecked: benefits,
                  feePerCharge: fee === '' ? null : Number(fee),
                  lostDiscount: discount === '' ? null : Number(discount),
                },
              },
              { onSuccess: () => setOpen(false) },
            )
          }}
        >
          <p className="text-sm">
            Check the provider’s payment settings, then record the change you
            made. Costs or lost discounts mean keeping this bill in place for
            the current plan.
          </p>
          <label className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
            />
            The provider accepts this card and I changed the payment method
          </label>
          <label className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={benefits}
              onChange={(e) => setBenefits(e.target.checked)}
            />
            I checked existing card benefits and autopay discounts
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              Fee per charge
              <Input
                type="number"
                min="0"
                step="0.01"
                required
                value={fee}
                onChange={(e) => setFee(e.target.value)}
                placeholder="Enter 0 if none"
              />
            </label>
            <label className="text-sm">
              Lost discount per charge
              <Input
                type="number"
                min="0"
                step="0.01"
                required
                value={discount}
                onChange={(e) => setDiscount(e.target.value)}
                placeholder="Enter 0 if none"
              />
            </label>
          </div>
          <Button size="sm" disabled={move.isPending || !accepted || !benefits}>
            Confirm payment change
          </Button>
        </form>
      ) : null}
      {move.error ? (
        <p role="alert" className="text-sm text-loss">
          {move.error.message}
        </p>
      ) : null}
      {billPreference.error ? (
        <p role="alert" className="text-sm text-loss">
          {billPreference.error.message}
        </p>
      ) : null}
    </li>
  )
}

export function StrategyBillChecklist({
  bills,
  planId,
  enabled,
}: {
  bills: BillSuggestion[]
  planId: string | null
  enabled: boolean
}) {
  return (
    <section className="space-y-3" aria-label="Recurring bill checklist">
      <div>
        <h3 className="font-semibold">Recurring bills</h3>
        <p className="text-sm text-text-muted">
          CMA bills stay put by default to avoid card fees. Set exceptions per
          bill; preferences carry forward to future plans.
        </p>
      </div>
      {!enabled ? (
        <p className="text-sm text-text-muted">
          Approve a plan and link its opened card to start confirming payment
          changes.
        </p>
      ) : null}
      {bills.length ? (
        <ul className="grid gap-3 lg:grid-cols-2">
          {bills.map((bill) => (
            <BillRow
              key={bill.key}
              bill={bill}
              planId={planId}
              enabled={enabled}
            />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-text-muted">
          No current recurring bills have enough evidence yet.
        </p>
      )}
    </section>
  )
}
