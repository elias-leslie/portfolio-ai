'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { HouseholdCreditCard } from '@/lib/api/cards'
import type { CardCandidate, SavedStrategy } from '@/lib/api/cards/strategy'
import { formatCurrencyWhole } from '@/lib/formatters'
import {
  useCardStrategy,
  useStrategyActions,
} from '@/lib/hooks/useCardStrategy'
import { CardBonusControls } from './CardBonusControls'
import { StrategyBillChecklist } from './StrategyBillChecklist'
import { StrategyPreferences } from './StrategyPreferences'

function CandidateDetails({ candidate }: { candidate: CardCandidate }) {
  return (
    <div className="space-y-3">
      <p className="text-lg font-semibold">{candidate.productName}</p>
      <p className="text-sm">
        <strong>{candidate.applicant}</strong> · suggested application window{' '}
        {candidate.applicationOn}–{candidate.applicationBy}
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <p className="text-xs text-text-muted">Required purchases</p>
          <p className="font-medium">
            {formatCurrencyWhole(candidate.minimumSpend)} in{' '}
            {candidate.windowDays} days
          </p>
        </div>
        <div>
          <p className="text-xs text-text-muted">Monthly pace</p>
          <p className="font-medium">
            {formatCurrencyWhole(candidate.monthlyRequired)}
          </p>
        </div>
        <div>
          <p className="text-xs text-text-muted">Estimated additional value</p>
          <p className="font-medium">
            {formatCurrencyWhole(candidate.incrementalValue)}
          </p>
        </div>
      </div>
      <p className="text-sm text-text-muted">{candidate.rationale}</p>
      <p className="text-xs text-text-muted">
        Annual fee: {formatCurrencyWhole(candidate.annualFee)}. The application
        window is a planning suggestion, not an offer-expiration date.
      </p>
      <details className="text-sm" open={!candidate.termsCurrent}>
        <summary className="cursor-pointer font-medium">
          {candidate.termsCurrent
            ? 'Evidence & eligibility checks'
            : 'Offer evidence needs review'}
        </summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-text-muted">
          {candidate.checks.map((check) => (
            <li key={check}>{check}</li>
          ))}
        </ul>
        <div className="mt-2 flex flex-wrap gap-3">
          {candidate.sourceUrls.map((url, index) => (
            <a
              key={url}
              className="underline"
              href={url}
              target="_blank"
              rel="noreferrer"
            >
              Issuer source {index + 1}
            </a>
          ))}
        </div>
        {!candidate.termsCurrent ? (
          <a className="mt-2 inline-block underline" href="#card-offer-terms">
            Review catalog evidence below
          </a>
        ) : null}
      </details>
    </div>
  )
}

