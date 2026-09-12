'use client'

import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { CardCandidate } from '@/lib/api/cards/strategy'
import { formatCurrency, formatCurrencyWhole } from '@/lib/formatters'
import { StrategyCandidateChoice } from './StrategyCandidateChoice'

export function StrategyProposalComparison({
  candidate,
  candidates,
}: {
  candidate: CardCandidate
  candidates: CardCandidate[]
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const current = candidates.find(
    (c) =>
      c.key === candidate.key &&
      c.termsFingerprint === candidate.termsFingerprint &&
      c.incrementalValue === candidate.incrementalValue,
  )
  const distinct = candidates.filter(
    (c, i) =>
      c.productId !== candidate.productId &&
      candidates.findIndex((other) => other.productId === c.productId) === i,
  )
  const fit = distinct.find((c) => c.termsCurrent && !c.spendingGap)
  const stretch = distinct
    .filter((c) => c.spendingGap > 0)
    .sort(
      (a, b) =>
        Number(b.termsCurrent) - Number(a.termsCurrent) ||
        b.incrementalValue - a.incrementalValue,
    )[0]
  const others = [fit, stretch, ...distinct]
    .filter((c): c is CardCandidate => !!c)
    .filter(
      (c, i, all) =>
        all.findIndex((other) => other.productId === c.productId) === i,
    )
    .slice(0, 3)
  const rank =
    current?.termsCurrent && current.valueRank
      ? `Value #${current.valueRank} of ${current.comparedOffers} checked offers`
      : 'Value rank needs current offer evidence'
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant="outline"
                aria-expanded={open}
                aria-controls={id}
                onClick={() => setOpen(!open)}
              >
                {rank}
              </Button>
            </TooltipTrigger>
            <TooltipContent className="max-w-sm">
              Estimated additional value after the annual fee versus a
              2%-or-better baseline. Points use 1 cent or less; conditional
              credits are excluded. Distinct offers share a rank when values
              tie. Includes options needing up to 20% more spending, subject to
              eligibility confirmation.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <button
          type="button"
          className="text-xs underline"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => setOpen(!open)}
        >
          Compare here · including higher-spend options
        </button>
      </div>
      {current ? (
        <p className="text-xs text-text-muted">
          {current.spendingGap > 0
            ? 'Additional planned purchases needed.'
            : 'Fits your calculated spending with a seven-day buffer.'}
        </p>
      ) : null}
      {open ? (
        <section
          id={id}
          aria-label="Proposal comparison"
          className="space-y-3 rounded-lg border border-border/40 p-3"
        >
          <p className="text-sm text-text-muted">
            {current
              ? `${current.comparedOffers} checked offers qualify for this comparison from ${current.catalogOffers} catalog offers. `
              : 'This saved proposal needs a fresh comparison. '}
            This covers the maintained catalog, not every market or personalized
            offer. Checked bonus terms require supporting issuer evidence from
            the past 30 days; applicant eligibility still needs confirmation.
          </p>
          <p className="text-xs text-text-muted">
            Best fit favors spending you already do. Value rank also includes
            nearby options needing up to 20% more over their spending window.
            Other benefits and redemption preferences can change your choice.
          </p>
          {others.length ? (
            <ul className="space-y-3">
              {others.map((c) => (
                <li
                  key={c.key}
                  className="space-y-2 rounded-lg border border-border/40 p-3"
                >
                  <p className="font-medium">
                    {c.productName} · {c.applicant}
                  </p>
                  <p className="text-sm">
                    {formatCurrencyWhole(c.incrementalValue)} estimated
                    additional value · {formatCurrencyWhole(c.minimumSpend)} in{' '}
                    {c.windowDays} days
                  </p>
                  <p className="text-xs text-text-muted">
                    {c.spendingGap > 0
                      ? `Needs ${formatCurrency(c.spendingGap)} more in total (about ${formatCurrency(c.monthlyGap)}/month), keeping the seven-day buffer.`
                      : 'Fits the calculated spending with a seven-day buffer.'}
                  </p>
                  {!c.termsCurrent ? (
                    <p className="text-xs text-warning">
                      Offer figures need issuer verification before approval.
                    </p>
                  ) : null}
                  <StrategyCandidateChoice
                    candidate={c}
                    label={`Review ${c.productName}`}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm">
              No other catalog offers currently fit this comparison.
            </p>
          )}
          {!stretch ? (
            <p className="text-xs text-text-muted">
              No additional catalog option is within the 20% higher-spending
              range after the known card-history checks.
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}