function DraftApproval({ draft }: { draft: SavedStrategy }) {
  const [eligibility, setEligibility] = useState(false)
  const [cashFlow, setCashFlow] = useState(false)
  const decision = useStrategyActions().decision
  const candidate = draft.snapshot.candidate
  return (
    <section
      className="space-y-4 rounded-xl border border-primary/40 bg-primary/5 p-5"
      aria-label="Proposed card strategy"
    >
      <h3 className="font-semibold">Review this proposal</h3>
      {candidate ? (
        <CandidateDetails candidate={candidate} />
      ) : (
        <p>
          Keep the current cards and wait for a better-supported opportunity.
        </p>
      )}
      <p className="text-sm">
        Uses {formatCurrencyWhole(draft.snapshot.baseline.monthlyAvailable)}
        /month in ordinary purchases, after merchant reservations and the
        buffer.
      </p>
      {draft.snapshot.baseline.warnings.length ? (
        <ul className="list-disc space-y-1 pl-5 text-sm text-text-muted">
          {draft.snapshot.baseline.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
      {candidate ? (
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={eligibility}
            onChange={(e) => setEligibility(e.target.checked)}
          />
          I checked {candidate.applicant}’s complete card history and
          eligibility for this offer
        </label>
      ) : null}
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={cashFlow}
          onChange={(e) => setCashFlow(e.target.checked)}
        />
        I reviewed the cash-flow assumptions and can pay these ordinary
        purchases in full
      </label>
      <Button
        disabled={
          decision.isPending ||
          !cashFlow ||
          (!!candidate && (!eligibility || !candidate.termsCurrent))
        }
        onClick={() =>
          decision.mutate({
            id: draft.id,
            payload: {
              action: 'approve',
              fingerprint: draft.fingerprint,
              eligibilityConfirmed: eligibility,
              cashFlowConfirmed: cashFlow,
            },
          })
        }
      >
        {decision.isPending ? 'Approving…' : 'Approve this strategy'}
      </Button>
      <p className="text-xs text-text-muted">
        Approval starts tracking this revision. Record an application or payment
        change only after you make it.
      </p>
      {decision.error ? (
        <p role="alert" className="text-sm text-loss">
          {decision.error.message}
        </p>
      ) : null}
    </section>
  )
}

export function CardStrategyPanel({
  cards,
  onAddCard,
}: {
  cards: HouseholdCreditCard[]
  onAddCard: () => void
}) {
  const query = useCardStrategy()
  const { proposal, decision } = useStrategyActions()
  const [selectedCard, setSelectedCard] = useState('')
  if (query.isError)
    return (
      <section
        id="card-strategy"
        className="rounded-xl border border-border p-5"
        role="alert"
      >
        <h3 className="font-semibold">Card strategy unavailable</h3>
        <p className="my-2 text-sm">{query.error.message}</p>
        <Button variant="outline" onClick={() => query.refetch()}>
          Retry strategy
        </Button>
      </section>
    )
  if (!query.data)
    return (
      <section
        id="card-strategy"
        className="rounded-xl border border-border p-5"
        role="status"
      >
        Loading your household card strategy…
      </section>
    )
  const view = query.data
  const active = view.active
  const candidate = active?.snapshot.candidate
  const matchingCards = cards.filter(
    (c) =>
      c.productId === candidate?.productId &&
      c.player === candidate.player &&
      !['candidate', 'closed'].includes(c.status),
  )
  const relevantProgress = view.progress.filter(
    (p) => p.status !== 'received' || p.cardId === active?.actualCardId,
  )
  return (
    <section
      id="card-strategy"
      className="space-y-6 scroll-mt-24"
      aria-label="Household card strategy"
    >
      <div className="rounded-2xl border border-border/40 bg-surface-muted/20 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">Your card strategy</h2>
            <p className="mt-1 text-sm text-text-muted">
              {active
                ? active.status === 'paused'
                  ? 'Tracking reminders paused. Your approved plan is preserved.'
                  : 'An approved plan, tracked against your actual purchases.'
                : 'Choose a household plan before opening the next card.'}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">
              Ordinary bonus-spend allowance
            </p>
            <p className="text-2xl font-semibold">
              {formatCurrencyWhole(view.baseline.monthlyAvailable)}
              <span className="text-sm font-normal">/month</span>
            </p>
          </div>
        </div>
        {active ? (
          <div className="mt-5 space-y-4 border-t border-border/40 pt-4">
            <p className="text-sm text-text-muted">
              Approved allowance:{' '}
              {formatCurrencyWhole(active.snapshot.baseline.monthlyAvailable)}
              /month. Tracking uses the lower of this and the current estimate.
            </p>
            <p className="text-xs uppercase tracking-wide text-text-muted">
              {active.status === 'paused' ? 'Paused plan' : 'Approved plan'}
            </p>
            {candidate ? (
              <CandidateDetails candidate={candidate} />
            ) : (
              <p>
                Keep the current cards; wait for a better-supported opportunity.
              </p>
            )}
            <Button
              size="sm"
              variant="outline"
              disabled={decision.isPending}
              onClick={() =>
                decision.mutate({
                  id: active.id,
                  payload: {
                    action: active.status === 'paused' ? 'resume' : 'pause',
                    fingerprint: active.fingerprint,
                  },
                })
              }
            >
              {active.status === 'paused'
                ? 'Resume reminders'
                : 'Pause this plan'}
            </Button>
            {candidate &&
            !active.actualCardId &&
            active.status === 'approved' ? (
              <div className="space-y-2 rounded-xl border border-border/40 p-3">
                <p className="text-sm font-medium">
                  After the issuer opens the card
                </p>
                <p className="text-xs text-text-muted">
                  Add it to your wallet with the actual owner, opening date and
                  original offer, then link it here. A proposal is not an opened
                  account.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={onAddCard}>
                    Record opened card
                  </Button>
                  {matchingCards.length ? (
                    <>
                      <select
                        aria-label="Opened card to track"
                        className="rounded-lg border border-border bg-surface px-2 text-sm"
                        value={selectedCard}
                        onChange={(e) => setSelectedCard(e.target.value)}
                      >
                        <option value="">Choose matching card</option>
                        {matchingCards.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.accountLabel ?? c.product?.productName} ·{' '}
                            {c.openedDate ?? 'opening date missing'}
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        disabled={!selectedCard || decision.isPending}
                        onClick={() =>
                          decision.mutate({
                            id: active.id,
                            payload: {
                              action: 'link_card',
                              fingerprint: active.fingerprint,
                              cardId: selectedCard,
                            },
                          })
                        }
                      >
                        Track this card
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
        {decision.error ? (
          <p role="alert" className="mt-3 text-sm text-loss">
            {decision.error.message}
          </p>
        ) : null}
        {view.changes.length ? (
          <div className="mt-4 rounded-lg border border-warning/40 p-3">
            <p className="font-medium">Review what changed</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {view.changes.map((change) => (
                <li key={change}>{change}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      {relevantProgress.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {relevantProgress.map((p) => (
            <article
              key={p.cardId}
              className="space-y-2 rounded-xl border border-border/40 p-4"
            >
              <h3 className="font-semibold">{p.label}</h3>
              <p className="text-sm">
                {p.status.replaceAll('_', ' ')} · {p.applicant}
              </p>
              <p className="text-lg">
                {formatCurrencyWhole(p.posted)} posted
                {p.required !== null
                  ? ' / ' + formatCurrencyWhole(p.required)
                  : ''}
              </p>
              {p.pending !== 0 ? (
                <p className="text-xs text-text-muted">
                  {formatCurrencyWhole(p.pending)} pending, excluded from
                  completion.
                </p>
              ) : null}
              <p className="text-sm">
                Deadline: {p.deadline ?? 'needs confirmation'}
                {p.remaining !== null
                  ? ' · ' + formatCurrencyWhole(p.remaining) + ' remaining'
                  : ''}
              </p>
              {p.forecast !== null && p.status !== 'received' ? (
                <p className="text-sm">
                  Projected by deadline: {formatCurrencyWhole(p.forecast)}
                </p>
              ) : null}
              <p className="text-xs text-text-muted">{p.explanation}</p>
              {cards.find((c) => c.id === p.cardId) ? (
                <CardBonusControls
                  card={cards.find((c) => c.id === p.cardId)!}
                />
              ) : null}
              <a
                className="inline-block text-xs underline"
                href={'#card-' + p.cardId}
              >
                Review card history
              </a>
            </article>
          ))}
        </div>
      ) : null}

      {view.draft ? (
        <DraftApproval key={view.draft.id} draft={view.draft} />
      ) : null}
      <details
        className="rounded-xl border border-border/40 p-4"
        open={!active && !view.draft}
      >
        <summary className="cursor-pointer font-semibold">
          {active ? 'Next card & alternative plans' : 'Recommended next move'}
        </summary>
        <p className="my-3 text-sm text-text-muted">
          {view.recommendation} Comparisons cover the maintained card catalog.
        </p>
        {view.candidates[0] ? (
          <CandidateDetails candidate={view.candidates[0]} />
        ) : null}
        <div className="my-4 flex flex-wrap gap-2">
          {view.candidates[0] ? (
            <Button
              size="sm"
              disabled={proposal.isPending}
              onClick={() => proposal.mutate({ key: view.candidates[0]?.key })}
            >
              Prepare this proposal
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            disabled={proposal.isPending}
            onClick={() => proposal.mutate({ wait: true })}
          >
            Plan to wait
          </Button>
        </div>
        {view.candidates.length > 1 ? (
          <details>
            <summary className="cursor-pointer text-sm">
              Compare other cards and applicants
            </summary>
            <ul className="mt-3 space-y-3">
              {view.candidates.slice(1).map((c) => (
                <li
                  key={c.key}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border/40 p-3"
                >
                  <div>
                    <p className="text-sm font-medium">
                      {c.productName} · {c.applicant}
                    </p>
                    <p className="text-xs text-text-muted">
                      {formatCurrencyWhole(c.incrementalValue)} estimated extra
                      value · {formatCurrencyWhole(c.minimumSpend)} in{' '}
                      {c.windowDays} days
                      {!c.termsCurrent ? ' · terms need review' : ''}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={proposal.isPending}
                    onClick={() => proposal.mutate({ key: c.key })}
                  >
                    Review proposal
                  </Button>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {proposal.error ? (
          <p role="alert" className="mt-3 text-sm text-loss">
            {proposal.error.message}
          </p>
        ) : null}
      </details>

      <details
        className="rounded-xl border border-border/40 p-4"
        open={active?.status === 'approved' && !!active.actualCardId}
      >
        <summary className="cursor-pointer font-medium">
          Recurring bill checklist · {view.bills.length}
        </summary>
        <div className="mt-4">
          <StrategyBillChecklist
            bills={view.bills}
            planId={active?.id ?? null}
            enabled={active?.status === 'approved' && !!active.actualCardId}
          />
        </div>
      </details>
      <details className="rounded-xl border border-border/40 p-4">
        <summary className="cursor-pointer font-medium">
          Spending evidence & cash flow
        </summary>
        <div className="mt-3 space-y-2 text-sm">
          <p>
            Historical median:{' '}
            {formatCurrencyWhole(view.baseline.historicalMonthly)}/month before
            the buffer and changes in Costco shopping.
          </p>
          <ul className="list-disc space-y-1 pl-5">
            {view.baseline.months.map((m) => (
              <li key={m.month}>
                {m.month}: {formatCurrencyWhole(m.ordinaryCardSpend)} ordinary
                card purchases; {formatCurrencyWhole(m.reservedSpend)} reserved
                purchases.
              </li>
            ))}
          </ul>
          <p>
            Income:{' '}
            {view.baseline.incomeMonthly === null
              ? 'not established'
              : formatCurrencyWhole(view.baseline.incomeMonthly) +
                '/month'}{' '}
            · {view.baseline.incomeSource}
          </p>
          <p>
            Current free-cash estimate:{' '}
            {view.baseline.freeCash === null
              ? 'unavailable'
              : formatCurrencyWhole(view.baseline.freeCash)}
            . This is a cash-flow check, not additional bonus spending.
          </p>
          <ul className="list-disc space-y-1 pl-5 text-text-muted">
            {[...view.baseline.reservations, ...view.baseline.warnings].map(
              (text) => (
                <li key={text}>{text}</li>
              ),
            )}
          </ul>
        </div>
      </details>
      {view.reviewEvents.length ? (
        <div className="rounded-xl border border-border/40 p-4">
          <h3 className="font-medium">Upcoming card reviews</h3>
          {view.reviewEvents.map((event) => (
            <p key={event.id} className="mt-2 text-sm">
              {event.date} · {event.title}. {event.detail}
            </p>
          ))}
        </div>
      ) : null}
      <StrategyPreferences
        key={JSON.stringify(view.settings)}
        value={view.settings}
      />
      {view.history.length ? (
        <details className="rounded-xl border border-border/40 p-4">
          <summary className="cursor-pointer font-medium">
            Strategy history
          </summary>
          <ul className="mt-3 space-y-2 text-sm">
            {view.history.map((plan) => (
              <li key={plan.id}>
                {plan.createdAt.slice(0, 10)} · {plan.status} ·{' '}
                {plan.snapshot.candidate
                  ? plan.snapshot.candidate.productName +
                    ' for ' +
                    plan.snapshot.candidate.applicant
                  : 'Wait with current cards'}{' '}
                · {formatCurrencyWhole(plan.snapshot.baseline.monthlyAvailable)}
                /month
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
